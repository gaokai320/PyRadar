import configparser
import csv
import json
import logging
import math
import os
import random
import re
import time
from typing import Optional
from urllib.parse import urlparse

import pandas as pd
import requests
import validators
from bs4 import BeautifulSoup
from joblib import Parallel, delayed
from pymongo import MongoClient
from tqdm import tqdm

from baselines.utils import GITHUB_RESERVED_NAMES

db = MongoClient("127.0.0.1", 27017)["radar"]
release_metadata = db["release_metadata"]
tqdm.pandas()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

config = configparser.ConfigParser()
config.read("config.ini")
tokens = []
if "tokens" in config:
    tokens = config["tokens"].get("tokens", "").split(",")


repo_pattern = re.compile(
    r"(github\.com|bitbucket\.org|gitlab\.com)/([a-z0-9_\.\-]+)/([a-z0-9_\.\-]+)",
    flags=re.I,
)

sub_pattern = re.compile(r"[^a-zA-Z0-9]")

url_cache = {}


def normalize_url(url: str):
    url = url.lower().strip("/")
    if url.endswith(".git"):
        url = url[:-4]
    if len(url.split("/")) != 5:
        return ""
    return url


def find_repo_from_field(data: str) -> list[str]:
    if not data:
        return []

    urls = []
    for matchObj in repo_pattern.findall(data):
        platform, user, repo = matchObj
        if platform.lower() == "github.com" and user.lower() in GITHUB_RESERVED_NAMES:
            continue
        url = f"https://{platform}/{user}/{repo}"
        urls.append(normalize_url(url))
    return urls


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Connection": "close",
}
proxies = {"http": "http://162.105.88.97:7890", "https": "http://162.105.88.97:7890"}


def _configure_session():
    session = requests.Session()
    session.headers.update(headers)
    session.proxies = proxies

    return session


def find_repo_from_webpage(url: str, session: Optional[requests.Session] = None):
    if url in url_cache:
        return url_cache[url]

    res = []
    if not session:
        session = _configure_session()
    try:
        response = session.get(url, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.findAll("a"):
            href_url = link.get("href", "")
            repo_urls = find_repo_from_field(href_url)
            if repo_urls:
                res.extend(repo_urls)
        res = list(set(res))
        url_cache[url] = res
    except requests.exceptions.HTTPError as errh:
        logger.error(f"{url}: Http Error, {errh}")
    except requests.exceptions.ConnectionError as errc:
        logger.error(f"{url}: Error Connecting, {errc}")
    except requests.exceptions.Timeout as errt:
        logger.error(f"{url}: Timeout Error, {errt}")
    except Exception as err:
        logger.error(f"{url}: OOps, Something Else, {err}")
    finally:
        return res


def validate_url(url: str) -> bool:
    url = url.strip("/").lower()

    # url points to a file
    if url.endswith((".tar.gz", ".zip", ".whl", ".tar", ".egg")):
        return False

    # exclude urls containing non ascii characters
    if not url.isascii():
        return False

    # add scheme if missing scheme to use validators
    if "//" not in url:
        url = "https://" + url
    if not validators.url(url):
        return False

    u = urlparse(url)
    if u.scheme not in ["http", "https"]:
        return False

    # if regex can not extract from the url, the url may have some problems, just skip it
    if any(
        [
            netloc in u.netloc
            for netloc in [
                "github.com",
                "bitbucket.org",
                "gitlab.com",
                "pypi.org",
                "pypi.python.org",
            ]
        ]
    ):
        return False

    return True


def github_repo_redirection(
    url: str, session: Optional[requests.Session] = None, token: str = None
) -> Optional[str]:
    forge, name, repo = url.split("/")[-3:]
    if forge != "github.com":
        logger.error(f"{url} is not a GitHub repository")
        return
    session = session or _configure_session()
    # session.proxies = None
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})

    while True:
        query_url = f"https://api.github.com/repos/{name}/{repo}"
        response = session.get(query_url, timeout=10)
        rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
        cur_ts = int(time.time())
        if (rate_limit_remaining == 0) and (cur_ts < rate_limit_reset):
            sleep_time = rate_limit_reset - cur_ts + 1
            time.sleep(sleep_time)
            logger.info(f"sleep {sleep_time}s...")
            continue

        if response.status_code in [403, 404, 451]:
            return
        return normalize_url(response.json().get("html_url"))


