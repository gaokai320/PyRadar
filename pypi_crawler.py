import json
import logging
import os
import random
import re
import time
import xml.etree.ElementTree as ET
import xmlrpc.client
from datetime import datetime, timezone

from bs4 import BeautifulSoup
import requests
from joblib import Parallel, delayed
from tqdm import tqdm

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def safe_open(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}
proxies = {"http": "http://127.0.0.1:10805", "https": "http://127.0.0.1:10805"}


def _single_get(url: str, headers: dict, timeout: int = 5):
    try:
        r = requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
        if r.status_code == 404:
            logger.info(f"{url}: 404 not found!")
            return 404
        r.raise_for_status()
        return r
    except Exception as e:
        logger.error(f"{url}: Query error! {e}")
        return None


def my_get(url: str, headers: dict, timeout: int = 5, email: str = None, repeat=0):
    if email:
        headers["email"] = email
    if repeat > 0:
        for _ in range(repeat):
            r = _single_get(url, headers=headers, timeout=timeout)
            if r == 404:
                return None
            if r:
                return r
        return None
    else:
        while True:
            r = _single_get(url, headers=headers, timeout=timeout)
            if r == 404:
                return None
            if r:
                return r


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
        email: str = None,
    ) -> list[str]:
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
            return json.load(open(self.name_file))["packages"]

        if api == "xmlrpc":
            return self.list_with_xmlrpc(update, dump)
        elif api == "simple":
            return self.list_with_simple(update, dump, timeout, email)
        return []

    def list_with_xmlrpc(self, update: bool = True, dump: bool = False) -> list[str]:
        """list packages names with XML-RPC API.

        Args:
            update (bool): If False, load package names from `self.name_file` (if exists). Else, query XML-RPC API and update data. Defaults to True.
            dump (bool): If True, dump package names to `self.name_file`. Defaults to False.
        """

        if (not update) and (os.path.exists(self.name_file)):
            return json.load(open(self.name_file))["packages"]

        try:
            client = xmlrpc.client.ServerProxy(PyPI.JSON_API_BASE)

            # record current timestamp, for next package update use.
            timestamp = int(time.time())
            pkgs = client.list_packages()

            if dump:
                with open(safe_open(self.name_file), "w") as f:
                    json.dump({"timestamp": timestamp, "packages": pkgs}, f, indent=4)

            return pkgs
        except Exception as e:
            logger.error(f"XML-RPC API query error! {e}")

        return []

    def list_with_simple(
        self,
        update: bool = True,
        dump: bool = False,
        timeout: int = 60,
        email: str = None,
    ) -> list[str]:
        """list package names with Simple API.

        Args:
            update (bool): If False, load package names from `self.name_file` (if exists). Else, query Simple API and update data. Defaults to True.
            dump (bool): If True, dump package names to `self.name_file`. Defaults to False.
            timeout (int): the timeout of `requests.get`. Defaults to 60.
            email (str): the email in `requests.get` headers. Defaults to None.
        """

        if (not update) and (os.path.exists(self.name_file)):
            pkgs = json.load(open(self.name_file))["packages"]
            return pkgs

        try:
            # record current timestamp, for next package update use.
            timestamp = int(time.time())

            if email:
                headers["From"] = email

            response = my_get(
                PyPI.SIMPLE_API_BASE_URL, timeout=timeout, headers=headers
            )
            if response:
                response.raise_for_status()
                content = response.text
                pattern = r"<a href=.*>(.*?)</a>"
                pkgs = re.findall(pattern, content)

                if dump:
                    with open(safe_open(self.name_file), "w") as f:
                        json.dump(
                            {"timestamp": timestamp, "packages": pkgs}, f, indent=4
                        )
                return pkgs
            return []
        except Exception as e:
            logger.error(f"Simple API query error! {e}")
            return []

    @staticmethod
    def new_releases_since(timestamp: int) -> list[tuple[str, str, int]]:
        """Given a timestamp, return all new releases since then.

        Args:
            timestamp (int): the timestamp used to query updates.

        Returns:
            list[(str, str, int)]: A tuple list. For each tuple, the first element is the package name, the second element is the package version, and the third element is the release's upload timestamp.
        """
        res = []
        client = xmlrpc.client.ServerProxy(PyPI.JSON_API_BASE)
        recent_changes = client.changelog(timestamp)
        for entry in recent_changes:
            if entry[3] == "new release":
                res.append((entry[0], entry[1], int(entry[2])))
        return res

    def update(self, api: str = "xmlrpc"):
        """Update package lists and store new releases information. Currently, two APIs can be used to achieve this. the XML-RPC API and the RSS API. The RSS API only returns the latest 100 new releases. XMLRPC API can return all new releases since a timestamp, but will be depreated in the future. Per discussion on https://github.com/pypi/warehouse/issues/7116, we can query RSS API every minute or even second. Maybe, we can periodically update every 10 seconds?

        Args:
            kind (str, optional): Specify which API is used, should be "xmlrpc" or "rss".  Defaults to "xmlrpc".
        """
        assert api in ["xmlrpc", "rss"], "The API should be 'xmlrpc' or 'rss'."

        if not os.path.exists(self.name_file):
            logger.error(
                "Do not find the `names.json` file. "
                + "You should call `list_all_packages` method first!"
            )
            return False

        old_dump = json.load(open(self.name_file))
        old_ts = old_dump["timestamp"]
        old_pkgs = old_dump["packages"]

        if api == "xmlrpc":
            new_releases = PyPI.new_releases_since(old_ts)
        elif api == "rss":
            new_releases = PyPI.new_releases_by_rss()

        new_ts = 0
        p2v = dict()
        for p, v, t in new_releases:
            if t > new_ts:
                new_ts = t
            old_pkgs.append(p)
            p2v[p] = p2v.get(p, [])
            p2v[p].append(v)

        new_pkgs = list(set(old_pkgs))
        with open(self.name_file, "w") as f:
            json.dump({"timestamp": new_ts, "packages": new_pkgs}, f, indent=4)

        with open(os.path.join(self.data_folder, "updates.json"), "w") as f:
            json.dump(p2v, f, indent=4)

        return True

    @staticmethod
    def new_releases_by_rss(
        email: str = None, timeout: int = 60
    ) -> list[tuple[str, str, int]]:
        """Query new releases with FEED API. This API only returns the latest 100 new releases.

        Returns:
            list[tuple[str, str, int]]: a tuple list, the elements in a tuple corresponds to package name, package version, upload timestamp, respectively.

        Args:
            email (str): the email in `requests.get` headers. Defaults to None.
        """
        res = []
        if email:
            headers["From"] = email
        r = my_get(PyPI.LATEST_UPDATES_FEED, headers=headers, timeout=timeout)
        if r:
            root = ET.fromstring(r.text)
            for item in root[0].findall("item"):
                p, v = item.find("title").text.split()
                dt = item.find("pubDate").text
                dt = datetime.strptime(dt, "%a, %d %b %Y %H:%M:%S %Z")
                ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
                res.append((p, v, ts))
        return res


