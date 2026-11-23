import json
import logging
import os
import re
import time
from collections import Counter
from functools import cached_property
from typing import Optional

import requests
from Levenshtein import ratio
from woc.local import WocMapsLocal

from pyradar.utils import DistReader, download, normalize_url, restore_url

woc = WocMapsLocal(profile_path="wocprofile.json")
bad_blobs = json.load(open("pyradar/bad_blobs.json"))
logger = logging.getLogger(__name__)

ACCEPTED_EXTENSIONS = (".tar.gz", ".zip", ".whl", ".egg")
RELEASE_JSON_API_ENDPOINT = "https://pypi.org/pypi/{name}/{version}/json"

JSON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
}
sub_pattern = re.compile(r"[^a-zA-Z0-9]")


def query_b2tac(sha: str):
    try:
        cs = []
        for _, c, _ in woc.get_values("bb2cf", sha):
            ts = woc.show_content("commit", c)[2][1]
            cs.append((c, ts))
        return sorted(cs, key=lambda x: x[1])[0][0]
    except:
        return


def query_c2p(sha: str):
    try:
        return woc.get_values("c2p", sha)
    except:
        return []


def query_b2p(sha: str):
    cmt = query_b2tac(sha)
    if cmt:
        return query_c2p(cmt)

    return []


def query_p2P(proj: str):
    try:
        return woc.get_values("p2P", proj)[0]
    except:
        return proj


def query_sdist(name: str, version: str, packagetype: str = "sdist"):
    url = RELEASE_JSON_API_ENDPOINT.format(name=name, version=version)
    try:
        with requests.Session() as s:
            s.headers.update(JSON_HEADERS)
            for dist in s.get(url).json().get("urls"):
                if dist["packagetype"] == packagetype:
                    return dist
    except:
        return


def get_most_common(data: dict[str, int], n: int = 10):
    if not data:
        return []
    res = []
    prior = -1
    cnt = 0
    for k, v in data.items():
        if prior != v:
            prior = v
            cnt += 1
        if cnt > 2:
            break
        if v == prior:
            res.append((k, v))

    return res[:n]


def defork(url: str, session: Optional[requests.Session] = None):
    if not url:
        return
    if not url.startswith("https://github.com/"):
        return url
    user, repo = url.split("/", 4)[3:]
    api_point = f"https://api.github.com/repos/{user}/{repo}"
    if not session:
        session = requests.Session()
        session.headers.update(headers)
    while True:
        response = session.get(api_point)
        rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
        rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
        # print(rate_limit_remaining, rate_limit_reset)

        cur_ts = int(time.time())
        if (rate_limit_remaining == 0) and (cur_ts < rate_limit_reset):
            sleep_time = rate_limit_reset - cur_ts + 1
            time.sleep(sleep_time)
            continue
        if response.status_code != 200:
            return

        data = response.json()
        if "source" in data:
            return normalize_url(data["source"].get("html_url", ""))
        return normalize_url(data.get("html_url", ""))


def select_final(
    py_candidates: dict[str, int],
    n: int = 10,
    session: Optional[requests.Session] = None,
):
    most_common = get_most_common(py_candidates, n)
    if not most_common:
        return
    res = []
    for woc_uri, _ in most_common:
        deforked_url = defork(restore_url(woc_uri), session)
        if deforked_url:
            res.append(deforked_url)
    if not res:
        return
    return Counter(res).most_common(1)[0][0]


class WoCRetrieverV2:
    def __init__(
        self,
        name: str,
        version: str,
        base_folder: str,
        token: Optional[str] = None,
        packagetype: str = "sdist",
        translate_newline: bool = True,
    ) -> None:
        self.name = name
        self.version = version
        self.base_folder = base_folder
        self.packagetype = packagetype
        self.translate_newline = translate_newline
        self.session = requests.Session()
        self.session.headers.update(headers)
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    @cached_property
    def fileshas(self) -> list[tuple[str, str]]:
        res = []
        sdist = query_sdist(self.name, self.version, self.packagetype)
        if sdist:
            url = sdist["url"]
            filename = sdist["filename"]
            if not filename.endswith(ACCEPTED_EXTENSIONS):
                return res
            save_path = os.path.join(
                self.base_folder, "distribution", self.name, filename
            )
            download(url, save_path)
            for fname, fsha in DistReader(
                save_path, self.translate_newline
            ).file_shas():
                res.append((fname, fsha))
        return res

    def get_candidates(self, blob_uniqueness: int = 500):
        py_candidates = {}
        setup_candidates = set()
        num_pyfiles = 0
        tmp_p2P = {}
        for name, sha in self.fileshas:
            if sha in bad_blobs:
                continue

            if os.path.basename(name) == "pyproject.toml":
                projs = query_b2p(sha)
                if len(projs) > blob_uniqueness:
                    continue
                for p in projs:
                    setup_candidates.add(p)
                    if tmp_p2P.get(p, None):
                        setup_candidates.add(tmp_p2P[p])
                    else:
                        P = query_p2P(p)
                        tmp_p2P[p] = P
                        setup_candidates.add(P)
                continue

            if name.endswith(".py"):
                projs = query_b2p(sha)
                if len(projs) > blob_uniqueness:
                    continue
                num_pyfiles += 1
                tmp = set()
                for p in projs:
                    tmp.add(p)
                    if not (p in tmp_p2P):
                        P = query_p2P(p)
                        tmp_p2P[p] = P
                    tmp.add(tmp_p2P[p])
                for p in tmp:
                    py_candidates[p] = py_candidates.get(p, 0) + 1
                    if os.path.basename(name) == "setup.py":
                        setup_candidates.add(p)

        py_candidates = sorted(py_candidates.items(), key=lambda x: x[1], reverse=True)
        py_candidates = {k: v for k, v in py_candidates}
        return num_pyfiles, py_candidates, list(setup_candidates)

    def get_final(self, n: int = 10, thresh: float = 0.6) -> Optional[str]:
        _, py_candidates, _ = self.get_candidates()
        final = select_final(py_candidates, n=n, session=self.session)
        if final is None:
            return None
        user, repo = final.split("/")[-2:]
        ratio1 = ratio(sub_pattern.sub("", self.name), sub_pattern.sub("", repo))
        ratio2 = ratio(sub_pattern.sub("", self.name), sub_pattern.sub("", user + repo))
        if max(ratio1, ratio2) >= thresh:
            return final
