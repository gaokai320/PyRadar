from typing import Optional

from pymongo import MongoClient

from baselines.utils import get_latest_version

release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]


class Release:
    def __init__(self, package_name: str, version: Optional[str] = None) -> None:
        self.package_name = package_name
        self.version = version

    @property
    def metadata(self) -> Optional[dict[str, str]]:
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
