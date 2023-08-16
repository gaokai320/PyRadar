import configparser
import csv
import logging
import math
import os
import random
import time
from collections import Counter
from functools import reduce
from typing import Optional

import pandas as pd
import requests
from joblib import Parallel, delayed
from pymongo import MongoClient
from tqdm import tqdm

from baselines.librariesio import LibrariesIO
from baselines.ossgadget import OSSGadget
from baselines.py2src import Py2Src
from baselines.release import Release
from baselines.warehouse import Warehouse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]
config = configparser.ConfigParser()
config.read("config.ini")

proxies = None
if "proxies" in config:
    if "http" in config["proxies"] and "https" in config["proxies"]:
        proxies = {
            "http": config["proxies"]["http"],
            "https": config["proxies"]["https"],
        }
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Connection": "close",
}

baselines = {
    "ossgadget": OSSGadget,
    "warehouse": Warehouse,
    "librariesio": LibrariesIO,
    "py2src": Py2Src,
}


def chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def py2src_main(data: list, i: int):
    session = requests.Session()
    session.headers.update(headers)
    session.verify = False
    session.proxies = proxies
    with open(f"data/py2src-{i}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "name",
                "version",
                "py2src_ossgadget",
                "py2src_badge",
                "py2src_homepage",
                "py2src_metadata",
                "py2src_readthedocs",
                "py2src_statistics",
                "py2src_final",
            ]
        )
        for name, versions in data:
            for version in versions:
                for metadata in release_metadata.find(
                    {"name": name, "version": version},
                    projection={
                        "_id": 0,
                        "name": 1,
                        "version": 1,
                        "home_page": 1,
                        "download_url": 1,
                        "project_urls": 1,
                        "description": 1,
                        "description_content_type": 1,
                    },
                ):
                    name = metadata["name"]
                    version = metadata["version"]
                    try:
                        urls = Py2Src.parse_metadata(metadata, session, logger)
                        tmp = [_ for _ in urls if _]
                        mode_url = Counter(tmp).most_common(1)[0][0] if tmp else None
                        line = [name, version]
                        line.extend(urls)
                        line.append(mode_url)
                        writer.writerow(line)
                        f.flush()
                    except Exception as e:
                        logger.error(f"Exception: {name}, {version}, {e}")
                time.sleep(random.randint(5, 10))

    session.close()


def run_py2src(
    name: Optional[str] = None,
    version: Optional[str] = None,
    n_jobs: int = 1,
    chunk_size: int = 100,
):
    if name:
        metadata = Release(name, version).metadata
        res = Py2Src.parse_metadata(metadata)
        print(res)
        return res

    df = pd.DataFrame()
    if os.path.exists("data/py2src.csv"):
        df = pd.read_csv("data/py2src.csv", low_memory=False, keep_default_na=False)
    releases = []
    for metadata in release_metadata.find(
        {}, projection={"_id": 0, "name": 1, "version": 1}
    ):
        releases.append((metadata["name"], metadata["version"]))

    existing = []
    for row in df.itertuples(index=False):
        existing.append((row.name, row.version))

    left_releases = list(set(releases) - set(existing))
    print(f"{len(left_releases)} packages to be processed")
    data = {}
    for name, version in left_releases:
        data[name] = data.get(name, [])
        data[name].append(version)
    data = list(data.items())
    chunk_lst = chunks(data, chunk_size)
    num_chunks = math.ceil(len(data) / chunk_size)
    Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(py2src_main)(task, i) for i, task in enumerate(chunk_lst)
    )

    for i in range(num_chunks):
        data = pd.read_csv(
            f"data/py2src-{i}.csv", low_memory=False, keep_default_na=False
        )
        df = pd.concat([df, data], axis=0)
        os.remove(f"data/py2src-{i}.csv")
    df.to_csv("data/py2src.csv", index=False)


def run(
    baseline: str,
    name: Optional[str] = None,
    version: Optional[str] = None,
    n_jobs: int = 1,
    chunk_size: int = 100,
):
    if baseline not in baselines.keys():
        print(f"baseline should be {list(baselines.keys())}, not{baseline}")
        return
    if baseline == "py2src":
        run_py2src(name, version, n_jobs, chunk_size)
        return
    func = baselines[baseline]
    if name:
        metadata = Release(name, version).metadata
        res = func.parse_metadata(metadata)
        print(res)
        return

    with open(f"data/{baseline}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version", baseline])
        for metadata in tqdm(
            release_metadata.find(
                {},
                projection={
                    "_id": 0,
                    "name": 1,
                    "version": 1,
                    "home_page": 1,
                    "download_url": 1,
                    "project_urls": 1,
                },
            )
        ):
            try:
                name = metadata["name"]
                version = metadata["version"]
                repo_url = func.parse_metadata(metadata)
                if repo_url:
                    writer.writerow([name, version, repo_url.lower()])
                else:
                    writer.writerow([name, version, None])
            except Exception as e:
                logger.error(f"{name}, {version}, {e}")


def dump_to_database():
    for baseline in baselines.keys():
        if not os.path.exists(f"data/{baseline}.csv"):
            print(
                f"data/{baseline}.csv not exists, pelease run --baseline {baseline} first"
            )
            return

    db = MongoClient("127.0.0.1", 27017)["radar"]
    db.drop_collection("package_repository_url")
    col = db.get_collection("package_repository_url")

    ossgadget = pd.read_csv("data/ossgadget.csv", keep_default_na=False)
    warehouse = pd.read_csv("data/warehouse.csv", keep_default_na=False)
    librariesio = pd.read_csv("data/librariesio.csv", keep_default_na=False)
    py2src = pd.read_csv("data/py2src.csv", low_memory=False, keep_default_na=False)

    res = reduce(
        lambda left, right: pd.merge(left, right, on=["name", "version"]),
        [ossgadget, warehouse, librariesio, py2src],
    )

    col.insert_many(res.to_dict("records"))
    col.create_index([("name", 1), ("version", 1)])
    col.create_index([("name", 1)])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=str)
    parser.add_argument("--name", type=str, default=None)
    parser.add_argument("--version", type=str, default=None)
    parser.add_argument("--n_jobs", type=int, default=1)
    parser.add_argument("--chunk_size", type=int, default=100)
    parser.add_argument("--dump", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    if args.baseline:
        run(args.baseline, args.name, args.version, args.n_jobs, args.chunk_size)
    if args.dump:
        dump_to_database()
