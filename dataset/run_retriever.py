import argparse
import configparser
import json
import logging
import math
import os
import random
import sys
import time
from collections import Counter
from typing import Optional

import pandas as pd
import requests
from joblib import Parallel, delayed
from pymongo import MongoClient
from tqdm import tqdm

from pyradar.utils import download
from pyradar.woc_retriever import WoCRetriever, defork, get_most_common, restore_url

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

config = configparser.ConfigParser()
config.read("config.ini")
proxies = None
if "proxies" in config:
    if "http" in config["proxies"] and "https" in config["proxies"]:
        proxies = {
            "http": config["proxies"]["http"],
            "https": config["proxies"]["https"],
        }
tokens = []
if "tokens" in config:
    tokens = config["tokens"].get("tokens", "").split(",")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
}


def get_candidates_main(name: str, version: str, base_folder: str, mirror: str = None):
    try:
        wr = WoCRetriever(name, version, base_folder, mirror=mirror)
        if wr.fileshas:
            return wr.get_candidates()
    except Exception as e:
        logger.error(f"{name}, {version}, {e}")


def get_candidates(
    data_path: str,
    save_path: str,
    base_folder: str,
    n_jobs: int = 1,
    mirror: Optional[str] = None,
):
    retriever_dataset = pd.read_csv(data_path, low_memory=False, keep_default_na=False)
    results = Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(get_candidates_main)(name, version, base_folder, mirror)
        for name, version in tqdm(
            retriever_dataset[["name", "version"]].itertuples(index=False),
            file=sys.stdout,
            total=len(retriever_dataset),
        )
    )
    print("Finish retrieving, start dumping results")
    data = {}
    for i, name in enumerate(retriever_dataset["name"]):
        data[name] = results[i]

    with open(save_path, "w") as outf:
        json.dump(data, outf)


def get_sample_most_common(candidate_path: str, save_path: str, n: int):
    if not os.path.exists(candidate_path):
        print(
            f"{candidate_path} does not exist, please run --candidates or --candidate_remaining first."
        )
        return

    candidate = json.load(open(candidate_path))
    res = {}
    for k, v in tqdm(candidate.items(), file=sys.stdout):
        try:
            res[k] = get_most_common(v[1], n)
        except:
            print(k)

    with open(save_path, "w") as outf:
        json.dump(res, outf)


def defork_main(urls: list[str], i: int, save_path: str):
    session = requests.Session()
    session.headers.update(headers)
    token = tokens[i % len(tokens)]
    session.headers.update({"Authorization": f"Bearer {token}"})
    session.proxies = proxies
    res = {}
    for url in urls:
        try:
            res[url] = defork(url, session)
            time.sleep(random.randint(1, 5))
        except Exception as e:
            logger.error(f"{url}, {e}")
    with open(f"{save_path}.{i}", "w") as f:
        json.dump(res, f)


