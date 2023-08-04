import csv
import logging
import os
from collections import Counter
from email.message import EmailMessage
from functools import lru_cache
from typing import Generator, Optional, TypeVar
from urllib.parse import urlparse

import readme_renderer.markdown
import readme_renderer.rst
import readme_renderer.txt
import requests
import urllib3
import validators
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pyparsing import Iterable
from tqdm import tqdm
from urllib3.util import Retry

from baselines.ossgadget import OSSGadget
from baselines.utils import configure_logger
from baselines.warehouse import Warehouse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# logger = configure_logger("py2src", "log/py2src.log", logging.DEBUG)
release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]

_RENDERERS = {
    None: readme_renderer.rst,  # Default if description_content_type is None
    "": readme_renderer.rst,  # Default if description_content_type is None
    "text/plain": readme_renderer.txt,
    "text/x-rst": readme_renderer.rst,
    "text/markdown": readme_renderer.markdown,
}


def render(value, content_type=None, use_fallback=True):
    """Code copyed from `warehouse/utils/readme.py` in [pypi/warehouse](https://github.com/pypi/warehouse/blob/main/warehouse/utils/readme.py)"""
    if value is None:
        return value

    # Necessary because `msg.get_content_type()` returns `test/plain` for
    # invalid or missing input, per RFC 2045, which changes our behavior.
    if content_type is not None:
        msg = EmailMessage()
        msg["content-type"] = content_type
        content_type = msg.get_content_type()

    # Get the appropriate renderer
    renderer = _RENDERERS.get(content_type, readme_renderer.txt)

    # Actually render the given value, this will not only render the value, but
    # also ensure that it's had any disallowed markup removed.
    rendered = renderer.render(value)

    # Wrap plaintext as preformatted to preserve whitespace.
    if content_type == "text/plain":
        rendered = f"<pre>{rendered}</pre>"

    # If the content was not rendered, we'll render as plaintext instead. The
    # reason it's necessary to do this instead of just accepting plaintext is
    # that readme_renderer will deal with sanitizing the content.
    # Skip the fallback option when validating that rendered output is ok.
    if use_fallback and rendered is None:
        rendered = readme_renderer.txt.render(value)

    return rendered


class Py2Src:
    @staticmethod
    def parse_metadata(
        metadata: dict[str, Optional[str | dict[str, str]]], session=None, logger=None
    ) -> list[str]:
        """Code adapted from `get_final_url` method in [GetFinalURL](https://github.com/simonepirocca/py2src/blob/master/src/get_github_url.py#L10) class."""
        ossgadget_url = URLFinder.find_ossgadget_url(metadata, session, logger)
        badge_url = URLFinder.find_github_url_from_pypi_badge(metadata, session, logger)
        homepage_url = URLFinder.mode_2(metadata, session, logger)
        metadata_url = URLFinder.mode_1(metadata, session, logger)
        readthedocs_url = URLFinder.find_github_url_from_readthedocs(
            metadata, session, logger
        )
        statistics_url = URLFinder.find_github_url_from_pypi_statistics(metadata)

        return [
            ossgadget_url,
            badge_url,
            homepage_url,
            metadata_url,
            readthedocs_url,
            statistics_url,
        ]


@lru_cache(maxsize=1024)
def safe_get(url: str, session=None, logger=None) -> Optional[requests.Response]:
    """A robust wrapper of `requests.get` to handle exceptions. Code adapted from https://stackoverflow.com/a/47007419"""
    response = None
    if not session:
        session = requests.Session()
    if not logger:
        logger = configure_logger("py2src", "log/py2src.log", logging.DEBUG)
    try:
        response = session.get(url)
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


