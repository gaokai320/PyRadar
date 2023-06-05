from packaging.version import Version
from pymongo import MongoClient

release_metadata = MongoClient("127.0.0.1", 27017)["radar"]["release_metadata"]


def get_latest_version(package_name: str) -> str:
    versions = [
        Version(res["version"])
        for res in release_metadata.find(
            {"name": package_name}, projection={"_id": 0, "version": 1}
        )
    ]
    versions = [v for v in versions if not (v.is_prerelease or v.is_devrelease)]
    versions.sort()
    return str(versions[-1]) if versions else None
