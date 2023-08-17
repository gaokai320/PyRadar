import argparse
import json
import os
from pathlib import Path

from joblib import Parallel, delayed

from pyradar.repository import Repository


def chunks(lst: list[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(urls: list[str]):
    for url in urls:
        Repository(url, "/data/kyle/pypi_data")


if __name__ == "__main__":
    repo_urls = json.load(open("data/repo_urls.json"))
    remaining = []
    for url in repo_urls:
        forge, user, repo = url.split("/")[-3:]
        path = f"/data/kyle/pypi_data/repository/{forge}/{user}/{repo}/repo"
        if not os.path.exists(path):
            remaining.append(url)
    print(
        f"{len(repo_urls)} unique code repositories",
        f"{len(remaining)} code repositories not cloned",
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, default=1)
    parser.add_argument("--chunk_size", type=int, default=1)
    args = parser.parse_args()

    processes = args.processes
    chunk_size = args.chunk_size
    print(processes, "processes", chunk_size, "repos per batch")
    chunk_lst = chunks(remaining, chunk_size)

    Parallel(n_jobs=processes, backend="multiprocessing")(
        delayed(main)(urls) for urls in chunk_lst
    )

    cloned_folders = [
        str(_) for _ in Path("/data/kyle/pypi_data").glob("repository/*/*/*/repo")
    ]
    cloned_urls = ["https://" + "/".join(f.split("/")[5:-1]) for f in cloned_folders]
    cloned_urls = list(set(cloned_urls).intersection(set(repo_urls)))
    print(f"{len(cloned_urls)} successfully cloned repositories")

    with open("data/cloned_repos.json", "w") as outf:
        json.dump(cloned_urls, outf)