def url_redirection(
    url, session: Optional[requests.session] = None, token: str = None
) -> Optional[str]:
    session = session or _configure_session()

    forge = url.split("/")[2]
    if forge == "github.com":
        return github_repo_redirection(url, session, token)
    else:
        r = session.get(url, timeout=10)
        if r.status_code in [403, 404]:
            return
        return normalize_url(r.url)


class MetadataRetriever:
    @staticmethod
    def parse_metadata(
        metadata: dict[str, Optional[str | dict[str, str]]],
        webpage: bool = False,
        session: Optional[requests.session] = None,
        redirect: bool = False,
        token: Optional[str] = None,
    ) -> Optional[str]:
        if not metadata:
            return None
        name = metadata.get("name")
        home_page = metadata.get("home_page")
        download_url = metadata.get("download_url")
        project_urls = metadata.get("project_urls")
        description = metadata.get("description")

        url = MetadataRetriever.search_fields(home_page, download_url, project_urls)
        if url:
            if redirect:
                try:
                    url = url_redirection(url, session, token)
                except:
                    pass
            return url

        url = MetadataRetriever.search_description(name, description)
        if url:
            if redirect:
                try:
                    url = url_redirection(url, session, token)
                except:
                    pass
            return url

        if webpage:
            webpage_urls = MetadataRetriever.select_homepage_doc_url(project_urls)
            url = MetadataRetriever.search_webpage(name, webpage_urls, session=session)
            if url:
                if redirect:
                    try:
                        url = url_redirection(url, session, token)
                    except:
                        pass
                return url

    @staticmethod
    def search_fields(
        home_page: str,
        download_url: str,
        project_urls: Optional[dict[str, str]],
    ) -> Optional[str]:
        urls = find_repo_from_field(home_page)
        if urls:
            return urls[0]

        urls = find_repo_from_field(download_url)
        if urls:
            return urls[0]

        if not project_urls:
            return
        for k, v in project_urls.items():
            if any(
                [keyword in k.lower() for keyword in ["source", "code", "repository"]]
            ):
                urls = find_repo_from_field(v)
                if urls:
                    return urls[0]

        for v in project_urls.values():
            urls = find_repo_from_field(v)
            if urls:
                return urls[0]

    @staticmethod
    def search_description(name, description: str) -> Optional[str]:
        urls = find_repo_from_field(description)
        if urls:
            for url in urls:
                repo = url.rsplit("/", 1)[-1]
                sub_name = sub_pattern.sub("", name)
                sub_repo = sub_pattern.sub("", repo)
                if (sub_name in sub_repo) or (sub_repo in sub_name):
                    return url

    @staticmethod
    def select_homepage_doc_url(project_urls: Optional[dict[str, str]]):
        if not project_urls:
            return []
        res = []

        # search Homepage
        for key, value in project_urls.items():
            if key.lower().replace("-", "").replace("_", "") == "homepage":
                if validate_url(value):
                    res.append(normalize_url(value))
                    break

        # search doc
        for key, value in project_urls.items():
            if key.lower().startswith("doc") and validate_url(value):
                res.append(normalize_url(value))
                break

        return list(set(res))

    @staticmethod
    def search_webpage(
        name: str,
        webpage_urls: list[str],
        session: Optional[requests.Session] = None,
    ) -> Optional[str]:
        for webpage_url in webpage_urls:
            urls = find_repo_from_webpage(webpage_url, session)
            for url in urls:
                repo = url.rsplit("/", 1)[-1]
                sub_name = sub_pattern.sub("", name)
                sub_repo = sub_pattern.sub("", repo)
                if (sub_name in sub_repo) or (sub_repo in sub_name):
                    return url


def chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(webpage_urls: list[str], i: int):
    session = _configure_session()
    res = {}
    for webpage_url in webpage_urls:
        res[webpage_url] = find_repo_from_webpage(webpage_url, session)
        time.sleep(random.randint(5, 10))

    with open(f"data/webpage_repos-{i}.json", "w") as f:
        json.dump(res, f)


