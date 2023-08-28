import argparse
import json
import logging
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

from pyradar.repository import Repository

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


def chunks(lst: list[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(urls: list[str], base_folder: str):
    for url in urls:
        repo = Repository(url, base_folder)
        if len(repo.commit_shas) > 10000:
            print(f"{url}: {len(repo.commit_shas)} commits")
        repo.traverse_all()
        logging.error(f"Finish {url}")


def clean(base_folder: str):
    fs = list(Path(f"{base_folder}/repository/").glob("*/*/*/index.json"))
    for f in fs:
        f.unlink(missing_ok=True)
    fs = list(Path(f"{base_folder}/repository/").glob("*/*/*/snapshot-*.json"))
    for f in fs:
        f.unlink(missing_ok=True)


if __name__ == "__main__":
    cloned_urls = json.load(open("data/cloned_repos.json"))
    logging.basicConfig(format="%(message)s", level=logging.ERROR)

    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--chunk_size", type=int, default=1)
    parser.add_argument("--base_folder", type=str, required=True)
    parser.add_argument("--clean", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    processes = args.processes
    chunk_size = args.chunk_size
    do_clean = args.clean

    print(f"{processes} processes, {chunk_size} repos per batch")

    chunk_lst = chunks(cloned_urls, chunk_size)

    Parallel(n_jobs=processes, backend="multiprocessing")(
        delayed(main, args.base_folder)(task) for task in chunk_lst
    )
