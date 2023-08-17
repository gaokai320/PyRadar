import configparser
import json
import logging
import math
import os
import random
import re
import time
from calendar import monthrange
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from joblib import Parallel, delayed
from packaging.utils import canonicalize_name
from packaging.version import Version
from tqdm import tqdm

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


def get_maintainers(name: str, session=None) -> Optional[list[str]]:
    maintainers = []
    if not session:
        session = requests.Session()
        session.headers.update(headers)
        session.headers.update({"Connection": "close"})
        session.proxies = proxies

    r = session.get(f"https://pypi.org/project/{name}", timeout=10)
    if r.status_code == 404:
        return maintainers

    soup = BeautifulSoup(r.content, "html.parser")

    for span in soup.find_all("span", {"class": "sidebar-section__user-gravatar-text"}):
        name = span.text.strip("\n ")
        maintainers.append(name)

    return list(set(maintainers))


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


def maintainer_main(names: list[str], i: int):
    session = requests.Session()
    session.headers.update(headers)
    session.headers.update({"Connection": "close"})
    session.proxies = proxies
    res = {}
    for name in names:
        try:
            res[name] = get_maintainers(name, session)
        except Exception as e:
            logger.error(f"{name} error: {e}")
        finally:
            time.sleep(random.randint(5, 10))
    with open(f"data/pypi_maintainers-{i}.json", "w") as f:
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
        f"{len(left_repo_urls)} repositories, {n_jobs} processes, {chunk_size} repositories per chunk"
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


def collect_pypi_maintainers(n_jobs: int, chunk_size: int):
    if not os.path.exists("data/package_names.json"):
        names = list(
            pd.read_csv(
                "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
            )["name"].unique()
        )
        with open("data/package_names.json", "w") as f:
            json.dump(names, f)
    else:
        names = json.load(open("data/package_names.json"))

    res = {}
    if os.path.exists("data/pypi_maintainers.json"):
        res = json.load(open("data/pypi_maintainers.json"))
    left_pkgs = list(set(names) - set(res.keys()))
    print(
        f"{len(left_pkgs)} packages, {n_jobs} processes, {chunk_size} packages per chunk"
    )
    chunk = chunks(left_pkgs, chunk_size)
    num_chunk = math.ceil(len(left_pkgs) / chunk_size)

    Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(maintainer_main)(names, i) for i, names in enumerate(chunk)
    )

    for i in range(num_chunk):
        for k, v in json.load(open(f"data/pypi_maintainers-{i}.json")).items():
            res[k] = v
        os.remove(f"data/pypi_maintainers-{i}.json")
    with open("data/pypi_maintainers.json", "w") as f:
        json.dump(res, f)


def normalize_url(url: str):
    url = url.lower().strip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url


def positive_data():
    if not os.path.exists("data/gh_package.json"):
        print("data/gh_package.json not exists, please run --package first")
        return

    df = pd.read_csv(
        "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
    )
    downloads = pd.read_csv("data/downloads.csv")

    df = pd.read_csv(
        "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
    )
    downloads = pd.read_csv("data/downloads.csv")

    gh_pkgs = {}
    for k, v in json.load(open("data/gh_package.json")).items():
        for name in v:
            name = canonicalize_name(name)
            if name == "example":
                continue
            # sshuttle move its repository from https://github.com/apenwarr/sshuttle to https://github.com/sshuttle/sshuttle
            if name == "sshuttle" and k == "https://github.com/apenwarr/sshuttle":
                continue
            gh_pkgs[name] = gh_pkgs.get(name, set())
            gh_pkgs[name].add(normalize_url(k))
    gh_pkgs = {k: list(v)[0] for k, v in gh_pkgs.items()}
    gh_pkgs = pd.DataFrame(gh_pkgs.items(), columns=["name", "url"])
    # only consider github packages that also exist in pypi and have the same url found by metadata retriever
    gh_pkgs = gh_pkgs.merge(
        df[["name", "version", "redirected"]].rename(columns={"redirected": "url"}),
        on=["name", "url"],
    )
    print(
        f"GitHub source: {len(gh_pkgs['name'].unique())} packages, {len(gh_pkgs)} releases"
    )

    top4000_pkgs = df[
        df["name"].isin(downloads.head(4000)["name"]) & (df["redirected"] != "")
    ][["name", "version", "redirected"]]
    top4000_pkgs.rename(columns={"redirected": "url"}, inplace=True)
    print(
        f"Top 4000 PyPI packages: {len(top4000_pkgs['name'].unique())} packages, {len(top4000_pkgs)} releases"
    )

    res = gh_pkgs.merge(top4000_pkgs, how="outer", indicator=True)
    res["github"] = res["_merge"].apply(
        lambda x: True if x in ["left_only", "both"] else False
    )
    res["top4000"] = res["_merge"].apply(
        lambda x: True if x in ["right_only", "both"] else False
    )
    res.drop(columns=["_merge"], inplace=True)

    # insert sampleproject packages.
    if res[res["name"] == "sampleproject"].empty:
        sample_project_df = df[
            (df["name"] == "sampleproject") & (df["redirected"] != "")
        ][["name", "version", "redirected"]].copy()
        sample_project_df.rename(columns={"redirected": "url"}, inplace=True)
        sample_project_df["github"] = False
        sample_project_df["top4000"] = False
        print(
            f"sampleproject has {len(sample_project_df)} releases with repository url"
        )
        res = pd.concat([res, sample_project_df], ignore_index=True)
    res.drop(
        res[
            (res["url"] == "https://github.com/pypa/sampleproject")
            & (res["name"] != "sampleproject")
        ].index,
        inplace=True,
    )
    print(f"Total: {len(res['name'].unique())} packages, {len(res)} releases")
    res.to_csv("data/positive_dataset_all.csv", index=False)

    # select the url of the latest version' url
    def select_version(x):
        versions = []
        for row in x.itertuples(index=False):
            try:
                Version(row.version)
                versions.append((row.version, row.github, row.top4000))
            except:
                pass
        if versions:
            versions.sort(key=lambda x: Version(x[0]))
        else:
            versions = [
                (row.version, row.github, row.top4000)
                for row in x.itertuples(index=False)
            ]
            versions.sort(key=lambda x: x[0])
        version, github, top4000 = versions[-1]
        return pd.Series({"version": version, "github": github, "top4000": top4000})

    sample_releases = res.groupby(["name", "url"]).apply(select_version).reset_index()
    sample_releases.drop(
        sample_releases[
            (sample_releases["url"] == "https://github.com/pypa/sampleproject")
            & (sample_releases["name"] != "sampleproject")
        ].index,
        inplace=True,
    )
    print(f"{len(sample_releases)} records in positive_dataset.csv")

    sample_releases.to_csv("data/positive_dataset_sample.csv", index=False)


