import hashlib
import json
import logging
import os
import tarfile
import zipfile
from functools import cached_property
from typing import Optional, Union

import wget

from package_statistics import url_parser
from pyradar.repository import Repository

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Reference: https://peps.python.org/pep-0527/
ACCEPTED_PACKAGETYPES = ["sdist", "bdist_wheel", "bdist_egg"]
ACCEPTED_EXTENSIONS = [".tar.gz", ".zip", ".whl", ".egg"]


def calculate_sha(content: Union[bytes, str]) -> Optional[str]:
    if isinstance(content, str):
        content = content.encode()
    if not isinstance(content, bytes):
        logger.error("Please pass in a bytes-like or str-like data")
        return None
    sha1 = hashlib.sha1()
    sha1.update(f"blob {len(content)}\0".encode())
    sha1.update(content)
    return sha1.hexdigest()


class ZipReader:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.file = zipfile.ZipFile(self.file_path)

    @cached_property
    def file_shas(self) -> list[tuple[str, str]]:
        res = []
        for name in self.file.namelist():
            with self.file.open(name) as f:
                res.append((name, calculate_sha(f.read())))
        return res

    def get_file_content(self, filename: str) -> str:
        return self.file.open(filename).read().decode("utf-8")


class TarReader:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.file = tarfile.open(self.file_path)

    @cached_property
    def file_shas(self) -> list[tuple[str, str]]:
        res = []
        for member in self.file.getmembers():
            if member.isreg():
                with self.file.extractfile(member) as f:
                    res.append((member.name, calculate_sha(f.read())))
        return res

    def get_file_content(self, filename: str) -> str:
        return self.file.extractfile(filename).read().decode("utf-8")


class Reader:
    def __init__(self, file_path: str) -> None:
        if file_path.endswith(".tar.gz"):
            self.reader = TarReader(file_path)
        elif any(file_path.endswith(suffix) for suffix in [".zip", "whl", ".egg"]):
            self.reader = ZipReader(file_path)

    @cached_property
    def file_shas(self) -> list[tuple[str, str]]:
        return self.reader.file_shas

    def get_file_content(self, filename: str) -> str:
        return self.reader.get_file_content(filename)