class Package:
    def __init__(self, name: str, data_folder="/data/pypi_data/metadata") -> None:
        """Initialize a PyPI Package object with package name.

        Args:
            name (str): the PyPI package's name
            data_folder (str, optional): the folder that stores package's release metadata. Defaults to "/data/pypi_data/metadata".
        """
        self.name = name
        self.data_folder = os.path.join(data_folder, name)

    def get_versions(
        self,
        update: bool = True,
        dump: bool = False,
        email: str = None,
        timeout: int = 65,
    ):
        """Return all versions of the package. This piece information can be accessed by both JSON API and XML-RPC API. Since XML-RPC API will be deprecated, here only uses the JSON API.

        Args:
            update(bool): If False, load package metadata from the `{self.name}.json` file in `self.data_folder` (if exists). Else, query Simple API and update data. Defaults to True.
            dump (bool): If True, dump package metadata to the `{self.name}.json` file in `self.data_folder`. Defaults to False.
            email (str): the email in `requests.get` headers. Defaults to None.
        """
        file_path = os.path.join(self.data_folder, f"{self.name}.json")

        if (not update) and os.path.exists(file_path):
            data = json.load(open(file_path))
            return list(data["releases"].keys())

        try:
            if email:
                headers["From"] = email
            r = my_get(
                PyPI.JSON_API_BASE + f"/{self.name}/json",
                headers=headers,
                timeout=timeout,
            )
            if r:
                data = r.json()
                if dump:
                    with open(safe_open(file_path), "w") as f:
                        json.dump(data, f, indent=4)
                return list(data["releases"].keys())
            return []
        except Exception as e:
            logger.error(f"{self.name}: Package metadata query error! {e}")
            return []

    def query_single_release(
        self, version: str, dump: bool = False, email: str = None, timeout: int = 60
    ):
        """Query the metadata of the given version

        Returns:
            tuple[dict, bool]: the queryed metadata and whether hit cache.

        Args:
            version (str): the version to query metadata.
            dump (bool): If True, dump package metadata to the `{version}.json` file in `self.data_folder`. Defaults to False.
            email (str): the email in `requests.get` headers. Defaults to None.
        """

        file_path = os.path.join(self.data_folder, f"{version}.json")

        if os.path.exists(file_path):
            data = json.load(open(file_path))
            logger.info(f"{file_path} already exist!")
            return data, True

        try:
            if email:
                headers["From"] = email
            r = my_get(
                PyPI.JSON_API_BASE + f"/{self.name}/{version}/json",
                headers=headers,
                timeout=timeout,
            )
            if r:
                r.raise_for_status()
                data = r.json()
                if dump:
                    with open(safe_open(file_path), "w") as f:
                        json.dump(data, f, indent=4)
                logger.info(f"{self.name} {version}: Release metadata query finished")
                return data, False
            return None, False
        except Exception as e:
            logger.error(f"{self.name} {version}: Release metadata query error! {e}")
        return None, False

    @staticmethod
    def get_maintainers(name: str, timeout=10) -> list[str]:
        maintainers = []
        url = f"https://pypi.org/project/{name}/"
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"{name}, {e}")
            return []
        soup = BeautifulSoup(response.text, "lxml")

        try:
            vertical_tabs = soup.find("div", {"class": "vertical-tabs__tabs"})
            for sidebar in vertical_tabs.find_all("div", {"class": "sidebar-section"}):
                title = sidebar.find("h3", {"class": "sidebar-section__title"})
                if title.text != "Maintainers":
                    continue
                for span in sidebar.find_all("span", {"class": "sidebar-section__maintainer"}):
                    t = span.find("span", {"class": "sidebar-section__user-gravatar-text"}).text
                    maintainers.append(t.strip(" \n"))
        except:
            logger.error(f"{name}")
        return maintainers


