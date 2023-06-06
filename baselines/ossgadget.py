from functools import cached_property
import re
from typing import Optional, Union

from baselines.utils import get_latest_version
from pymongo import MongoClient

release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]

# Reference to: https://github.com/microsoft/OSSGadget/blob/main/src/Shared/PackageManagers/BaseProjectManager.cs#L68
pattern = re.compile(r"github\.com/([a-z0-9\-_\.]+)/([a-z0-9\-_\.]+)", flags=re.I)


class OSSGadget:
    """OSSGadget is a class that imitate the process of [OSSGadget oss-find-source tool](https://github.com/microsoft/OSSGadget/wiki/OSS-Find-Source) that Attempts to locate the source code on GitHub of a given Python package.

    OSSGadget locates a package/release's source code repository on GitHub from the package/release's PyPI metadata, see [`IdentifySourceRepositoryAsync`](https://github.com/microsoft/OSSGadget/blob/main/src/Shared/PackageManagers/BaseProjectManager.cs). Here, we use pre-collected PyPI release metadata dump instead.
    """

    def __init__(self, package_name: str, version: str = None) -> None:
        self.package_name = package_name
        self.version = version

    @cached_property
    def metadata(self) -> Optional[dict[str, str]]:
        """Retrieve metadata fields used by OSSGadget."""

        # if version is not specified, use the latest non development version
        if not self.version:
            self.version = get_latest_version(self.package_name)

        query = {"name": self.package_name, "version": self.version}
        metadata = release_metadata.find_one(
            filter=query,
            projection={
                "_id": 0,
            },
        )
        return metadata

    def search_source(self) -> Optional[str]:
        """Search the source code repository of the package.

        Returns:
            Optional[str]: The URL of the source code repository.
        """
        metadata = self.metadata
        if metadata:
            repo_urls = OSSGadget.parse_metadata(metadata)
            if repo_urls:
                return repo_urls[0]
        else:
            return None

    @staticmethod
    def parse_metadata(metadata: dict[str, Union[str, dict[str, str]]]) -> list[str]:
        """Parse the metadata fields used by OSSGadget.

        OSSGadget only searches the `home_page`, `download_url` and `project_urls` field, see [`SearchRepoUrlsInPackageMetadata`](https://github.com/microsoft/OSSGadget/blob/main/src/Shared/PackageManagers/PyPIProjectManager.cs).

        Args:
            metadata (dict[str, str]): The metadata fields.

        Returns:
            Optional[str]: The URL of the source code repository.
        """
        repository_urls = []
        if metadata is None:
            return repository_urls
        for key, value in metadata.items():
            if key.lower() in ["home_page", "download_url"] and value:
                urls = OSSGadget.extractGitHubURL(value)
                if urls:
                    repository_urls.append(urls[0])
            elif key.lower() == "project_urls" and value:
                for url in value.values():
                    urls = OSSGadget.extractGitHubURL(url)
                    if urls:
                        repository_urls.append(urls[0])
        return list(set(repository_urls))

    @staticmethod
    def extractGitHubURL(url: str) -> list[str]:
        """Extract GitHub URL from a URL.

        OSSGadget use regex to extract GitHub URL, see [`ExtractGitHubPackageURLs`](https://github.com/microsoft/OSSGadget/blob/main/src/Shared/PackageManagers/BaseProjectManager.cs)

        Args:
            url (str): The URL to be extracted.

        Returns:
            Optional[str]: The GitHub URL.
        """
        res = []
        for matchObj in pattern.findall(url.lower()):
            user, repo = matchObj
            if user in ["repos", "metacpan"]:
                continue
            if repo.endswith(".git"):
                repo = repo[:-4]
            res.append(f"https://github.com/{user}/{repo}")

        return res
