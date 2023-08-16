import configparser
import csv
import json
import logging
from typing import Generator, Iterable, Optional, TypeVar

import requests
import urllib3
from lxml import etree
from tqdm import tqdm

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config = configparser.ConfigParser()
config.read("config.ini")
proxies = None
if "proxies" in config:
    if "http" in config["proxies"] and "https" in config["proxies"]:
        proxies = {
            "http": config["proxies"]["http"],
            "https": config["proxies"]["https"],
        }
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Connection": "close",
}


def data_preparation():
    from pymongo import MongoClient

    col = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]
    names = col.find({}, {"_id": 0, "name": 1}).distinct("name")
    with open("data/package_names.json", "w") as outf:
        json.dump(names, outf)


def configure_logger(name: str, log_file: str, level: int):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    fh = logging.FileHandler(log_file, "w")
    fh.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


def safe_get(url: str, session=None, logger=None) -> Optional[requests.Response]:
    """A robust wrapper of `requests.get` to handle exceptions. Code adapted from https://stackoverflow.com/a/47007419"""
    response = None
    if not session:
        session = requests.Session()
    try:
        response = session.get(url, timeout=60)
        response.raise_for_status()
    except requests.exceptions.HTTPError as errh:
        logger.error(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        logger.error(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        logger.error(f"Timeout Error: {errt}")
    except Exception as err:
        logger.error(f"OOps, Something Else: {err}")
    finally:
        return response


def get_maintainers(name: str, session=None, logger=None) -> Optional[list[str]]:
    response = safe_get(f"https://pypi.org/project/{name}", session, logger)
    if not response:
        return []

    html = etree.HTML(response.text)

    return [
        _.strip("\n ")
        for _ in html.xpath(
            '(//div[contains(./h3, "Maintainers")])[1]//span[@class="sidebar-section__user-gravatar-text"]/text()'
        )
    ]


def main(names: list[str], i: int, session=None, logger=None, disable_pbar=True):
    logger = configure_logger(f"py2src-{i}", f"log/py2src-{i}.log", logging.DEBUG)
    session = requests.Session()
    session.headers.update(headers)
    session.verify = False
    session.proxies = proxies

    with open(f"data/maintainers-{i}.json", "w") as outf:
        writer = csv.writer(outf)
        for name in tqdm(names, disable=disable_pbar):
            maintainers = get_maintainers(name, session, logger)
            writer.writerow([name] + maintainers)
            outf.flush()


T = TypeVar("T")


def chunks(lst: Iterable[T], n: int) -> Generator[list[T], None, None]:
    lst = lst[::-1]
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


if __name__ == "__main__":
    names = json.load(open("data/package_names.json"))

    main(names[:100], 0, disable_pbar=False)