def post_process_log(n_jobs: int, chunk_size: int):
    if not os.path.exists("data/webpage_repos.json"):
        print("data/webpage_repos.json not exists, please run --left_release first")
        return

    if not os.path.exists("log/metadata_retriever.log"):
        print("log/metadata_retriever.log not exists!")
        return

    left_urls = []
    with open("log/metadata_retriever.log") as f:
        for line in f:
            try:
                url, err_info = line.strip("\n").split(": ", 1)
                if err_info.startswith("Http Error, 404 Client Error"):
                    continue
                left_urls.append(url)
            except:
                pass

    chunk = chunks(left_urls, chunk_size)
    num_chunk = math.ceil(len(left_urls) / chunk_size)
    print(
        f"{len(left_urls)} urls to be precessed, {n_jobs} processes, {chunk_size} urls perl batch, {num_chunk} batches"
    )

    Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(main)(urls, i) for i, urls in enumerate(chunk)
    )

    res = json.load(open("data/webpage_repos.json"))
    for i in range(num_chunk):
        for k, v in json.load(open(f"data/webpage_repos-{i}.json")).items():
            res[k] = v
        os.remove(f"data/webpage_repos-{i}.json")
    with open("data/webpage_repos.json", "w") as f:
        json.dump(res, f)


def run_search_webpage(n_jobs: int, chunk_size: int):
    if not os.path.exists("data/metadata_retriever.csv"):
        print("data/metadata_retriever.csv not exists, please run --all first")

    if os.path.exists("data/left_release_webpages.json"):
        data = json.load(open("data/left_release_webpages.json"))
    else:
        df = pd.read_csv("data/metadata_retriever.csv", low_memory=False)
        left_df = df[df["metadata_retriever"].isna()].copy()

        left_df.loc[:, "urls"] = left_df[["name", "version"]].progress_apply(
            lambda x: MetadataRetriever.select_homepage_doc_url(
                release_metadata.find_one(
                    {"name": x["name"], "version": x["version"]}
                ).get("project_urls")
            ),
            axis=1,
        )
        data = left_df[["name", "version", "urls"]].to_dict("records")
        with open("data/left_release_webpages.json", "w") as outf:
            json.dump(data, outf)

    print(f"{len(data)} releases do not have repository urls in the metadata")

    res = {}
    unique_urls = []
    for info in data:
        unique_urls.extend(info["urls"])
    unique_urls = list(set(unique_urls))
    if os.path.exists("data/webpage_repos.json"):
        res = json.load(open("data/webpage_repos.json"))
    left_urls = list(set(unique_urls) - set(res.keys()))

    chunk = chunks(left_urls, chunk_size)
    num_chunk = math.ceil(len(left_urls) / chunk_size)
    print(
        f"{len(left_urls)} urls to be searched, {n_jobs} processes, {chunk_size} urls perl batch, {num_chunk} batches"
    )

    Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(main)(urls, i) for i, urls in enumerate(chunk)
    )

    for i in range(num_chunk):
        for k, v in json.load(open(f"data/webpage_repos-{i}.json")).items():
            res[k] = v
        os.remove(f"data/webpage_repos-{i}.json")
    with open("data/webpage_repos.json", "w") as f:
        json.dump(res, f)


def merge():
    if not os.path.exists("data/webpage_repos.json"):
        print("data/webpage_repos.json not exists, please run --left_release first")
        return
    data = json.load(open("data/left_release_webpages.json"))
    webpage_repo_urls = json.load(open("data/webpage_repos.json"))

    res = []
    for release in data:
        name, version, urls = release["name"], release["version"], release["urls"]
        hit = False
        for url in urls:
            for repo_url in webpage_repo_urls.get(url, []):
                repo = repo_url.rsplit("/", 1)[-1]
                sub_name = sub_pattern.sub("", name)
                sub_repo = sub_pattern.sub("", repo)
                if (sub_name in sub_repo) or (sub_repo in sub_name):
                    hit = True
                    res.append([name, version, repo_url])
                    break
            if hit:
                break
        if not hit:
            res.append([name, version, None])
    res = pd.DataFrame(res, columns=["name", "version", "metadata_retriever"])
    df = pd.read_csv("data/metadata_retriever.csv", low_memory=False)
    pd.concat([df[df["metadata_retriever"].notna()], res]).drop_duplicates().to_csv(
        "data/metadata_retriever.csv", index=False
    )


def redirection_main(urls: list[str], token: str, i: int):
    res = {}
    session = _configure_session()
    for url in urls:
        try:
            res[url] = url_redirection(url, session, token)
        except Exception as e:
            logger.error(f"{url}, {e}")
        finally:
            time.sleep(random.randint(5, 10))

    with open(f"data/redirection-{i}.json", "w") as f:
        json.dump(res, f)


