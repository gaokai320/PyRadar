import json
import os
import re
import sys
import time
import xmlrpc.client

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
        self.data_folder = data_folder

    def list_all_packages(self, api: str = "xmlrpc", filename=None, timeout: int = 60):
        """Return names of all packages registered on PyPI.

        Args:
            api (str, optional): the api used to retrieve packages, should be `xmlrpc` or `simple`. XML-RPC API returns more complete results than Simple API, but XML-RPC API will be deprecated in the future. Defaults to `xmlrpc`.
            filename (str): file to save all package names. If None, will not save to file. Else, join with `self.data_folder`. Defaults to None.
            timeout (int, optional): the timeout for requests.get. Defaults to 60.

        """
        assert api in ["simple", "xmlrpc"], "api should be `xmlrpc` or `simple`"
        pkgs = []
        if filename is None:
            file_path = None
        else:
            file_path = os.path.join(self.data_folder, filename)
        ts = int(time.time())
        if api == "xmlrpc":
            pkgs = self.list_with_xmlrpc(ts, file_path)
        elif api == "simple":
            pkgs = self.list_with_simple(ts, file_path, timeout)
        return pkgs

    def list_with_xmlrpc(self, timestamp: int, file_path=None):
        """Return names of all PyPI packages with XML-RPC API.

        Args:
            timestamp (int): the timestamp when listing all packages.
            file_path (str): file to store all package names. If None, will not save to file. Defaults to None.
        """
        pkgs = []
        try:
            client = xmlrpc.client.ServerProxy(PyPI.JSON_API_BASE)
            pkgs = client.list_packages()
        except Exception as e:
            print("XML-RPC API query error!", e, file=sys.stderr)

        if file_path is not None:
            with open(safe_open(file_path), "w") as f:
                json.dump({timestamp: pkgs}, f, indent=4)

        return pkgs

    def list_with_simple(self, timestamp: int, file_path=None, timeout=60):
        """Return names of all PyPI packages with Simple API.

        Args:
            timestamp (int): the timestamp when listing all packages.
            file_path (str): file to store all package names. If None, will not save to file. Defaults to None.
            timeout (int): the timeout of requests.get. Defaults to 60.
        """
        pkgs = []
        url = PyPI.SIMPLE_API_BASE_URL
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            content = response.text
            pattern = r"<a href=.*>(.*?)</a>"
            pkgs = re.findall(pattern, content)
        except Exception as e:
            print("Simple API query error!", e, file=sys.stderr)

        if file_path is not None:
            with open(safe_open(file_path), "w") as f:
                json.dump({timestamp: pkgs}, f, indent=4)

        return pkgs


class Package:
    def __init__(self, name: str, data_folder="/data/pypi_data/metadata") -> None:
        """Initialize a PyPI Package object with the name

        Args:
            name (str): the PyPI package's name
            data_folder (str, optional): the folder that stores package's release metadata. Defaults to "/data/pypi_data/metadata".
        """
        self.name = name
        self.data_folder = os.path.join(data_folder, name)

    def get_versions(self, tofile=0):
        """Return all versions of the package. This piece information can be accessed by both JSON API and XML-RPC API. Since XML-RPC API will be deprecated, here only uses the JSON API."""
        url = PyPI.JSON_API_BASE + f"/{self.name}/json"
        try:
            r = requests.get(url)
            r.raise_for_status()
            data = r.json()
            if tofile == 1:
                file_path = os.path.join(self.data_folder, f"{self.name}.json")
                with open(safe_open(file_path), "w") as f:
                    json.dump(data, f, indent=4)
            versions = list(data["releases"].keys())
            return versions
        except Exception as e:
            print(f"Package metadata query for {self.name} error!", e, file=sys.stderr)

    def query_single_release(self, version: str, tofile=0):
        """Query the metadata of the given version

        Args:
            version (str): the version to query metadata
        """
        url = PyPI.JSON_API_BASE + f"/{self.name}/{version}/json"
        try:
            r = requests.get(url)
            r.raise_for_status()
            data = r.json()
            if tofile == 1:
                file_path = os.path.join(self.data_folder, f"{version}.json")
                with open(safe_open(file_path), "w") as f:
                    json.dump(data, f, indent=4)
            return data
        except Exception as e:
            print(f"Release metadata query for {self.name} {version} error!", e, file=sys.stderr)