class Validator:
    def __init__(
        self,
        name: str,
        base_folder: str,
        version: str = None,
    ) -> None:
        """Configure package's name, version, and data folder.

        Args:
            name (str): package name
            base_folder (str): should be the environment variable `$DATA_HOME`.
            version (str, optional): package version. If None, use the latest version. Defaults to None.
        """
        self.name = name

        self.base_folder = base_folder
        self.metadata_folder = os.path.join(self.base_folder, "metadata", self.name)
        if not os.path.exists(self.metadata_folder):
            logger.error(f"{self.name} not found.")
            raise FileNotFoundError(f"{self.name} not found")
        self.distribution_folder = os.path.join(base_folder, "distribution", self.name)

        # If no version specified, use the latest version
        if version:
            self.version = version
        else:
            self.version = json.load(
                open(os.path.join(self.metadata_folder, f"{self.name}.json"))
            )["info"]["version"]

        # load metadata for the version.
        try:
            self.metadata = json.load(
                open(os.path.join(self.metadata_folder, f"{self.version}.json"))
            )
        except FileNotFoundError as e:
            logger.error(f"{self.name} {self.version} metadata not found")
            raise FileNotFoundError(f"{self.name} doesn't have version {self.version}")

    @cached_property
    def repository_url(self) -> Optional[str]:
        """the repository url of the release.

        Returns:
            str: a repository URL. If no repository found, return None.
        """
        url = None
        files = os.listdir(self.metadata_folder)

        ## first check the metadata of the corresponding version
        url = url_parser(self.metadata["info"])

        # If no repository url found, check other versions.
        if not url:
            for f in files:
                if f == f"{self.version}.json":
                    continue
                data = json.load(open(os.path.join(self.metadata_folder, f)))["info"]
                url = url_parser(data)
                if url:
                    break
        return url

    @cached_property
    def repository(self) -> Optional[Repository]:
        if self.repository_url:
            return Repository(url=self.repository_url, base_folder=self.base_folder)

        return None

    @cached_property
    def distribution_urls(self) -> Optional[dict[str, str]]:
        """get distribution urls (if have) of the release.

        Returns:
            dict[str, str]: three kay-value pairs corresponding to packagetypes: `sdist`, `bdist_wheel`, `bdist_egg` respectively
        """
        if "urls" in self.metadata:
            dist_infos = self.metadata["urls"]
        elif "releases" in self.metadata:
            dist_infos = self.metadata["releases"][self.version]
        else:
            logger.info(f"no distribution info found")
            return None

        urls = {k: None for k in ACCEPTED_PACKAGETYPES}
        sizes = {k: 0 for k in ACCEPTED_PACKAGETYPES}

        for info in dist_infos:
            packagetype = info.get("packagetype", "")
            if packagetype in ACCEPTED_PACKAGETYPES:
                url = info.get("url", "")
                size = info.get("size", 0)
                # select the largest distribution to deal with the corner case: tensorflow-2.11.0-cp310-cp310-win_amd64.whl only have 1.9kB.
                if any(url.endswith(ext) for ext in ACCEPTED_EXTENSIONS) and (
                    size > sizes[packagetype]
                ):
                    urls[packagetype] = url
                    sizes[packagetype] = size

        return urls

    def download(self, max_try=5):
        if not self.distribution_urls:
            return

        os.makedirs(self.distribution_folder, exist_ok=True)
        for _, url in self.distribution_urls.items():
            if url:
                filename = url.rsplit("/", 1)[1]
                save_path = os.path.join(self.distribution_folder, filename)
                if os.path.exists(save_path):
                    logger.info(f"{filename} has already been downloaded")
                    continue
                logger.info(f"start downloading {filename} from {url}")
                i = 0
                success = False
                while (not success) and (i < max_try):
                    try:
                        wget.download(url, save_path)
                        success = True
                        logger.info(f"\nfinish downloading {filename} from {url}")
                    except Exception as e:
                        i = i + 1
                        logger.error(f"Download error, retry......")
                if not success:
                    logger.error(f"Failed to download {filename} from {url}")

    def dist_reader(self, type="sdist") -> Optional[Reader]:
        if type not in ACCEPTED_PACKAGETYPES:
            raise TypeError(
                f"Distribution type should be `sdist`, `bdist_wheel`, or `bdist_egg`, you pass in {type}"
            )
        url = self.distribution_urls[type]
        if url:
            filename = url.rsplit("/", 1)[1]
            save_path = os.path.join(self.distribution_folder, filename)
            if not os.path.exists(save_path):
                self.download()
            dist_reader = Reader(save_path)
            return dist_reader
        return None

    @cached_property
    def sdist_reader(self) -> Optional[Reader]:
        return self.dist_reader("sdist")

    @cached_property
    def wheel_reader(self) -> Optional[Reader]:
        return self.dist_reader("bdist_wheel")

    @cached_property
    def egg_reader(self) -> Optional[Reader]:
        return self.dist_reader("bdist_egg")

    def match_shas(
        self, package_type="sdist", include: str = [".py"]
    ) -> tuple[int, int, list[tuple[str, str]]]:
        reader = self.dist_reader(package_type)
        total = 0
        matched = 0
        phantom = []
        if self.repository and reader:
            dis_file_shas = reader.file_shas
            repo_blob_shas = self.repository.blob_shas

            if include:
                for name, sha in dis_file_shas:
                    if any(name.endswith(suffix) for suffix in include):
                        total += 1
                        if sha in repo_blob_shas:
                            matched += 1
                        else:
                            phantom.append((name, sha))
            else:
                total = len(dis_file_shas)
                matched = len(
                    [sha for _, sha in dis_file_shas if sha in repo_blob_shas]
                )
                phantom = [
                    (name, sha)
                    for name, sha in dis_file_shas
                    if sha not in repo_blob_shas
                ]
        return [total, matched, phantom]

    def map_commit(self, type="sdist"):
        pass

    def get_modify_file_pairs(self):
        pass

    def maintainer_analysis(self):
        pass
