import csv
import logging
from collections import OrderedDict
from typing import Optional
from urllib.parse import urlparse

from pymongo import MongoClient
from tqdm import tqdm

from baselines.utils import GITHUB_RESERVED_NAMES, configure_logger

logger = configure_logger("warehouse", "log/warehouse.log", logging.DEBUG)

release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]


class Warehouse:
    """[Warehouse](https://warehouse.pypa.io/index.html) is a web application that implements the canonical Python package index (repository); its production deployment is PyPI."""

    @staticmethod
    def parse_metadata(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        if metadata:
            urls = Warehouse.urls(metadata)
            repository_url = Warehouse.extract_repository_url(urls.values())
            if repository_url:
                return repository_url
        return None

    @staticmethod
    def urls(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> OrderedDict[str, str]:
        """Get all urls in the `home_page`, `download_url`, and `project_urls` field of distribution metadata. Code modified from: https://github.com/pypi/warehouse/blob/main/warehouse/packaging/models.py#L555

        Returns:
            dict[str, str]: urls in the package metadata
        """
        _urls = OrderedDict()

        if metadata:
            if metadata["home_page"]:
                _urls["Homepage"] = metadata["home_page"]
            if metadata["download_url"]:
                _urls["Download"] = metadata["download_url"]

            if metadata["project_urls"]:
                for name, url in metadata["project_urls"].items():
                    # avoid duplicating homepage/download links in case the same
                    # url is specified in the pkginfo twice (in the Home-page
                    # or Download-URL field and again in the Project-URL fields)
                    comp_name = name.casefold().replace("-", "").replace("_", "")
                    if comp_name == "homepage" and url == _urls.get("Homepage"):
                        continue
                    if comp_name == "downloadurl" and url == _urls.get("Download"):
                        continue

                    _urls[name] = url

        return _urls

    @staticmethod
    def extract_repository_url(urls) -> Optional[str]:
        """Get the first GitHub repository url in the `home_page`, `download_url`, and `project_urls` field of distribution metadata.

        Args:
            urls (_type_): _description_

        Returns:
            Optional[str]: _description_
        """
        for url in urls:
            parsed = urlparse(url)
            segments = parsed.path.strip("/").split("/")
            if parsed.netloc in {"github.com", "www.github.com"} and len(segments) >= 2:
                user_name, repo_name = segments[:2]
                if user_name in GITHUB_RESERVED_NAMES:
                    continue
                if repo_name.endswith(".git"):
                    repo_name = repo_name.removesuffix(".git")
                return f"https://github.com/{user_name}/{repo_name}".lower()
        return None


if __name__ == "__main__":
    with open("data/Warehouse.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version", "Warehouse"])
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
                    writer.writerow([name, version, repo_url.lower()])
                else:
                    writer.writerow([name, version, None])
            except Exception as e:
                logger.error(f"{name}, {version}, {e}")
                break
