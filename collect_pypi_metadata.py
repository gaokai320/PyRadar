import argparse
import math
import os
import sys
import time

from pypi_crawler import Package, PyPI

parser = argparse.ArgumentParser()
parser.add_argument(
    "--folder", type=str, required=True, help="the folder to store PyPI data"
)
parser.add_argument(
    "--thread", type=int, required=True, help="the thread id for run this script"
)
args = parser.parse_args()

data_folder = args.folder
thread_id = args.thread

thread_num = min(os.cpu_count() / 2, 40)
assert thread_id < thread_num, f"Thread id should be less than {thread_num}!"

def process(name: str):
    print(f"[INFO]: Start processing {name}", file=sys.stderr)
    p = Package(name=name, data_folder=os.path.join(data_folder, "metadata"))
    vs = p.get_versions(update=False, dump=True)
    for v in vs:
        p.query_single_release(version=v, dump=True)
    print(f"[INFO]: Finish processing {name}", file=sys.stderr)
    time.sleep(2)


pypi = PyPI(data_folder=data_folder)
pkgs = pypi.list_all_packages(api="xmlrpc", update=False, dump=True)
print(f"[INFO]: {len(pkgs)} packages on PyPI in total!", file=sys.stderr)


segment = math.ceil(len(pkgs) / thread_num)

for p in pkgs[segment * thread_id : segment * (thread_id + 1)]:
    process(p)
