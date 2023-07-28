import re
from typing import Optional

pattern = re.compile(
    r"(github\.com|bitbucket\.org|gitlab\.com)/[a-zA-Z0-9_\.\-]+/[a-zA-Z0-9_\.\-]+"
)

removed_urls = ["https://github.com/sponsors", "https://github.com/pypa/sampleprojec", "https://github.com/user/reponame"]


class MetadataRetriever:
    @staticmethod
    def parse_metadata(
        metadata: dict[str, Optional[str | dict[str, str]]]
    ) -> Optional[str]:
        if not metadata:
            return None
        home_page = metadata.get("home_page").lower()
        download_url = metadata.get("download_url").lower()
        project_urls = metadata.get("project_urls", [])
        if home_page:
            match = pattern.search(home_page)
            if match:
                return "https://" + match.group(0).rstrip(".git")
        if download_url:
            match = pattern.search(download_url)
            if match:
                return "https://" + match.group(0).rstrip(".git")
        if project_urls:
            for url in project_urls.values():
                url = url.lower()
                match = pattern.search(url)
                if match:
                    remove = False
                    for removed_url in removed_urls:
                        if removed_url in url: 
                            remove = True
                    if not remove:
                        return "https://" + match.group(0).rstrip(".git")
        return None


if __name__ == "__main__":
    import csv

    from pymongo import MongoClient
    from tqdm import tqdm

    db = MongoClient("127.0.0.1", 27017)["radar"]
    release_metadata = db["release_metadata"]

    with open("data/metadata_retriever.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version", "PyRadar.MetadataRetriever"])
        for metadata in tqdm(
            release_metadata.find(
                {},
                {
                    "_id": 0,
                    "name": 1,
                    "version": 1,
                    "home_page": 1,
                    "download_url": 1,
                    "project_urls": 1,
                },
            )
        ):
            name = metadata["name"]
            version = metadata["version"]
            repo_url = MetadataRetriever.parse_metadata(metadata)
            writer.writerow([name, version, repo_url])