def github_redirect_main(urls: list[str], token: str, i: int):
    res = {}
    session = _configure_session()
    for url in urls:
        try:
            res[url] = github_repo_redirection(url, session, token)
        except Exception as e:
            logger.error(f"{url}, {e}")

    with open(f"data/gh_redirection-{i}.json", "w") as f:
        json.dump(res, f)


def redirection(n_jobs: int, chunk_size: int, tokens: list[str] = []):
    if len(tokens) == 0:
        print("Please supply github tokens.")
        return
    df = pd.read_csv(
        "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
    )
    unique_urls = list(
        df[df["metadata_retriever"] != ""]["metadata_retriever"].unique()
    )
    res = {}
    if os.path.exists("data/redirection.json"):
        res = json.load(open("data/redirection.json"))
    left_urls = list(set(unique_urls) - set(res.keys()))
    print(f"{len(unique_urls)} unique urls, {len(left_urls)} urls remains")

    github_urls = [url for url in left_urls if url.split("/")[2] == "github.com"]
    chunk = chunks(github_urls, 1000)
    num_chunk1 = math.ceil(len(github_urls) / 1000)
    print(
        f"{len(github_urls)} GitHub urls, {len(tokens)} GitHub tokens, 1000 urls per batch, {num_chunk1} batches"
    )
    Parallel(n_jobs=len(tokens), backend="multiprocessing")(
        delayed(github_redirect_main)(urls, tokens[i % len(tokens)], i)
        for i, urls in enumerate(chunk)
    )

    other_urls = [url for url in left_urls if url.split("/")[2] != "github.com"]
    chunk = chunks(other_urls, chunk_size)
    num_chunk = math.ceil(len(other_urls) / chunk_size)
    print(
        f"{len(other_urls)} Bitbucket and GitLab urls, {n_jobs} processes, {chunk_size} urls per batch, {num_chunk} batches"
    )

    Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(redirection_main)(urls, tokens[i % len(tokens)], i)
        for i, urls in enumerate(chunk)
    )

    for i in range(num_chunk1):
        for k, v in json.load(open(f"data/gh_redirection-{i}.json")).items():
            res[k] = v
        os.remove(f"data/gh_redirection-{i}.json")

    for i in range(num_chunk):
        for k, v in json.load(open(f"data/redirection-{i}.json")).items():
            res[k] = v
        os.remove(f"data/redirection-{i}.json")
    with open("data/redirection.json", "w") as f:
        json.dump(res, f)

    df["redirected"] = df["metadata_retriever"].map(res)
    df.to_csv("data/metadata_retriever.csv", index=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--single", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument("--all", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument(
        "--webpage", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--left_release", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--redirect", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--process_log", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument("--merge", default=False, action=argparse.BooleanOptionalAction)
    parser.add_argument("--name", type=str)
    parser.add_argument("--version", type=str)
    parser.add_argument("--n_jobs", type=int, default=1)
    parser.add_argument("--chunk_size", type=int, default=100)
    parser.add_argument("--token_file", type=str)
    args = parser.parse_args()

    if args.single:
        metadata = release_metadata.find_one(
            {"name": args.name, "version": args.version},
            {
                "_id": 0,
                "name": 1,
                "version": 1,
                "home_page": 1,
                "download_url": 1,
                "project_urls": 1,
                "description": 1,
            },
        )
        print(MetadataRetriever.parse_metadata(metadata, webpage=args.webpage))

    elif args.all:
        with open("data/metadata_retriever.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "version", "metadata_retriever"])
            for metadata in tqdm(
                release_metadata.find(
                    {},
                    {
                        "_id": 0,
                        "name": 1,
                        "version": 1,
                        "home_page": 1,
                        "download_url": 1,
                        "project_urls": 1,
                        "description": 1,
                    },
                )
            ):
                name = metadata["name"]
                version = metadata["version"]
                repo_url = MetadataRetriever.parse_metadata(metadata)
                writer.writerow([name, version, repo_url])

    elif args.left_release:
        run_search_webpage(args.n_jobs, args.chunk_size)

    elif args.process_log:
        post_process_log(args.n_jobs, args.chunk_size)

    elif args.merge:
        merge()

    elif args.redirect:
        tokens = json.load(open(args.token_file))
        redirection(args.n_jobs, args.chunk_size, tokens)
