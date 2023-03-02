import json
import os
import re
import sys
import time
import xmlrpc.client
from typing import List

import requests


def safe_open(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


class PyPI:
    NAME = "PyPI"
    BASE_URL = "https://pypi.org"

    JSON_API_BASE = "https://pypi.org/pypi"
    """JSON API endpoint"""

    SIMPLE_API_BASE_URL = "https://pypi.org/simple"
    """Simple API endpoint"""

    NEWEST_PACKAGES_FEED = "https://pypi.org/rss/packages.xml"
    """return the lastest 40 newly created packages"""

    LATEST_UPDATES_FEED = "https://pypi.org/rss/updates.xml"
    """return the lastest 100 newly created packages"""

    PROJECT_RELEASES_BASE_FEED = "https://pypi.org/rss/project/%s/releases.xml"
    """return the lastest 40 releases of the given package."""

    def __init__(self, data_folder: str = "/data/pypi_data") -> None:
        """Initialize a PyPI object.

        Args:
            data_folder (str): the folder that store PyPI data. Defaults to "/data/pypi_data".
        """
        self.data_folder = data_folder

        self.name_file = os.path.join(data_folder, "names.json")
        """The file that stores package names"""

    def list_all_packages(
        self,
        api: str = "xmlrpc",
        update: bool = True,
        dump: bool = False,
        timeout: int = 60,
    ) -> List[str]:
        """Return names of all packages registered on PyPI. Load form existing file or update the data.

        Args:
            api (str, optional): the api used to retrieve packages, should be "xmlrpc" or "simple". XML-RPC API returns more complete results than Simple API, but XML-RPC API will be deprecated in the future. Defaults to "xmlrpc".
            update (bool): If False, load package names from `self.name_file` (if exists). Else, query PyPI API and update data. Defaults to True.
            dump (bool): If True, dump package names to `self.name_file`. Defaults to False.
            timeout (int, optional): the timeout for `requests.get`. Defaults to 60.
        """
        assert api in ["simple", "xmlrpc"], "api should be `xmlrpc` or `simple`"

        ## if `update`` is False and `slef.name_file` exists, load data from the file and return.
        if (not update) and os.path.exists(self.name_file):
            return list(json.load(open(self.name_file)).values())[0]

        if api == "xmlrpc":
            return self.list_with_xmlrpc(update, dump)
        elif api == "simple":
            return self.list_with_simple(update, dump, timeout)
        return []

    def list_with_xmlrpc(self, update: bool = True, dump: bool = False) -> List[str]:
        """List packages names with XML-RPC API.

        Args:
            update (bool): If False, load package names from `self.name_file` (if exists). Else, query XML-RPC API and update data. Defaults to True.
            dump (bool): If True, dump package names to `self.name_file`. Defaults to False.
        """

        if (not update) and (os.path.exists(self.name_file)):
            return list(json.load(open(self.name_file)).values())[0]

        try:
            client = xmlrpc.client.ServerProxy(PyPI.JSON_API_BASE)

            # record current timestamp, for next package update use.
            timestamp = time.time()
            pkgs = client.list_packages()

            if dump:
                with open(safe_open(self.name_file), "w") as f:
                    json.dump({timestamp: pkgs}, f, indent=4)

            return pkgs
        except Exception as e:
            print("[ERROR]: XML-RPC API query error!", e, file=sys.stderr)

        return []

    def list_with_simple(
        self, update: bool = True, dump: bool = False, timeout: int = 60
    ) -> List[str]:
        """List package names with Simple API.

        Args:
            update (bool): If False, load package names from `self.name_file` (if exists). Else, query Simple API and update data. Defaults to True.
            dump (bool): If True, dump package names to `self.name_file`. Defaults to False.
            timeout (int): the timeout of `requests.get`. Defaults to 60.
        """

        if (not update) and (os.path.exists(self.name_file)):
            pkgs = list(json.load(open(self.name_file)).values())[0]
            return pkgs

        try:
            # record current timestamp, for next package update use.
            timestamp = time.time()

            response = requests.get(PyPI.SIMPLE_API_BASE_URL, timeout=timeout)
            response.raise_for_status()
            content = response.text
            pattern = r"<a href=.*>(.*?)</a>"
            pkgs = re.findall(pattern, content)

            if dump:
                with open(safe_open(self.name_file), "w") as f:
                    json.dump({timestamp: pkgs}, f, indent=4)

            return pkgs
        except Exception as e:
            print("[ERROR]: Simple API query error!", e, file=sys.stderr)
            return []


class Package:
    def __init__(self, name: str, data_folder="/data/pypi_data/metadata") -> None:
        """Initialize a PyPI Package object with package name.

        Args:
            name (str): the PyPI package's name
            data_folder (str, optional): the folder that stores package's release metadata. Defaults to "/data/pypi_data/metadata".
        """
        self.name = name
        self.data_folder = os.path.join(data_folder, name)

    def get_versions(self, update: bool = True, dump: bool = False):
        """Return all versions of the package. This piece information can be accessed by both JSON API and XML-RPC API. Since XML-RPC API will be deprecated, here only uses the JSON API.

        Args:
            update(bool): If False, load package metadata from the `{self.name}.json` file in `self.data_folder` (if exists). Else, query Simple API and update data. Defaults to True.
            dump (bool): If True, dump package metadata to the `{self.name}.json` file in `self.data_folder`. Defaults to False.
        """
        file_path = os.path.join(self.data_folder, f"{self.name}.json")

        if (not update) and os.path.exists(file_path):
            data = json.load(open(file_path))
            return list(data["releases"].keys())

        try:
            r = requests.get(PyPI.JSON_API_BASE + f"/{self.name}/json")
            r.raise_for_status()
            data = r.json()
            if dump:
                with open(safe_open(file_path), "w") as f:
                    json.dump(data, f, indent=4)
            return list(data["releases"].keys())
        except Exception as e:
            print(
                f"[ERROR]: Package metadata query for {self.name} error!",
                e,
                file=sys.stderr,
            )
            return []

    def query_single_release(self, version: str, dump: bool = False):
        """Query the metadata of the given version

        Args:
            version (str): the version to query metadata.
            dump (bool): If True, dump package metadata to the `{version}.json` file in `self.data_folder`. Defaults to False.
        """

        file_path = os.path.join(self.data_folder, f"{version}.json")

        if os.path.exists(file_path):
            data = json.load(open(file_path))
            print(f"[INFO]: {file_path} already exist!", file=sys.stderr)
            return data

        try:
            r = requests.get(PyPI.JSON_API_BASE + f"/{self.name}/{version}/json")
            r.raise_for_status()
            data = r.json()
            if dump:
                with open(safe_open(file_path), "w") as f:
                    json.dump(data, f, indent=4)
            return data
        except Exception as e:
            print(
                f"[ERROR]: Release metadata query for {self.name} {version} error!",
                e,
                file=sys.stderr,
            )
