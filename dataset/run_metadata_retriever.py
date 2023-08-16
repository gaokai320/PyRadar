import argparse
import configparser
import csv
import json
import logging
import math
import os
import random
import re
import time

import pandas as pd
from joblib import Parallel, delayed
from pymongo import MongoClient
from tqdm import tqdm

from pyradar.metadata_retriever import (
    MetadataRetriever,
    _configure_session,
    find_repo_from_webpage,
    github_repo_redirection,
    url_redirection,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

db = MongoClient("127.0.0.1", 27017)["radar"]
release_metadata = db["release_metadata"]
tqdm.pandas()

sub_pattern = re.compile(r"[^a-zA-Z0-9]")

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


def chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(webpage_urls: list[str], i: int):
    session = _configure_session()
    session.proxies = proxies
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
        df = pd.read_csv(
            "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
        )
        left_df = df[df["metadata_retriever"] != ""].copy()

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
    df = pd.read_csv(
        "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
    )
    pd.concat([df[df["metadata_retriever"].notna()], res]).drop_duplicates().to_csv(
        "data/metadata_retriever.csv", index=False
    )


def redirection_main(urls: list[str], token: str, i: int):
    res = {}
    session = _configure_session()
    session.proxies = proxies
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
    session.proxies = proxies
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
    parser = argparse.ArgumentParser()
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
    args = parser.parse_args()

    if args.name:
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
        print(
            MetadataRetriever.parse_metadata(
                metadata, webpage=args.webpage, redirect=args.redirect
            )
        )

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
                repo_url = MetadataRetriever.parse_metadata(
                    metadata, webpage=args.webpage, redirect=args.redirect
                )
                writer.writerow([name, version, repo_url])

    elif args.left_release:
        run_search_webpage(args.n_jobs, args.chunk_size)

    elif args.process_log:
        post_process_log(args.n_jobs, args.chunk_size)

    elif args.merge:
        merge()

    elif args.redirect:
        redirection(args.n_jobs, args.chunk_size, tokens)