def chunks(lst, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def do_defork(most_common_path: str, save_path: str, chunk_size: int):
    if not os.path.exists(most_common_path):
        print(
            f"{most_common_path} does not exist, please run --most_common or --most_common_remaining first."
        )
        return

    most_common = json.load(open(most_common_path))
    urls = []
    for v in most_common.values():
        for uri, _ in v:
            url = restore_url(uri)
            if url:
                urls.append(url)
    print(len(urls))
    urls = list(set(urls))

    res = {}
    if os.path.exists(save_path):
        res = json.load(open(save_path))
    remaining = list(set(urls) - set(res.keys()))
    print(f"{len(urls)} unique urls in total, {len(remaining)} urls left")

    chunk = chunks(remaining, chunk_size)
    num_chunks = math.ceil(len(remaining) / chunk_size)
    print(f"{len(tokens)} tokens, {chunk_size} urls perl batch, {num_chunks} batches")
    Parallel(n_jobs=len(tokens), backend="multiprocessing")(
        delayed(defork_main)(urls, i, save_path) for i, urls in enumerate(chunk)
    )

    for i in range(num_chunks):
        for k, v in json.load(open(f"{save_path}.{i}")).items():
            res[k] = v
        os.remove(f"{save_path}.{i}")
    with open(save_path, "w") as f:
        json.dump(res, f)


def do_final(deforked_path: str, most_common_path: str, data_path: str):
    if not os.path.exists(deforked_path):
        print(
            f"{deforked_path} does not exist, please run --defork or --defork_remaining first."
        )
        return
    deforked = json.load(open(deforked_path))
    most_common = json.load(open(most_common_path))
    res = {}
    for k, woc_uris in most_common.items():
        finals = []
        for woc_uri, _ in woc_uris:
            url = restore_url(woc_uri)
            url = deforked.get(url)
            if url:
                finals.append(url)
        if not finals:
            res[k] = ""
        else:
            res[k] = Counter(finals).most_common(1)[0][0]

    retriever_dataset = pd.read_csv(data_path, low_memory=False, keep_default_na=False)
    retriever_dataset["final"] = retriever_dataset["name"].map(res).fillna("")
    retriever_dataset.to_csv(data_path, index=False)


def download_main(data: pd.DataFrame, dist_folder: str):
    for name, filename, url in data[["name", "filename", "url"]].itertuples(
        index=False
    ):
        try:
            save_path = os.path.join(dist_folder, name, filename)
            download(url, save_path, check=True)
        except Exception as e:
            logger.error(f"{name} {url}, {e}")


def download_remaining(
    base_folder: str, n_jobs: int, chunk_size: int, mirror: Optional[str] = None
):
    df = pd.read_csv(
        "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
    )
    print(f"{len(df)} releases in total")
    remaining_df = df[
        df["metadata_retriever"].isin(["", "https://github.com/pypa/sampleproject"])
    ][["name", "version", "metadata_retriever"]]
    print(
        f"{len(remaining_df)} releases do not have source code repository information"
    )
    dist_col = MongoClient("127.0.0.1", port=27017)["radar"]["distribution_file_info"]
    sdist_df = pd.DataFrame(
        dist_col.find({"packagetype": "sdist"}, projection={"_id": 0, "packagetype": 0})
    )
    print(f"{len(sdist_df)} releases have source distributions")

    remaining_df = remaining_df.merge(sdist_df)
    print(
        f"{len(remaining_df)} releases without source code repository have source distributions"
    )
    remaining_df["upload_time"] = pd.to_datetime(remaining_df["upload_time"])
    remaining_df = remaining_df[remaining_df["upload_time"] < "2021-10"]
    print(f"{len(remaining_df)} releases are before 2021-10")
    remaining_latest_df = remaining_df.sort_values(
        "upload_time", ascending=False
    ).drop_duplicates("name")
    remaining_latest_df = remaining_latest_df[
        remaining_latest_df["filename"].str.endswith(
            (".tar.gz", ".zip", ".egg", ".whl")
        )
    ]
    remaining_latest_df[["name", "version", "metadata_retriever"]].to_csv(
        "data/retriever_dataset_remaining.csv", index=False
    )
    print(f"{len(remaining_latest_df)} packages in total")

    if mirror:
        remaining_latest_df["url"] = remaining_latest_df["url"].apply(
            lambda x: x.replace("https://files.pythonhosted.org", mirror)
        )

    dist_folder = os.path.join(base_folder, "distribution")
    chunk = chunks(remaining_latest_df, chunk_size)
    Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(download_main)(data, dist_folder)
        for data in tqdm(chunk, file=sys.stdout)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_folder", type=str, required=True)
    parser.add_argument("--mirror", type=str, default=None)
    parser.add_argument("--n_jobs", default=1, type=int)
    parser.add_argument("--chunk_size", default=400, type=int)
    parser.add_argument("--n_candidate", default=5, type=int)
    parser.add_argument("--thresh", default=0.5, type=float)
    parser.add_argument(
        "--candidates", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--most_common", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--defork", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--download_remaining", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--candidate_remaining", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--most_common_remaining", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--defork_remaining", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument("--final", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument(
        "--final_remaining", default=False, action=argparse.BooleanOptionalAction
    )
    args = parser.parse_args()

    if args.candidates:
        get_candidates(
            "data/retriever_dataset.csv",
            "data/candidate.json",
            args.base_folder,
            args.n_jobs,
            args.mirror,
        )

    if args.most_common:
        get_sample_most_common(
            "data/candidate.json", "data/most_common.json", args.n_candidate
        )

    if args.defork:
        do_defork("data/most_common.json", "data/defored.json", args.chunk_size)

    if args.final:
        do_final(
            "data/deforked.json",
            "data/most_common.json",
            "data/retriever_dataset.csv",
        )

    if args.download_remaining:
        download_remaining(args.base_folder, args.n_jobs, args.chunk_size, args.mirror)

    if args.candidate_remaining:
        get_candidates(
            "data/retriever_dataset_remaining.csv",
            "data/candidate_remaining.json",
            args.base_folder,
            args.n_jobs,
            args.mirror,
        )

    if args.most_common_remaining:
        get_sample_most_common(
            "data/candidate_remaining.json",
            "data/most_common_remaining.json",
            args.n_candidate,
        )

    if args.defork_remaining:
        do_defork(
            "data/most_common_remaining.json",
            "data/deforked_remaining.json",
            args.chunk_size,
        )

    if args.final_remaining:
        do_final(
            "data/deforked_remaining.json",
            "data/most_common_remaining.json",
            "data/retriever_dataset_remaining.csv",
        )
