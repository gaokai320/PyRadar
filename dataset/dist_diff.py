import json
import logging
import os
import urllib.request
from typing import Optional

import pandas as pd

from pyradar.utils import DistReader

logging.basicConfig(format="%(message)s", level=logging.ERROR)


def download(
    url: str,
    save_path: str,
    check: bool = True,
    max_try=3,
    logger: logging.Logger = None,
) -> bool:
    if check and os.path.exists(save_path):
        return True

    logger = logger or logging.getLogger(__name__)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    success = False
    i = 0

    while (not success) and (i < max_try):
        try:
            urllib.request.urlretrieve(url, save_path)
            success = True
        except Exception as e:
            i += 1
            logger.error(f"Error downloading {url}, retry {i}: {e}")

    return success


def comp(dict1, dict2):
    res = {"sdist-only": {}, "bdist-only": {}}
    shas1 = set(dict1.keys())
    shas2 = set(dict2.keys())
    for sha in shas1 - shas2:
        res["sdist-only"][sha] = list(dict1[sha])
    for sha in shas2 - shas1:
        res["bdist-only"][sha] = list(dict2[sha])

    for sha in shas1.intersection(shas2):
        filenames1 = list(dict1[sha])
        filenames2 = list(dict2[sha])
        for f1 in filenames1.copy():
            for f2 in filenames2:
                if f1.rsplit("/", 1)[-1] == f2.rsplit("/", 1)[-1]:
                    filenames1.remove(f1)
                    filenames2.remove(f2)
                    break
        exclude1 = set(filenames1)
        exclude2 = set(filenames2)
        if exclude1:
            res["sdist-only"][sha] = list(exclude1)
        if exclude2:
            res["bdist-only"][sha] = list(exclude2)
    return res


def cal_release_dists_diff(data: dict[str, list[list[str]]]):
    sdist_files = {}
    bdist_files = {}

    for name, files in data.items():
        if name.endswith(".tar.gz") or name.endswith(".zip"):
            for filename, filesha in files:
                if filename.rsplit("/", 1)[-1] == "PKG-INFO":
                    continue
                # A .tar.gz source distribution (sdist) contains a single top-level directory: https://packaging.python.org/en/latest/specifications/source-distribution-format/#source-distribution-file-format
                if filename.rsplit("/", 1)[0].endswith(".egg-info"):
                    continue
                sdist_files[filesha] = sdist_files.get(filesha, set())
                sdist_files[filesha].add(filename)

        if name.endswith(".egg"):
            for filename, filesha in files:
                if filename.rsplit("/", 1)[0].endswith("EGG-INFO"):
                    continue
                bdist_files[filesha] = bdist_files.get(filesha, set())
                bdist_files[filesha].add(filename)

        if name.endswith(".whl"):
            for filename, filesha in files:
                if filename.rsplit("/", 1)[0].endswith(".dist-info"):
                    continue
                bdist_files[filesha] = bdist_files.get(filesha, set())
                bdist_files[filesha].add(filename)

    return comp(sdist_files, bdist_files)


def list_release_dist_files(
    df: pd.DataFrame,
    dist_folder: str,
    mirror: Optional[str] = None,
    check: bool = True,
    logger: logging.Logger = None,
):
    logger = logger or logging.getLogger(__name__)
    df = df.copy()
    if mirror:
        df.loc[:, "url"] = df["url"].apply(
            lambda x: x.replace("https://files.pythonhosted.org", mirror)
        )
    name = df.iloc[0]["name"]
    res = {}
    for row in df.itertuples(index=False):
        save_path = os.path.join(dist_folder, name, row.filename)
        success = download(row.url, save_path, check=check)
        success = True
        if not success:
            continue
        reader = DistReader(save_path, translate_newline=True)
        res[row.filename] = reader.file_shas()

    return res


def chunks(df: pd.DataFrame, chunk_size: int):
    names = list(df["name"].unique())
    for i in range(0, len(names), chunk_size):
        yield df[df["name"].isin(names[i : i + chunk_size])]


def main(data: pd.DataFrame, i: int, dist_folder: str, mirror: Optional[str] = None):
    # logger = configure_logger("dist_diff-{i}", f"log/dist_diff-{i}.log", logging.ERROR)

    res = {}
    for name in data["name"].unique():
        try:
            res[name] = list_release_dist_files(
                data[data["name"] == name], dist_folder, mirror
            )
        except Exception as e:
            logging.error(f"Error for {name}: {e}")

    with open(f"data/release_dist_files-{i}.json", "w") as outf:
        json.dump(res, outf)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str)
    parser.add_argument("--version", type=str)
    parser.add_argument("--base_folder", type=str)
    parser.add_argument("--all", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--mirror", default=None, type=str)
    parser.add_argument("--processes", default=1, type=int)
    parser.add_argument("--chunk_size", default=100, type=int)
    args = parser.parse_args()

    df = pd.read_csv("data/sampled_releases.csv", keep_default_na=False)
    if args.all:
        print(
            f"dest: {args.base_folder}/distribution, mirror: {args.mirror}, processes: {args.processes}, chunk_size: {args.chunk_size}"
        )
        import math

        from joblib import Parallel, delayed

        chunk_lst = chunks(df, args.chunk_size)
        num_chunks = math.ceil(len(df["name"].unique()) / args.chunk_size)
        Parallel(n_jobs=args.processes, backend="multiprocessing")(
            delayed(main)(data, i, f"{args.base_folder}/distribution", args.mirror)
            for i, data in enumerate(chunk_lst)
        )
        res = {}
        for i in range(num_chunks):
            data = json.load(open(f"data/release_dist_files-{i}.json"))
            for name, dist_files in data.items():
                try:
                    res[name] = cal_release_dists_diff(dist_files)
                except Exception as e:
                    logging.error(i, name)
        with open("data/sampled_dist_diff.json", "w") as f:
            json.dump(res, f)
        for i in range(num_chunks):
            os.remove(f"data/release_dist_files-{i}.json")
    else:
        print(
            f"name: {args.name}, version: {args.version}, dest: {args.base_folder}/distribution, mirror: {args.mirror}"
        )
        res = list_release_dist_files(
            df[(df["name"] == args.name) & (df["version"] == args.version)],
            f"{args.base_folder}/distribution",
            args.mirror,
        )
        print(cal_release_dists_diff(res))
