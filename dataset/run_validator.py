import argparse
import json
import logging
import math
import os

import pandas as pd
from joblib import Parallel, delayed

from pyradar.validator import Validator

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
            (
                tmp["total_files"],
                tmp["matched_files"],
                tmp["phantom_file"],
            ) = v.get_phantom_files()
            res[name] = tmp
        except Exception as e:
            logger.error(f"{name}, {version}, {url}, {e}")

    with open(f"data/{prefix}-{i}.json", "w") as outf:
        json.dump(res, outf)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_folder", type=str, required=True)
    parser.add_argument("--n_jobs", default=1, type=int)
    parser.add_argument("--chunk_size", default=100, type=int)
    parser.add_argument(
        "--phantom_file", default=False, action=argparse.BooleanOptionalAction
    )

    args = parser.parse_args()

    positive_df = pd.read_csv("data/positive_dataset_sample.csv")
    negative_df = pd.read_csv("data/negative_dataset_sample.csv")

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
