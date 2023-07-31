import json
import logging
from pathlib import Path
from typing import Generator, Iterable, TypeVar

import pandas as pd

from pyradar.repository import Repository

logging.basicConfig(format="%(message)s", level=logging.ERROR)

T = TypeVar("T")


def chunks(lst: Iterable[T], n: int) -> Generator[list[T], None, None]:
    lst = lst[::-1]
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(urls: list[str]):
    for url in urls:
        print(f"Start traversing {url}")
        repo = Repository(url, "/data/kyle/pypi_data")
        # if len(repo.commit_shas) > 10000:
        #     logging.error(f"Too many commits: {url}")
        #     continue
        repo.traverse_all()
        logging.error(f"Finish {url}")


def clean():
    fs = list(Path("/data/kyle/pypi_data/repository/").glob("*/*/*/index.json"))
    for f in fs:
        f.unlink(missing_ok=True)
    fs = list(Path("/data/kyle/pypi_data/repository/").glob("*/*/*/snapshot-*.json"))
    for f in fs:
        f.unlink(missing_ok=True)


def repo_list():
    df = pd.read_csv("data/metadata_retriever.csv")
    repo_urls = df["PyRadar.MetadataRetriever"].dropna().unique()
    print(len(repo_urls), "unique code repositories")

    cloned_folders = [
        str(_) for _ in Path("/data/kyle/pypi_data").glob("repository/*/*/*/repo")
    ]
    cloned_urls = ["https://" + "/".join(f.split("/")[5:-1]) for f in cloned_folders]
    cloned_urls = list(set(cloned_urls).intersection(set(repo_urls)))
    print(f"{len(cloned_urls)} successfully cloned repositories")

    with open("data/cloned_repos.json", "w") as outf:
        json.dump(cloned_urls, outf, indent=4)


if __name__ == "__main__":
    import argparse

    from joblib import Parallel, delayed

    # clean()
    # repo_list()

    cloned_urls = json.load(open("data/cloned_repos.json"))

    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--batch_size", type=int, default=20000)
    parser.add_argument("--batch_id", type=int, default=0)
    parser.add_argument("--clean", default=False, action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    processes = args.processes
    batch_size = args.batch_size
    batch_id = args.batch_id
    do_clean = args.clean

    print(
        f"{processes} processes, {batch_size} repos per batch, doing batch {batch_id}, clean: {do_clean}"
    )

    process_urls = cloned_urls[batch_id * batch_size : (batch_id + 1) * batch_size]
    chunk_lst = chunks(process_urls, 10)
    # segments = len(process_urls) // processes + 1
    # print(segments, "repositories per process")

    Parallel(n_jobs=processes, backend="multiprocessing")(
        delayed(main)(task) for task in chunk_lst
    )
