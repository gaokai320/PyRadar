import json
import logging
import os
import urllib.request
from functools import cached_property
from typing import Optional

from pymongo import MongoClient

from pyradar.repository import Repository
from pyradar.utils import DistReader

logger = logging.getLogger(__name__)

# Reference: https://peps.python.org/pep-0527/
ACCEPTED_PACKAGETYPES = ("sdist", "bdist_wheel", "bdist_egg")
ACCEPTED_EXTENSIONS = (".tar.gz", ".zip", ".whl", ".egg")

radar_db = MongoClient("127.0.0.1", 27017)["radar"]
dist_file_info = radar_db["distribution_file_info"]


def download(
    url: str,
    save_path: str,
    check: bool = True,
    max_try=3,
) -> bool:
    if check and os.path.exists(save_path):
        return True

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    success = False
    i = 0

    while (not success) and (i < max_try):
        try:
            urllib.request.urlretrieve(url, save_path)
            success = True
        except Exception as e:
            i += 1
            logger.error(f"Error downloading {url}, retry {i}: {e}")

    return success


class Validator:
    def __init__(
        self,
        name: str,
        version: str,
        repo_url: str,
        base_folder: str,
        packagetype: str = "sdist",
    ) -> None:
        """Configure package's name, version, and data folder.

        Args:
            name (str): package name
            base_folder (str): should be the environment variable `$DATA_HOME`.
            version (str, optional): package version. If None, use the latest version. Defaults to None.
        """
        self.name = name
        self.version = version
        self.repository_url = repo_url
        self.base_folder = base_folder
        self.distribution_folder = os.path.join(base_folder, "distribution", self.name)
        self.packagetype = packagetype

    @cached_property
    def repository(self) -> Optional[Repository]:
        if self.repository_url:
            return Repository(url=self.repository_url, base_folder=self.base_folder)

        return None

    @cached_property
    def distribution_files(self) -> list[tuple[str, str]]:
        """get distribution urls (if have) of the release.

        Returns:
            dict[str, str]: three kay-value pairs corresponding to packagetypes: `sdist`, `bdist_wheel`, `bdist_egg` respectively
        """
        res = []
        for data in dist_file_info.find(
            {
                "name": self.name,
                "version": self.version,
                "packagetype": self.packagetype,
            }
        ):
            url = data["url"]
            filename = data["filename"]
            if not filename.endswith(ACCEPTED_EXTENSIONS):
                continue
            save_path = os.path.join(self.distribution_folder, filename)
            download(url, save_path)
            for fname, fsha in DistReader(save_path).file_shas():
                res.append((fname, fsha))
        return res

    def get_phantom_files(
        self, include: Optional[list[str]] = None
    ) -> tuple[int, int, list[tuple[str, str]]]:
        total = 0
        matched = 0
        phantom = []
        if self.distribution_files and self.repository:
            repo_blob_shas = self.repository.blob_shas

            if include:
                total_files = [
                    (fname, fsha)
                    for fname, fsha in self.distribution_files
                    if any(fname.endswith(suffix) for suffix in include)
                ]

            else:
                total_files = self.distribution_files

            total = len(total_files)
            matched = len(
                [(fname, fsha) for fname, fsha in total_files if fsha in repo_blob_shas]
            )
            phantom = [
                [fname, fsha]
                for fname, fsha in total_files
                if fsha not in repo_blob_shas
            ]

        return [total, matched, phantom]
