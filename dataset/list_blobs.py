import argparse
import json
import logging
import os
from pathlib import Path

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

    cloned_urls = json.load(open("data/cloned_repos.json"))
    remaining = []
    for url in cloned_urls:
        forge, user, repo = url.split("/")[-3:]
        path = f"{args.base_folder}/repository/{forge}/{user}/{repo}/index.json"
        if not os.path.exists(path):
            remaining.append(url)

    print(
        f"{len(cloned_urls)} repos, {len(remaining)} left, {processes} processes, {chunk_size} repos per batch"
    )

    chunk_lst = chunks(remaining, chunk_size)

    Parallel(n_jobs=processes, backend="multiprocessing")(
        delayed(main)(task, args.base_folder) for task in chunk_lst
    )
