import csv
import logging
from typing import Optional

from pymongo import MongoClient
from tqdm import tqdm

from baselines.url_parser import URLParser
from baselines.utils import GITHUB_RESERVED_NAMES, configure_logger

logger = configure_logger("librariesio", "log/librariesio.log", logging.DEBUG)

release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]


class LibrariesIO:
    @staticmethod
    def parse_metadata(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        if not metadata:
            return None

        # https://github.com/librariesio/libraries.io/blob/main/app/models/package_manager/pypi.rb#L102
        return LibrariesIO.repo_fallback(
            LibrariesIO.select_repository_url(metadata),
            LibrariesIO.select_homepge_url(metadata),
        )

    @staticmethod
    def select_repository_url(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        """reimplementation of [`select_repository_url`](https://github.com/librariesio/libraries.io/blob/main/app/models/package_manager/pypi.rb#L84)"""
        fields = ["Source", "Source Code", "Repository", "Code"]
        project_urls = metadata.get("project_urls")
        if project_urls:
            return next(
                (
                    project_urls.get(field)
                    for field in fields
                    if project_urls.get(field)
                ),
                None,
            )

    @staticmethod
    def select_homepge_url(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        """reimplementation of [`select_homepage_url`](https://github.com/librariesio/libraries.io/blob/main/app/models/package_manager/pypi.rb#L90)"""
        if metadata.get("home_page"):
            return metadata.get("home_page")
        if metadata.get("project_urls"):
            return metadata.get("project_urls").get("Homepage")

    @staticmethod
    def repo_fallback(repo, homepage) -> Optional[str]:
        # reimplementation of [`repo_fallback`](https://github.com/librariesio/libraries.io/blob/main/app/models/package_manager/base.rb#L314)
        repo = "" if not repo else repo
        homepage = "" if not homepage else homepage
        repo_url = URLParser.try_all(repo)
        homepage_url = URLParser.try_all(homepage)

        # if repo and homepage are not a valid repository url, just return None instead of default to repo
        if repo_url:
            return repo_url
        if homepage_url:
            return homepage_url
        return None


if __name__ == "__main__":
    with open("data/Libraries.io.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version", "Libraries.io"])
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
                repo_url = LibrariesIO.parse_metadata(metadata)
                if repo_url:
                    writer.writerow([name, version, repo_url.lower()])
                else:
                    writer.writerow([name, version, None])
            except Exception as e:
                logger.error(f"{name}, {version}, {e}")
                break
