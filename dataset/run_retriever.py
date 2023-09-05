import argparse
import json
import logging
import os

import pandas as pd
from joblib import Parallel, delayed
from tqdm import tqdm

from pyradar.utils import DistReader

logger = logging.getLogger(__name__)


def get_fileshas(name: str, filename: str, base_folder: str):
    path = os.path.join(base_folder, "distribution", name, filename)
    dr = DistReader(path)
    return dr.file_shas()


def cal_dist_fileshas(n_jobs: int, base_folder: str):
    df = pd.read_csv("data/retriever_dataset.csv")
    print(len(df))
    df = df[df["filename"].str.endswith((".zip", ".whl", ".tar.gz", ".egg"))]
    print(len(df), "left")

    res = []
    res = Parallel(n_jobs=n_jobs, backend="multiprocessing")(
        delayed(get_fileshas)(name, filename, base_folder)
        for name, filename in tqdm(df[["name", "filename"]].values)
    )
    fileshas = {}
    for i, name in enumerate(df["name"]):
        fileshas[name] = res[i]
    with open("data/retriever_fileshas.json", "w") as outf:
        json.dump(fileshas, outf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_folder", type=str, required=True)
    parser.add_argument("--n_jobs", default=1, type=int)
    parser.add_argument(
        "--fileshas", default=False, action=argparse.BooleanOptionalAction
    )
    args = parser.parse_args()

    if args.fileshas:
        cal_dist_fileshas(args.n_jobs, args.base_folder)
