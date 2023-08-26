import argparse
import json
import logging
import math
import os

import pandas as pd
from joblib import Parallel, delayed
from pymongo import MongoClient
from tqdm import tqdm

from pyradar.validator import Validator, download

logger = logging.getLogger(__name__)


def chunks(data, n: int):
    for i in range(0, len(data), n):
        yield data[i : i + n]


def get_phantom_file(data: pd.DataFrame, i: int, base_folder: str, prefix: str):
    res = {}
    for row in data.itertuples(index=False):
        name = row.name
        version = row.version
        url = row.url
        try:
            v = Validator(name, version, url, base_folder)
            tmp = {}
            tmp["version"] = version
            tmp["url"] = url
            tmp["phantom_file"] = v.phantom_files
            res[name] = tmp
        except Exception as e:
            logger.error(f"{name}, {version}, {url}, {e}")

    with open(f"data/{prefix}-{i}.json", "w") as outf:
        json.dump(res, outf)


def feature_main(name: str, version: str, url: str):
    v = Validator(name, version, url, "/data/kyle/pypi_data")
    return [name, version, url] + v.features()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_folder", type=str, required=True)
    parser.add_argument("--n_jobs", default=1, type=int)
    parser.add_argument("--chunk_size", default=100, type=int)
    parser.add_argument("--mirror", default=None, type=str)
    parser.add_argument(
        "--features", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        "--phantom_file", default=False, action=argparse.BooleanOptionalAction
    )
    parser.add_argument("--pypi", default=False, action=argparse.BooleanOptionalAction)

    args = parser.parse_args()

    positive_df = pd.read_csv("data/positive_dataset.csv")
    negative_df = pd.read_csv("data/negative_dataset.csv")

    if args.phantom_file:
        positive_prefix = "positive_phantom_files"
        Parallel(n_jobs=args.n_jobs, backend="multiprocessing")(
            delayed(get_phantom_file)(data, i, args.base_folder, positive_prefix)
            for i, data in enumerate(chunks(positive_df, args.chunk_size))
        )
        positive_res = {}
        for i in range(math.ceil(len(positive_df) / args.chunk_size)):
            path = f"data/{positive_prefix}-{i}.json"
            for k, v in json.load(open(path)).items():
                positive_res[k] = v
            os.remove(path)

        with open(f"data/{positive_prefix}.json", "w") as outf:
            json.dump(positive_res, outf)

        negative_prefix = "negative_phantom_files"
        Parallel(n_jobs=args.n_jobs, backend="multiprocessing")(
            delayed(get_phantom_file)(data, i, args.base_folder, negative_prefix)
            for i, data in enumerate(chunks(negative_df, args.chunk_size))
        )
        negative_res = {}
        for i in range(math.ceil(len(negative_df) / args.chunk_size)):
            path = f"data/{negative_prefix}-{i}.json"
            for k, v in json.load(open(path)).items():
                negative_res[k] = v
            os.remove(path)

        with open(f"data/{negative_prefix}.json", "w") as outf:
            json.dump(negative_res, outf)

    if args.features:
        positive_data = Parallel(n_jobs=args.n_jobs, backend="multiprocessing")(
            delayed(feature_main)(name, version, url)
            for name, version, url in tqdm(
                positive_df[["name", "version", "url"]].itertuples(index=False),
                total=len(positive_df),
            )
        )
        columns = [
            "name",
            "version",
            "repo_url",
            "num_phantom_pyfiles",
            "setup_change",
            "num_downloads",
            "tag_match",
            "num_maintainers",
            "num_maintainer_pkgs",
            "maintainer_max_downloads",
        ]
        positive_data = pd.DataFrame(positive_data, columns=columns)
        positive_data["label"] = 0

        negative_data = Parallel(n_jobs=args.n_jobs, backend="multiprocessing")(
            delayed(feature_main)(name, version, url)
            for name, version, url in tqdm(
                negative_df[["name", "version", "url"]].itertuples(index=False),
                total=len(negative_df),
            )
        )
        negative_data = pd.DataFrame(negative_data, columns=columns)
        negative_data["label"] = 1

        df = pd.concat([positive_data, negative_data]).sample(frac=1)

        df.to_csv("data/validator_dataset.csv", index=False)

    if args.pypi:
        dist_file_info_col = MongoClient("127.0.0.1", 27017)["radar"][
            "distribution_file_info"
        ]
        sdist_file_df = pd.DataFrame(
            dist_file_info_col.find(
                {"packagetype": "sdist"}, projection={"_id": 0, "packagetype": 0}
            )
        )
        sdist_file_df["upload_time"] = pd.to_datetime(sdist_file_df["upload_time"])
        retriver_df = pd.read_csv(
            "data/metadata_retriever.csv", low_memory=False, keep_default_na=False
        )
        release_with_repo = retriver_df[retriver_df["redirected"] != ""]

        latest_releases = (
            sdist_file_df.merge(release_with_repo[["name", "version", "redirected"]])
            .sort_values("upload_time", ascending=False)
            .drop_duplicates(["name"])
        )
        if args.mirror:
            latest_releases["url"] = latest_releases["url"].apply(
                lambda x: x.replace(
                    "https://files.pythonhosted.org",
                    args.mirror,
                )
            )

        print(f"{len(latest_releases)} releases")

        data = latest_releases[["name", "filename", "url"]].to_dict("records")
        print(args.n_jobs)

        for d in tqdm(data):
            name, filename, url = d["name"], d["filename"], d["url"]
            save_path = os.path.join(args.base_folder, "distribution", name, filename)
            download(url, save_path)
