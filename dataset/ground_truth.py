import configparser
import logging
import math
import os
import random
import re
import time
from calendar import monthrange
from typing import Optional

import requests
from bs4 import BeautifulSoup
from joblib import Parallel, delayed

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

pattern = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", flags=re.IGNORECASE)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
}

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


class GHRepoSearch:
    def __init__(self, token: Optional[str] = None) -> None:
        self.headers = headers.copy()
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.base_url = "https://api.github.com/search/repositories?q={}&per_page=100"

    def query(self, query_str: str) -> list[str]:
        repos = []
        i = 1
        init_url = self.base_url.format(query_str)
        query_url = init_url

        total_count = -1

        while True:
            response = requests.get(query_url, headers=self.headers)
            rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
            rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
            cur_ts = int(time.time())
            logger.info(
                f"Query Url: {query_url}, RateLimit-Remaining: {rate_limit_remaining}, RateLimit-Reset: {rate_limit_reset}, Current Time: {cur_ts}"
            )

            if (response.status_code == 403) or (
                (rate_limit_remaining == 0) and (cur_ts < rate_limit_reset)
            ):
                sleep_time = rate_limit_reset - cur_ts + 1
                time.sleep(sleep_time)
                logger.info(f"sleep {sleep_time}s...")
                continue
            if total_count == -1:
                total_count = response.json()["total_count"]
                logger.info(f"{total_count} repositories")
                if total_count > 1000:
                    logger.warning(
                        f"Too many (>1000) repositories for {query_url}, consider narrow down the query"
                    )
            logger.info(f"{len(response.json()['items'])} repositories in page {i}")
            for item in response.json()["items"]:
                repos.append([item["html_url"], item["stargazers_count"]])
            if i * 100 < min(total_count, 1000):
                # print(len(repos), total_count)
                i += 1
                query_url = init_url + f"&page={i}"
            else:
                break

        return repos


def collect_repo(token: Optional[str] = None):
    base_query = "language:python+stars:>100+created:{}"

    repos = []
    ghrs = GHRepoSearch(token)
    repos.extend(ghrs.query(base_query.format("<2010-01-01")))

    for year in range(2010, 2024):
        for month in range(1, 13):
            if year == 2023 and month == 3:
                break
            _, last_day = monthrange(year, month)
            query_str = base_query.format(
                f"{year}-{'%02d' % month}-01..{year}-{'%02d' % month}-{last_day}"
            )

            tmp = ghrs.query(query_str)
            repos.extend(tmp)
            print(f"{query_str}: {len(tmp)} repositories")

    print(len(repos))
    with open("data/gh_repos.json", "w") as outf:
        json.dump(repos, outf)


def get_packages(
    repo_url: str, session: Optional[requests.Session] = None
) -> list[str]:
    packages = []

    if not session:
        session = requests.Session()
        session.headers.update(headers)
        session.headers.update({"Connection": "close"})
        session.proxies = proxies
    r = session.get(f"{repo_url.strip('/')}/network/dependents", timeout=10)
    soup = BeautifulSoup(r.content, "html.parser")

    for menu in soup.find_all("span", {"class": "select-menu-item-text"}):
        name = menu.text.strip("\n ")
        if pattern.match(name):
            packages.append(name)

    for p in soup.find_all("p", {"class": "mb-4"}):
        name = p.strong.text
        if pattern.match(name):
            packages.append(name)
    return list(set(packages))


def main(repo_urls: list[str], i: int):
    session = requests.Session()
    session.headers.update(headers)
    session.headers.update({"Connection": "close"})
    session.proxies = proxies
    res = {}
    for repo_url in repo_urls:
        try:
            res[repo_url] = get_packages(repo_url, session)
        except Exception as e:
            logger.error(f"{repo_url} error: {e}")
        finally:
            time.sleep(random.randint(5, 10))
    with open(f"data/gh_package-{i}.json", "w") as f:
        json.dump(res, f)


def chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def collect_gh_package(n_jobs: int, chunk_size: int):
    if not os.path.exists("data/gh_repos.json"):
        print("data/gh_repos.json not exists, please run --repository first")
        return
    res = {}
    if os.path.exists("data/gh_package.json"):
        res = json.load(open("data/gh_package.json"))

    all_repo_urls = json.load(open("data/gh_repos.json"))
    left_repo_urls = list(set(all_repo_urls) - set(res.keys()))
    print(
        f"{len(left_repo_urls)} repositories, {n_jobs} processes, {chunk_size} repositorier per chunk"
    )
    chunk = chunks(left_repo_urls, chunk_size)
    num_chunk = math.ceil(len(left_repo_urls) / chunk_size)

    Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(main)(urls, i) for i, urls in enumerate(chunk)
    )

    for i in range(num_chunk):
        for k, v in json.load(open(f"data/gh_package-{i}.json")).items():
            res[k] = v
        os.remove(f"data/gh_package-{i}.json")
    with open("data/gh_package.json", "w") as f:
        json.dump(res, f)


def build_dataset():
    if not os.path.exists("data/gh_package.json"):
        print("data/gh_package.json not exists, please run --package first")
        return


if __name__ == "__main__":
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s: %(msg)s")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--package", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--dataset", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument("--n_jobs", type=int, default=1)
    parser.add_argument("--chunk_size", type=int, default=100)
    args = parser.parse_args()

    if args.repository:
        collect_repo(tokens[0])

    if args.package:
        collect_gh_package(args.n_jobs, args.chunk_size)

    if args.dataset:
        build_dataset()
