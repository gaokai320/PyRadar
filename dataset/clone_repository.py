import argparse
import json
import os
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

from pyradar.repository import Repository


def chunks(lst: list[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(urls: list[str], base_folder: str):
    for url in urls:
        Repository(url, base_folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--chunk_size", type=int, default=1)
    parser.add_argument("--base_folder", type=str, required=True)
    args = parser.parse_args()

    df = pd.read_csv(
        "data/metadata_retriever.csv", keep_default_na=False, low_memory=False
    )
    repo_urls = df[df["redirected"] != ""]["redirected"].unique()
    remaining = []
    for url in repo_urls:
        forge, user, repo = url.split("/")[-3:]
        path = f"{args.base_folder}/repository/{forge}/{user}/{repo}/repo"
        if not os.path.exists(path):
            remaining.append(url)
    print(
        f"{len(repo_urls)} unique code repositories",
        f"{len(remaining)} code repositories not cloned",
    )

    processes = args.processes
    chunk_size = args.chunk_size
    print(processes, "processes", chunk_size, "repos per batch")
    chunk_lst = chunks(remaining, chunk_size)

    Parallel(n_jobs=processes, backend="multiprocessing")(
        delayed(main)(urls, args.base_folder) for urls in chunk_lst
    )

    cloned_urls = []
    for url in repo_urls:
        forge, user, repo = url.split("/")[-3:]
        path = f"{args.base_folder}/repository/{forge}/{user}/{repo}/repo"
        if os.path.exists(path):
            cloned_urls.append(url)

    with open("data/cloned_repos.json", "w") as outf:
        json.dump(cloned_urls, outf)
