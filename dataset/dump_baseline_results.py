from functools import reduce

import pandas as pd
from pymongo import MongoClient

db = MongoClient("127.0.0.1", 27017)["radar"]
col = db["package_repository_url"]

ossgadget = pd.read_csv("data/OSSGadget.csv")
warehouse = pd.read_csv("data/Warehouse.csv")
librariesio = pd.read_csv("data/Libraries.io.csv")
py2src = pd.read_csv("data/Py2Src.csv", low_memory=False)

res = reduce(
    lambda left, right: pd.merge(left, right, on=["name", "version"]),
    [ossgadget, warehouse, librariesio, py2src],
)

col.insert_many(res.to_dict("records"))
col.create_index([("name", 1), ("version", 1)])
col.create_index([("name", 1)])