def batch_package_metadata(pkgs: list, metadata_folder: str, email: str = None):
    for name in pkgs:
        logger.info(f"{name}: Start processing......")
        pkg_folder = os.path.join(metadata_folder, name)

        p = Package(name=name, data_folder=metadata_folder)
        vs = p.get_versions(update=False, dump=True, email=email)
        if os.path.exists(pkg_folder) and (len(os.listdir(pkg_folder)) == len(vs) + 1):
            logger.info(f"{name}: Already queryed all the metadata")
            return
        for v in vs:
            _, hit = p.query_single_release(v, dump=True, email=email)
            if not hit:
                time.sleep(random.randint(2, 10) * 0.01)
        logger.info(f"{name}: Finish processing")


def chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main(pkgs, i, data_folder, email):
    logging.basicConfig(
        filename=f"log/collect_pypi_metadata-{i}.log",
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s %(processName)s [%(levelname)s] %(message)s",
    )
    meta_folder = os.path.join(data_folder, "metadata")
    batch_package_metadata(pkgs, metadata_folder=meta_folder, email=email)


def dump_pypi_metadata(
    data_folder: str, email: str = None, num_process: int = 1, chunk_size: int = 20
):
    # pypi = PyPI(data_folder=data_folder)
    # pkgs = pypi.list_all_packages(api="xmlrpc", update=False, dump=True)
    pkgs = json.load(open("unfinished.json"))["unfinished"][1000:1200]

    pkg_chunk = chunks(pkgs, chunk_size)

    res = Parallel(n_jobs=num_process, backend="multiprocessing")(
        delayed(main)(task, i % num_process, data_folder, email)
        for i, task in tqdm(enumerate(pkg_chunk), total=len(pkgs) / chunk_size)
    )


def update_pypi_metadata():
    pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder", type=str, required=True, help="the folder to store PyPI data"
    )
    parser.add_argument(
        "--email", type=str, default=None, help="your email for request header"
    )
    parser.add_argument(
        "--process", type=int, default=1, help="your email for request header"
    )
    parser.add_argument(
        "--chunk", type=int, default=1, help="your email for request header"
    )
    args = parser.parse_args()
    data_folder = args.folder
    email = args.email
    num_process = args.process
    chunk_size = args.chunk
    print(
        f"data_folder: {data_folder}, email: {email}, num_process: {num_process}, chunk_size: {chunk_size}"
    )

    dump_pypi_metadata(
        data_folder=data_folder,
        email=email,
        num_process=num_process,
        chunk_size=chunk_size,
    )
