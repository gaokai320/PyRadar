import argparse

from pymongo import MongoClient
from tqdm import tqdm

from baselines.ossgadget import OSSGadget
from baselines.warehouse import Warehouse

release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]


def run_OSSGadget(output):
    with open(output, "w") as f:
        for metadata in tqdm(
            release_metadata.find(
                {},
                projection={
                    "_id": 0,
                    "name": 1,
                    "version": 1,
                    "home_page": 1,
                    "download_url": 1,
                    "project_urls": 1,
                },
            )
        ):
            try:
                name = metadata["name"]
                version = metadata["version"]
                repo_url = OSSGadget.parse_metadata(metadata)
                if repo_url:
                    f.write(f"{name},{version},{repo_url}\n")
                else:
                    f.write(f"{name},{version},\n")
            except Exception as e:
                print(name, version, e.with_traceback())
                break


def run_Warehouse(output):
    with open(output, "w") as f:
        for metadata in tqdm(
            release_metadata.find(
                {},
                projection={
                    "_id": 0,
                    "name": 1,
                    "version": 1,
                    "home_page": 1,
                    "download_url": 1,
                    "project_urls": 1,
                },
            )
        ):
            try:
                name = metadata["name"]
                version = metadata["version"]
                repo_url = Warehouse.parse_metadata(metadata)
                if repo_url:
                    f.write(f"{name},{version},{repo_url}\n")
                else:
                    f.write(f"{name},{version},\n")
            except Exception as e:
                print(name, version, e.with_traceback())
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=str)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    if args.baseline.lower() == "ossgadget":
        run_OSSGadget(args.output)
    elif args.baseline.lower() == "warehouse":
        run_Warehouse(args.output)


if __name__ == "__main__":
    main()
