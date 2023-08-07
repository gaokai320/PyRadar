import json
import logging
import os
import urllib.request
from typing import Optional

import pandas as pd

from pyradar.utils import DistReader, configure_logger


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
            lambda x: os.path.join(mirror, "/".join(x.rsplit("/", 4)[1:]))
        )

    name = df.iloc[0]["name"]
    res = {}
    for row in df.itertuples(index=False):
        save_path = os.path.join(dist_folder, name, row.filename)
        success = download(row.url, save_path, check=check)
        success = True
        if not success:
            continue
        reader = DistReader(save_path)
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

    with open(f"data/dist_diff-{i}.json", "w") as outf:
        json.dump(res, outf)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str)
    parser.add_argument("--version", type=str)
    parser.add_argument("--dest", type=str)
    parser.add_argument("--all", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--mirror", default=None, type=str)
    parser.add_argument("--processes", default=1, type=int)
    parser.add_argument("--chunk_size", default=100, type=int)
    args = parser.parse_args()

    df = pd.read_csv("data/sampled_releases.csv", keep_default_na=False)
    if args.all:
        print(
            f"dest: {args.dest}, mirror: {args.mirror}, processes: {args.processes}, chunk_size: {args.chunk_size}"
        )
        from joblib import Parallel, delayed

        chunk_lst = chunks(df, args.chunk_size)
        Parallel(n_jobs=args.processes, backend="multiprocessing")(
            delayed(main)(data, i, args.dest, args.mirror)
            for i, data in enumerate(chunk_lst)
        )
    else:
        print(
            f"name: {args.name}, version: {args.version}, dest: {args.dest}, mirror: {args.mirror}"
        )
        list_release_dist_files(
            df[(df["name"] == args.name) & (df["version"] == args.version)],
            args.dest,
            args.mirror,
        )
