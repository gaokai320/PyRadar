import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse

import requests
import validators
from bs4 import BeautifulSoup

from baselines.utils import GITHUB_RESERVED_NAMES

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


repo_pattern = re.compile(
    r"(github\.com|bitbucket\.org|gitlab\.com)/([a-z0-9_\.\-]+)/([a-z0-9_\.\-]+)",
    flags=re.I,
)

sub_pattern = re.compile(r"[^a-zA-Z0-9]")

url_cache = {}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Connection": "close",
}


def _configure_session():
    session = requests.Session()
    session.headers.update(headers)

    return session


def normalize_url(url: str):
    url = url.lower().strip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url


def find_repo_from_field(data: str) -> list[str]:
    if not data:
        return []

    urls = []
    for matchObj in repo_pattern.findall(data):
        platform, user, repo = matchObj
        if platform.lower() == "github.com" and user.lower() in GITHUB_RESERVED_NAMES:
            continue
        url = f"https://{platform}/{user}/{repo}"
        urls.append(normalize_url(url))
    return urls


def find_repo_from_webpage(url: str, session: Optional[requests.Session] = None):
    if url in url_cache:
        return url_cache[url]

    res = []
    if not session:
        session = _configure_session()
    try:
        response = session.get(url, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.findAll("a"):
            href_url = link.get("href", "")
            repo_urls = find_repo_from_field(href_url)
            if repo_urls:
                res.extend(repo_urls)
        res = list(set(res))
        url_cache[url] = res
    except requests.exceptions.HTTPError as errh:
        logger.error(f"{url}: Http Error, {errh}")
    except requests.exceptions.ConnectionError as errc:
        logger.error(f"{url}: Error Connecting, {errc}")
    except requests.exceptions.Timeout as errt:
        logger.error(f"{url}: Timeout Error, {errt}")
    except Exception as err:
        logger.error(f"{url}: OOps, Something Else, {err}")
    finally:
        return res


def validate_url(url: str) -> bool:
    url = url.strip("/").lower()

    # url points to a file
    if url.endswith((".tar.gz", ".zip", ".whl", ".tar", ".egg")):
        return False

    # exclude urls containing non ascii characters
    if not url.isascii():
        return False

    # add scheme if missing scheme to use validators
    if "//" not in url:
        url = "https://" + url
    if not validators.url(url):
        return False

    u = urlparse(url)
    if u.scheme not in ["http", "https"]:
        return False

    # if regex can not extract from the url, the url may have some problems, just skip it
    if any(
        [
            netloc in u.netloc
            for netloc in [
                "github.com",
                "bitbucket.org",
                "gitlab.com",
                "pypi.org",
                "pypi.python.org",
            ]
        ]
    ):
        return False

    return True


def github_repo_redirection(
    url: str, session: Optional[requests.Session] = None, token: str = None
) -> Optional[str]:
    forge, name, repo = url.split("/")[-3:]
    if forge != "github.com":
        logger.error(f"{url} is not a GitHub repository")
        return
    session = session or _configure_session()
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})

    while True:
        query_url = f"https://api.github.com/repos/{name}/{repo}"
        response = session.get(query_url, timeout=10)
        rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
        cur_ts = int(time.time())
        if (rate_limit_remaining == 0) and (cur_ts < rate_limit_reset):
            sleep_time = rate_limit_reset - cur_ts + 1
            time.sleep(sleep_time)
            logger.info(f"sleep {sleep_time}s...")
            continue

        if response.status_code in [403, 404, 451]:
            return
        return normalize_url(response.json().get("html_url"))


def url_redirection(
    url, session: Optional[requests.session] = None, token: str = None
) -> Optional[str]:
    session = session or _configure_session()

    forge = url.split("/")[2]
    if forge == "github.com":
        return github_repo_redirection(url, session, token)
    else:
        r = session.get(url, timeout=10)
        if r.status_code in [403, 404]:
            return
        return normalize_url(r.url)


class MetadataRetriever:
    @staticmethod
    def parse_metadata(
        metadata: dict[str, Optional[str | dict[str, str]]],
        webpage: bool = False,
        session: Optional[requests.session] = None,
        redirect: bool = False,
        token: Optional[str] = None,
    ) -> Optional[str]:
        if not metadata:
            return None
        name = metadata.get("name")
        home_page = metadata.get("home_page")
        download_url = metadata.get("download_url")
        project_urls = metadata.get("project_urls")
        description = metadata.get("description")

        url = MetadataRetriever.search_fields(home_page, download_url, project_urls)
        if url:
            if redirect:
                try:
                    url = url_redirection(url, session, token)
                except:
                    pass
            return url

        url = MetadataRetriever.search_description(name, description)
        if url:
            if redirect:
                try:
                    url = url_redirection(url, session, token)
                except:
                    pass
            return url

        if webpage:
            webpage_urls = MetadataRetriever.select_homepage_doc_url(project_urls)
            url = MetadataRetriever.search_webpage(name, webpage_urls, session=session)
            if url:
                if redirect:
                    try:
                        url = url_redirection(url, session, token)
                    except:
                        pass
                return url

    @staticmethod
    def search_fields(
        home_page: str,
        download_url: str,
        project_urls: Optional[dict[str, str]],
    ) -> Optional[str]:
        urls = find_repo_from_field(home_page)
        if urls:
            return urls[0]

        urls = find_repo_from_field(download_url)
        if urls:
            return urls[0]

        if not project_urls:
            return
        for k, v in project_urls.items():
            if any(
                [keyword in k.lower() for keyword in ["source", "code", "repository"]]
            ):
                urls = find_repo_from_field(v)
                if urls:
                    return urls[0]

        for v in project_urls.values():
            urls = find_repo_from_field(v)
            if urls:
                return urls[0]

    @staticmethod
    def search_description(name, description: str) -> Optional[str]:
        urls = find_repo_from_field(description)
        if urls:
            for url in urls:
                repo = url.rsplit("/", 1)[-1]
                sub_name = sub_pattern.sub("", name)
                sub_repo = sub_pattern.sub("", repo)
                if (sub_name in sub_repo) or (sub_repo in sub_name):
                    return url

    @staticmethod
    def select_homepage_doc_url(project_urls: Optional[dict[str, str]]):
        if not project_urls:
            return []
        res = []

        # search Homepage
        for key, value in project_urls.items():
            if key.lower().replace("-", "").replace("_", "") == "homepage":
                if validate_url(value):
                    res.append(normalize_url(value))
                    break

        # search doc
        for key, value in project_urls.items():
            if key.lower().startswith("doc") and validate_url(value):
                res.append(normalize_url(value))
                break

        return list(set(res))

    @staticmethod
    def search_webpage(
        name: str,
        webpage_urls: list[str],
        session: Optional[requests.Session] = None,
    ) -> Optional[str]:
        for webpage_url in webpage_urls:
            urls = find_repo_from_webpage(webpage_url, session)
            for url in urls:
                repo = url.rsplit("/", 1)[-1]
                sub_name = sub_pattern.sub("", name)
                sub_repo = sub_pattern.sub("", repo)
                if (sub_name in sub_repo) or (sub_repo in sub_name):
                    return url
