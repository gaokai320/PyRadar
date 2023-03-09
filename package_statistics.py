import json
import logging
from urllib.parse import urlparse

import pandas as pd
from packaging.markers import UndefinedEnvironmentName
from packaging.requirements import InvalidRequirement, Requirement
from pymongo import MongoClient
from tqdm import tqdm
import networkx as nx

tqdm.pandas()
# logger = logging.getLogger(__file__)

gh_reserved_names = json.load(open("data/reserved-names.json"))


def parse_repo_url(url: str):
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if netloc in ["github.com", "bitbucket.org", "gitlab.com"]:
            path = parsed.path.strip("./").split("/")
            if len(path) >= 2:
                if (netloc == "github.com") and (path[0].lower() in gh_reserved_names):
                    return None
                res = f"https://{netloc}/{path[0].lower()}/{path[1].lower()}"
                return res
    except:
        return None


def url_parser(data):
    urls = {}
    home_page = parse_repo_url(data["home_page"])
    if home_page:
        urls[home_page] = urls.get(home_page, 0) + 1
    download_url = parse_repo_url(data["download_url"])
    if download_url:
        urls[download_url] = urls.get(download_url, 0) + 1

    if data["project_urls"]:
        for v in data["project_urls"].values():
            tmp = parse_repo_url(v)
            if tmp:
                urls[tmp] = urls.get(tmp, 0) + 1
    if urls:
        return sorted(urls.items(), key=lambda x: x[1])[-1][0]


def get_package_repo_urls():
    pypi_db = MongoClient("127.0.0.1", 27017)["pypi"]
    release_metadata = pypi_db["release_metadata"]

    df = pd.DataFrame(
        release_metadata.find(
            {},
            projection={
                "_id": 0,
                "name": 1,
                "version": 1,
                "home_page": 1,
                "download_url": 1,
                "project_urls": 1,
                "upload_time": 1,
            },
        )
    )
    df["name"] = df["name"].str.lower()
    df.loc[:, "repository"] = df[
        ["home_page", "download_url", "project_urls"]
    ].progress_apply(url_parser, axis=1)

    print("Number of packages: ", len(df["name"].unique()))
    print(
        "Number of packages with repositories: ",
        len(df[pd.notna(df["repository"])]["name"].unique()),
    )
    print("Number of releases: ", len(df))
    print("Number of releases with repositories: ", len(df[pd.notna(df["repository"])]))

    df.to_csv("data/package_repo_urls.csv", index=False)

    tmp = pd.DataFrame({"name": df["name"].unique(), "specify_repo": False})
    pkgs_with_repos = df[pd.notna(df["repository"])]["name"].unique()
    tmp.loc[tmp["name"].isin(pkgs_with_repos), "specify_repo"] = True
    tmp.to_csv("data/package_specify_repos.csv", index=False)


def get_yearly_data():
    df = pd.read_csv("data/package_repo_urls.csv")
    df["upload_time"] = pd.to_datetime(df["upload_time"])
    res = []
    for year in range(2006, 2024):
        data = df[df["upload_time"].dt.year < year]
        total = len(data["name"].unique())
        has_repos = len(data[pd.notna(data["repository"])]["name"].unique())
        res.append([year - 1, total, has_repos])
    res = pd.DataFrame(res, columns=["year", "total", "specify_repo"])
    res["ratio"] = res["specify_repo"] / res["total"]
    res = res.set_index("year")
    res.to_csv("data/yearly_package_count.csv")


def get_downloads_data():
    package_downloads = []
    with open("data/package_downloads_last30days.json") as f:
        for line in f:
            data = json.loads(line.strip("\n"))
            package_downloads.append(
                [data["project"].lower(), int(data["num_downloads"])]
            )

    package_downloads = pd.DataFrame(package_downloads, columns=["name", "downloads"])

    df = pd.read_csv("data/package_specify_repos.csv")
    pkgs_with_repos = df[df["specify_repo"]]["name"]
    package_downloads["specify_repo"] = False
    package_downloads.loc[
        package_downloads["name"].isin(pkgs_with_repos), "specify_repo"
    ] = True
    package_downloads.to_csv("data/downloads.csv", index=False)


def parse_requirement(requirement_str: str):
    try:
        req = Requirement(requirement_str)
    except InvalidRequirement:
        logging.error("InvalidRequirement: {}".format(requirement_str))
        return
    except:
        logging.error("ParseError: {}".format(requirement_str))
        return
    name, marker = req.name, req.marker
    extra = False
    if marker is not None:
        try:
            marker.evaluate()
        except UndefinedEnvironmentName:
            extra = True
        except:
            logging.error("MarkerError: {}".format(marker))
            extra = False
    return name.lower(), extra


def parse_release_metadata():
    pypi_db = MongoClient("127.0.0.1", 27017)["pypi"]
    release_metadata = pypi_db["release_metadata"]

    deps = []
    for doc in tqdm(
        release_metadata.find({}, {"name": 1, "_id": 0, "requires_dist": 1})
    ):
        name = doc.get("name", "")
        requires_dist = doc.get("requires_dist", [])
        if requires_dist:
            for req in requires_dist:
                res = parse_requirement(req)
                if res is not None:
                    dependency, extra = res
                    deps.append([name, dependency, extra])
    deps = pd.DataFrame(deps, columns=["name", "dependency", "extra"])
    deps = deps.drop_duplicates()
    deps.to_csv("data/dependency_graph.csv", index=False)


def get_dependents_data():
    deps_df = pd.read_csv("data/dependency_graph.csv")
    deps_df = deps_df[~deps_df["extra"]][["name", "dependency"]]
    deps_df["name"] = deps_df["name"].str.lower()
    deps_df["dependency"] = deps_df["dependency"].str.lower()
    deps_df = deps_df.drop_duplicates()

    G = nx.DiGraph()
    G.add_edges_from(deps_df.values)
    G = G.reverse()
    print(f"Number of nodes: {G.number_of_nodes()}")
    print(f"Number of edges: {G.number_of_edges()}")

    deps_cnt = []
    df = pd.read_csv("data/package_specify_repos.csv")
    pkgs = df["name"].str.lower()

    for p in tqdm(pkgs):
        try:
            direct = len(list(G.neighbors(p)))
            indirect = len(nx.descendants(G, p))
            deps_cnt.append([p, direct, indirect])
        except:
            deps_cnt.append([p, 0, 0])

    deps_cnt = pd.DataFrame(deps_cnt, columns=["name", "direct", "indirect"])
    deps_cnt["specify_repo"] = False
    pkgs_with_repos = df[df["specify_repo"]]["name"]
    deps_cnt.loc[deps_cnt["name"].isin(pkgs_with_repos), "specify_repo"] = True
    deps_cnt.to_csv("data/dependents_count.csv", index=False)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.INFO,
        filename="log/package_statistics.log",
        filemode="w",
    )
    get_package_repo_urls()
    get_yearly_data()
    get_downloads_data()
    parse_release_metadata()
    get_dependents_data()