class URLFinder:
    @staticmethod
    def real_github_url(url: str, session=None, logger=None) -> Optional[str]:
        """combination of `test_url_working`, `normalize_url`, and `real_github_url` methods in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py) to avoid redundant requests."""

        # adapted from [`normalize_url`](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L533).
        # only not None urls are passed to this mthods, we did not check if the url is None or empty.
        url = url.strip("/")
        url = "https://github.com" + urlparse(url).path.replace(".git", "").lower()

        # `test_url_working` overlaps with `real_github_url`, so I combine them.
        response = safe_get(url, session, logger)
        if (
            response
            and response.status_code == 200
            and urlparse(url).path.count("/") == 2
        ):
            real_url = response.url
            return real_url.strip("/")

    @staticmethod
    def find_ossgadget_url(
        metadata: dict[str, Optional[str | dict[str, str]]], session=None, logger=None
    ) -> Optional[str]:
        """reimplementation of `find_ossgadget_url` method in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L347). Note that we have reimplemented OSSGadget `oss-find-source`, so we just call the reimplementation."""
        url = OSSGadget.parse_metadata(metadata)
        if url:
            return URLFinder.real_github_url(url, session, logger)
        return None

    @staticmethod
    def render_readme(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        description = metadata.get("description")
        if description:
            # Here I simulate the render process as described in the `file_upload` method in [pypi/warehouse](https://github.com/pypi/warehouse/blob/main/warehouse/forklift/legacy.py#L1033)
            description_content_type = metadata.get("description_content_type")
            if not description_content_type:
                description_content_type = "text/x-rst"
            rendered = render(description, description_content_type, use_fallback=False)
            return rendered
        return None

    @staticmethod
    def find_github_url_from_pypi_badge(
        metadata: dict[str, Optional[str | dict[str, str]]], session=None, logger=None
    ) -> Optional[str]:
        """Code adapted from `find_github_url_from_pypi_badge` in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L462). Check if PyPI page have a GitHub badge linked to a GitHub URL. Instead of parsing the description part in the PyPI page, I use the `description` field in the package's distribution metadata, which are the same."""
        urls = []
        rendered = URLFinder.render_readme(metadata)
        if rendered:
            soup = BeautifulSoup(rendered, "html.parser")
            for badge in soup.findAll("a"):
                if len(badge.findAll("img")) > 0:
                    tmp_badge_url = badge.get("href")
                    # It cares about both GitHub and Travis badges
                    if tmp_badge_url and (
                        "github.com" in tmp_badge_url
                        or "travis-ci.org" in tmp_badge_url
                    ):
                        tmp_badge_url.rstrip("/")
                        badge_url_parts = urlparse(tmp_badge_url)
                        if (
                            metadata["name"].lower() != "black"
                            and "psf/black" in badge_url_parts.path
                        ):
                            continue
                        if badge_url_parts.path.count("/") >= 2:
                            badge_url_path_parts = badge_url_parts.path.split("/")
                            badge_url = (
                                "https://github.com/"
                                + badge_url_path_parts[1]
                                + "/"
                                + badge_url_path_parts[2]
                            )
                            badge_url = URLFinder.real_github_url(
                                badge_url, session, logger
                            )
                            if badge_url:
                                badge_url = badge_url.rstrip("/")
                                urls.append(badge_url)
        return Counter(urls).most_common(1)[0][0] if urls else None

    @staticmethod
    def is_valid_github_url(url: str) -> bool:
        """Code copyed from `is_valid_github_url` method in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L83)
        Determine if a url is a valid url in which it has a valid host and repository name
        :return: True - if url is valid otherwhise False
        """
        url_obj = urlparse(url)
        if "github.com" in url_obj.netloc:  # checking url domain
            if url_obj.path.count("/") in [
                2,
                3,
            ]:  # checking if it has valid repository name
                return True
        return False

    @staticmethod
    def get_homepage(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        """reimplementation of `get_homepage` method in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L161)"""
        if metadata and metadata.get("project_urls"):
            homepage_url = metadata.get("project_urls").get("Homepage")
            if homepage_url:
                return homepage_url.rstrip("/")
        return None

    @staticmethod
    def get_codepage(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        """reimplementation of `get_codepage` method in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L183)"""
        if metadata and metadata.get("project_urls"):
            codepage_url = next(
                (
                    value
                    for key, value in metadata.get("project_urls").items()
                    if "code" in key.lower()
                ),
                None,
            )
            if codepage_url:
                return codepage_url.rstrip("/")

        return None

    @staticmethod
    def find_github_url_metadata(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        """reimplementation of `find_github_url_metadata` method in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L235)"""
        if metadata and metadata.get("project_urls"):
            homepage_url = URLFinder.get_homepage(metadata)
            if homepage_url and URLFinder.is_valid_github_url(homepage_url):
                return homepage_url

            codepage_url = URLFinder.get_codepage(metadata)
            if codepage_url and URLFinder.is_valid_github_url(codepage_url):
                return codepage_url
        return None

    @staticmethod
    def mode_1(
        metadata: dict[str, Optional[str | dict[str, str]]], session=None, logger=None
    ) -> Optional[str]:
        github_url_metadata = URLFinder.find_github_url_metadata(metadata)
        if github_url_metadata:
            return URLFinder.real_github_url(github_url_metadata, session, logger)
        return None

    @staticmethod
    def scrape_source_name_from_webpage(
        name: str, url: Optional[str], session=None, logger=None
    ) -> Optional[str]:
        """reimplementation of `scrape_source_name_from_webpage` method in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L97)"""
        if not url:
            return None
        if not validators.url(url):
            return None

        package_in_github_urls = []
        response = safe_get(url, session, logger)
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.findAll("a"):
                href_url = link.get("href")
                if href_url:
                    url_parts = urlparse(href_url)
                    if url_parts.netloc in ["github.com"]:
                        regex = "[^a-zA-Z0-9]"
                        if name.replace(regex, "") in url_parts.path.replace(regex, ""):
                            package_in_github_urls.append(href_url)
        common_url = os.path.commonprefix(package_in_github_urls)
        if common_url:
            common_url = common_url.strip("/")
            common_url = "https://github.com" + "/".join(
                urlparse(common_url).path.split("/")[:3]
            )
            return common_url

        return None

    @staticmethod
    def mode_2(
        metadata: dict[str, Optional[str | dict[str, str]]], session=None, logger=None
    ) -> Optional[str]:
        if metadata and metadata.get("project_urls"):
            homepage_url = URLFinder.get_homepage(metadata)
            github_url_homepage = URLFinder.scrape_source_name_from_webpage(
                metadata.get("name"), homepage_url
            )
            if github_url_homepage:
                return URLFinder.real_github_url(github_url_homepage, session, logger)
        return None

    @staticmethod
    def find_github_url_from_readthedocs(
        metadata: dict[str, Optional[str | dict[str, str]]], session=None, logger=None
    ) -> Optional[str]:
        if not metadata:
            return None
        rendered = URLFinder.render_readme(metadata)
        links = []
        if metadata.get("project_urls"):
            for value in metadata.get("project_urls").values():
                if "readthedocs.io" in value:
                    links.append(value)
        if rendered:
            soup = BeautifulSoup(rendered, "html.parser")
            for link in soup.findAll("a"):
                href_url = link.get("href", "").replace(" ", "")
                if "readthedocs.io" in href_url:
                    links.append(href_url)
        link_url = Counter(links).most_common(1)[0][0] if links else None

        urls = []
        if link_url:
            response = safe_get(link_url, session, logger)
            if response and response.status_code == 200:
                docs_soup = BeautifulSoup(response.text, "html.parser")
                for link in docs_soup.findAll("a"):
                    tmp_url = link.get("href", "")
                    tmp_url_parts = urlparse(tmp_url)
                    if (
                        metadata.get("name") != "alabaster"
                        and "bitprophet/alabaster" in tmp_url_parts.path
                    ):
                        continue
                    if (
                        metadata.get("name") != "sphinx-rtd-theme"
                        and "readthedocs/sphinx_rtd_theme" in tmp_url_parts.path
                    ):
                        continue

                    if (
                        tmp_url_parts.netloc == "github.com"
                        and tmp_url_parts.path.count("/") >= 2
                    ):
                        tmp_url = tmp_url.rstrip("/")
                        tmp_url_path_parts = tmp_url_parts.path.split("/")
                        docs_github_url = (
                            "https://github.com/"
                            + tmp_url_path_parts[1]
                            + "/"
                            + tmp_url_path_parts[2]
                        )
                        docs_github_url = URLFinder.real_github_url(
                            docs_github_url, session, logger
                        )
                        if docs_github_url:
                            docs_github_url = docs_github_url.rstrip("/")
                            urls.append(docs_github_url)

        return Counter(urls).most_common(1)[0][0] if urls else None

    @staticmethod
    def find_github_url_from_pypi_statistics(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        """reimplementation of `find_github_url_from_pypi_statistics` method in [src/url_finder.py](https://github.com/simonepirocca/py2src/blob/master/src/url_finder.py#L369). Since the GitHub statistics section is based on the GitHub repository URL retrieved by warehouse. So I just call the reimplemented Warehouse class."""
        return Warehouse.parse_metadata(metadata)


T = TypeVar("T")


def chunks(lst: Iterable[T], n: int) -> Generator[list[T], None, None]:
    lst = lst[::-1]
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(names: list[str], i: int, token: str = None):
    logger = configure_logger(f"py2src-{i}", f"log/py2src-{i}.log", logging.DEBUG)
    with open(f"data/py2src-{i}.csv", "w") as f:
        pass

    # session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
        "Connection": "close",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    proxies = {
        "http": "http://162.105.88.97:7890",
        "https": "http://162.105.88.97:7890",
    }

    session = requests.Session()
    session.headers.update(headers)
    session.verify = False
    session.proxies = proxies
    with open(f"data/py2src-{i}.csv", "a") as f:
        writer = csv.writer(f)
        for name in tqdm(names):
            for metadata in release_metadata.find(
                {"name": name},
                projection={
                    "_id": 0,
                    "name": 1,
                    "version": 1,
                    "home_page": 1,
                    "download_url": 1,
                    "project_urls": 1,
                    "description": 1,
                    "description_content_type": 1,
                },
            ):
                name = metadata["name"]
                version = metadata["version"]
                logger.info(f"Start {name}, {version}")
                try:
                    proposed_urls = Py2Src.parse_metadata(metadata, session, logger)
                    tmp = [_ for _ in proposed_urls if _]
                    mode_url = Counter(tmp).most_common(1)[0][0] if tmp else None
                    line = [name, version]
                    line.extend(proposed_urls)
                    line.append(mode_url)
                    writer.writerow(line)
                    f.flush()
                except Exception as e:
                    logger.error(f"Exception: {name}, {version}, {e}")

                logger.info(f"Finish {name}, {version}")
    session.close()


def error_names():
    res = []
    prev = None
    for i in range(300):
        with open(f"log/py2src-{i}.log") as f:
            for line in f:
                msg = line.strip("\n").split(" - ")[-1]
                if msg.startswith("Start ") or msg.startswith("Exception "):
                    prev = msg.split(" ", 1)[1].split(", ")[0]
                elif msg.startswith("Http Error: "):
                    error_no = msg.split(" ")[2]
                    if error_no != "404":
                        res.append(prev)
                elif (
                    msg.startswith("Error Connecting: ")
                    or msg.startswith("Timeout Error: ")
                    or msg.startswith("OOps, Something Else: ")
                ):
                    res.append(prev)
    return list(set(res))


def unvisited():
    visited = []
    for i in range(0, 300):
        with open(f"data/py2src{i}.csv") as f:
            for line in f:
                name, version = line.split(",")[:2]
                visited.append((name, version))

    all_names = []
    for metadata in release_metadata.find({}, {"_id": 0, "name": 1, "version": 1}):
        name = metadata["name"]
        version = metadata["version"]
        all_names.append((name, version))

    tmp = set(all_names) - set(visited)
    return list(set([n for n, _ in tmp]))


if __name__ == "__main__":
    # from multiprocessing import Pool
    # p = Pool(20)
    from joblib import Parallel, delayed

    names = release_metadata.find({}).distinct("name")
    # names = list(set(unvisited() + error_names()))
    print(f"{len(names)} packages to be processed")
    chunk_lst = chunks(names, len(names) // 10 + 1)
    Parallel(n_jobs=10, backend="multiprocessing")(
        delayed(main)(task, i % 10) for i, task in enumerate(chunk_lst)
    )