def negative_data():
    if not os.path.exists("data/positive_dataset_all.csv"):
        print(
            "data/positive_dataset_all.csv not exists, please generate positive data first with `positive_data` function"
        )
        return

    df = pd.read_csv(
        "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
    )
    positive_data_all = pd.read_csv("data/positive_dataset_all.csv")
    pkg_maintainers = json.load(open("data/pypi_maintainers.json"))

    # select releases whose repository url the same as positive datasets
    candidate_releases = df[df["redirected"].isin(positive_data_all["url"])][
        ["name", "version", "redirected"]
    ].rename(columns={"redirected": "url"})
    candidate_releases = candidate_releases.merge(
        positive_data_all[["name", "version", "url"]], how="left", indicator=True
    )
    candidate_releases = candidate_releases[
        candidate_releases["_merge"] == "left_only"
    ].drop(columns=["_merge"])
    print(
        len(candidate_releases),
        "candidate releases",
        len(candidate_releases["name"].unique()),
        "candidate packages",
    )

    # select candidate packages whose PyPI maintainers different with positive datasets.
    candidate_pkgs = (
        candidate_releases[["name", "url"]]
        .drop_duplicates()
        .merge(
            positive_data_all[["name", "url"]].drop_duplicates(),
            how="left",
            on="url",
            suffixes=["_candidate", "_true"],
        )
    )
    candidate_pkgs["negative"] = candidate_pkgs[["name_candidate", "name_true"]].apply(
        lambda x: not bool(
            set(pkg_maintainers[x["name_candidate"]]).intersection(
                set(pkg_maintainers[x["name_true"]])
            )
        ),
        axis=1,
    )
    candidate_pkgs = (
        candidate_pkgs.groupby(["name_candidate", "url"])["negative"]
        .apply(lambda x: any(x))
        .to_frame()
        .reset_index()
    )
    # if a packages have both True and False value, we choose True to ensure that packages in the dataset are negative.
    # e.g., tf-nightly-cpu has the same repository with tensorflow but with different pypi maintainers
    # tf-nightly-cpu also has the same repository with tf-nightly and with the same pypi maintainers.
    # in this case, we consider tf-nightly-cpu's repository information is correct, which inline with the truth.
    negative_pkgs = candidate_pkgs[candidate_pkgs["negative"]][
        ["name_candidate", "url"]
    ].rename(columns={"name_candidate": "name"})

    negative_releases = negative_pkgs.merge(candidate_releases)
    print(
        len(negative_pkgs),
        "negative packages",
        len(negative_releases),
        "negative releases",
    )
    print(
        len(
            negative_pkgs[
                negative_pkgs["url"] == "https://github.com/pypa/sampleproject"
            ]["name"].unique()
        ),
        "packages' code repository is https://github.com/pypa/sampleproject",
    )

    negative_releases.to_csv("data/negative_dataset_full.csv", index=False)

    # select the url of the latest version' url
    def select_version(x):
        versions = []
        for v in x["version"]:
            try:
                Version(v)
                versions.append(v)
            except:
                pass
        if versions:
            versions.sort(key=lambda x: Version(x))
        else:
            versions = [v for v in x]
            versions.sort(key=lambda x: x)
        return pd.Series({"version": versions[-1]})

    sample_releases = (
        negative_releases.groupby(["name", "url"]).apply(select_version).reset_index()
    )
    print(len(sample_releases), "releases in the sample dataset")
    sample_releases.to_csv("data/negative_dataset_sample.csv", index=False)


def build_dataset():
    positive_data()
    negative_data()


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
    parser.add_argument(
        "--maintainer", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument("--n_jobs", type=int, default=1)
    parser.add_argument("--chunk_size", type=int, default=100)
    args = parser.parse_args()

    if args.repository:
        collect_repo(tokens[0])

    if args.package:
        collect_gh_package(args.n_jobs, args.chunk_size)

    if args.maintainer:
        collect_pypi_maintainers(args.n_jobs, args.chunk_size)

    if args.dataset:
        build_dataset()
