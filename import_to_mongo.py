import json
import os
import sys

import pymongo
from packaging.utils import canonicalize_name
from pymongo import MongoClient
from pymongo.write_concern import WriteConcern
from tqdm import tqdm

db = MongoClient("127.0.0.1", 27017)["radar"]
col = db["release_metadata"]

metadata_folder = os.path.join(sys.argv[1], "metadata")
packages = list(os.listdir(metadata_folder))

info_keys = [
    "name",
    "version",
    "summary",
    "keywords",
    "license",
    "author",
    "author_email",
    "maintainer",
    "maintainer_email",
    "home_page",
    "download_url",
    "project_urls",
    "requires_dist",
    "classifiers",
    "description",
    "description_content_type",
    "bugtrack_url",
    "docs_url",
    "downloads",
    "package_url",
    "platform",
    "project_url",
    "release_url",
    "requires_python",
    "yanked",
    "yanked_reason",
]

batch = []
for pkg in tqdm(packages):
    for version in os.listdir(os.path.join(metadata_folder, pkg)):
        if version == f"{pkg}.json":
            continue
        try:
            metadata = json.load(open(os.path.join(metadata_folder, pkg, version)))
            info_data = metadata["info"]
            data = {}
            for key in info_keys:
                data[key] = info_data.get(key, None)
            if len(metadata["urls"]) > 0:
                data["upload_time"] = metadata["urls"][0]["upload_time"]
            data["name"] = canonicalize_name(data["name"])
            batch.append(data)
        except Exception as e:
            print(f"{pkg} {version}: error! {e}")
        if len(batch) % 40000 == 0:
            try:
                col.with_options(write_concern=WriteConcern(w=0)).insert_many(
                    batch, ordered=False
                )
            except pymongo.errors.BulkWriteError as e:
                pass
if len(batch) > 0:
    col.with_options(write_concern=WriteConcern(w=0)).insert_many(batch, ordered=False)

col.create_index([("name", pymongo.ASCENDING)])
col.create_index([("name", pymongo.ASCENDING), ("version", pymongo.ASCENDING)])
