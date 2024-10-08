import json
import logging
import os
import re
from functools import cached_property
from typing import Optional

import pandas as pd
from joblib import load
from Levenshtein import ratio
from pymongo import MongoClient

from pyradar.repository import Repository
from pyradar.utils import DistReader, download, get_downloads_data, get_maintainer_info

logger = logging.getLogger(__name__)

# Reference: https://peps.python.org/pep-0527/
ACCEPTED_PACKAGETYPES = ("sdist", "bdist_wheel", "bdist_egg")
ACCEPTED_EXTENSIONS = (".tar.gz", ".zip", ".whl", ".egg")

radar_db = MongoClient("127.0.0.1", 27017)["radar"]
dist_file_info = radar_db["distribution_file_info"]

download_data = get_downloads_data()
maintainer_info = get_maintainer_info()

pkg_maintainers = json.load(open("data/pypi_maintainers.json"))

sub_pattern = re.compile(f"[^a-zA-Z0-9\.]")
sub_pattern2 = re.compile(r"[^a-zA-Z0-9]")


class Validator:
    def __init__(
        self,
        name: str,
        version: str,
        repo_url: str,
        base_folder: str,
        packagetype: str = "sdist",
        translate_newline: bool = True,
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
        self.translate_newline = translate_newline

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
        data = dist_file_info.find_one(
            {
                "name": self.name,
                "version": self.version,
                "packagetype": self.packagetype,
            }
        )
        if data:
            url = data["url"]
            filename = data["filename"]
            if not filename.endswith(ACCEPTED_EXTENSIONS):
                return res
            save_path = os.path.join(self.distribution_folder, filename)
            download(url, save_path)
            for fname, fsha in DistReader(
                save_path, self.translate_newline
            ).file_shas():
                res.append((fname, fsha))
        return res

    @cached_property
    def phantom_files(self) -> list[list[str, str]]:
        res = []
        if self.distribution_files and self.repository:
            repo_blob_shas = self.repository.blob_shas
            res = [
                [fname, fsha]
                for fname, fsha in self.distribution_files
                if fsha not in repo_blob_shas
            ]

        return res

    @cached_property
    def num_phantom_pyfiles(self) -> int:
        if (not self.distribution_files) or (not self.repository):
            return -1
        cnt = 0
        for fname, _ in self.phantom_files:
            if fname.endswith(".py"):
                cnt += 1
        return cnt

    @cached_property
    def setup_change(self) -> int:
        has_setup, has_pyproject = False, False
        for f in self.repository.file_names:
            basename = f.split("/")[-1]
            if (not has_setup) and (basename == "setup.py"):
                has_setup = True
            if (not has_pyproject) and (basename == "pyproject.toml"):
                has_pyproject = True

        for fname, _ in self.phantom_files:
            if len(fname.split("/")) != 2:
                continue
            if (os.path.basename(fname) == "setup.py") and has_setup:
                return 1
            if (os.path.basename(fname) == "pyproject.toml") and has_pyproject:
                return 1
        return 0

    @cached_property
    def num_downloads(self) -> int:
        return download_data.get(self.name, 0)

    @cached_property
    def num_maintainers(self) -> int:
        return len(pkg_maintainers.get(self.name, []))

    @cached_property
    def tag_match(self) -> int:
        for tag in self.repository.tag_shas:
            if self.version == tag:
                return 1
            if tag.endswith(self.version):
                return 1
            if sub_pattern.sub(".", tag).endswith(sub_pattern.sub(".", self.version)):
                return 1
        return 0

    @cached_property
    def num_maintainer_pkgs(self) -> int:
        pkgs = []
        for maintainer in pkg_maintainers.get(self.name, []):
            pkgs.extend(maintainer_info[maintainer])
        return len(set(pkgs))

    @cached_property
    def name_similarity(self):
        user, repo = self.repository_url.split("/")[-2:]
        ratio1 = ratio(
            sub_pattern2.sub("", self.name),
            sub_pattern2.sub("", repo),
        )
        ratio2 = ratio(
            sub_pattern2.sub("", self.name), sub_pattern2.sub("", user + repo)
        )
        return max(ratio1, ratio2)

    @cached_property
    def maintainer_max_downloads(self) -> int:
        max_downloads = 0
        for maintainer in pkg_maintainers.get(self.name, []):
            for pkg in maintainer_info[maintainer]:
                num_download = download_data.get(pkg, 0)
                if num_download > max_downloads:
                    max_downloads = num_download
        return max_downloads

    def features(self) -> list[str]:
        return [
            self.num_phantom_pyfiles,
            self.setup_change,
            self.name_similarity,
            self.tag_match,
            self.num_maintainers,
            self.num_maintainer_pkgs,
            # self.maintainer_max_downloads,
        ]

    def validate(self, model="dt", threshold=0.5):
        if model not in ["ada", "dt", "gb", "lr", "rf", "svm", "xgb"]:
            print(
                f"model should be ada, dt, gb, lr, rf, svm, or xgb, {model} is passed"
            )
            return
        feature_columns = [
            "num_phantom_pyfiles",
            "setup_change",
            "name_similarity",
            "tag_match",
            "num_maintainers",
            "num_maintainer_pkgs",
            # "maintainer_max_downloads",
        ]
        features = pd.DataFrame([self.features()], columns=feature_columns)
        ml_model = load(f"models/best_{model}.joblib")
        prob = ml_model.predict_proba(features)[:, 1][0]
        return prob
