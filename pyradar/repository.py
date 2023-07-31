import configparser
import json
import logging
import math
import os
import shutil
from functools import cached_property
from typing import Optional
from urllib.parse import urljoin, urlparse

from git import GitCommandError, GitDB, InvalidGitRepositoryError, Repo
from tqdm import tqdm

from pyradar.utils import CacheDict

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

failed_urls = []


def assemble_repo_folder(url: str, base_folder: str) -> str:
    """Assemble the folder path for a repository based on its remote url.

    Args:
        url (str): the remote repository url
        base_folder (str): the folder that stores repository and relevant data.

    Returns:
        str: the folder path for the repository
    """
    # if url.endswith(".git"):
    #     url = url[:-4]
    parsed = urlparse(url)
    return os.path.join(
        base_folder, "repository", parsed.netloc, parsed.path.strip("/")
    )


def normalize_git_url(url: str):
    if url.startswith("https://"):
        return url
    elif url.startswith("git@"):
        return "https://" + url.rsplit("@", 1)[1].replace(":", "/")
    elif url.startswith("git://"):
        return "https://" + url[6:]


class Repository:
    def __init__(
        self,
        url: str,
        base_folder: str,
        chunk_size: int = 1000,
        tree_cache_size: int = 30000,
    ) -> None:
        """Create a wrapped `gitpython.Repo` object.

        Args:
            url (str): the remote repository url
            base_folder (str): the folder that stores repository and relevant data.
        """
        self.url = url.strip("/")
        # if self.url.startswith("git@"):
        #     self.url = "https://" + self.url.split("@", 1)[1]
        self.base_folder = base_folder
        self.data_folder = assemble_repo_folder(url, base_folder)
        self.repo_path = os.path.join(self.data_folder, "repo")
        self.repo = self.safe_open(self.repo_path, self.url)
        self.submodule_flag = True
        self.chunk_size = chunk_size
        self.tree_cache_size = tree_cache_size

    # @staticmethod
    def safe_open(self, repo_path: str, url: str) -> Optional[Repo]:
        """Open a repository from `repo_path`. If not a valid git repository, clone it from `url`.

        Args:
            repo_path (str): the path to the repository
            url (str): the url of the remote repository

        Raises:
            FileNotFoundError: if failed to open the repository

        Returns:
            Optional[Repo]: the git.Repo object
        """
        # We only consider GitHub, GitLab, Bitbucket repositories.
        if not any(
            [loc in url for loc in ["github.com", "gitlab.com", "bitbucket.org"]]
        ):
            return None
        repo = None
        # try to open the repository
        if os.path.exists(repo_path):
            try:
                repo = Repo(repo_path, odbt=GitDB)
                logger.info(f"Load repository from {repo_path} successfully")
            except InvalidGitRepositoryError:
                logger.error(f"{repo_path} is not a valid git repository")
                shutil.rmtree(repo_path)

        # if not a valid git repository, clone it
        if not repo:
            if url.startswith("https://"):
                segments = url[8:].split("/")
                if len(segments) != 3:
                    return None
                url = f"git@{segments[0]}:{segments[1]}/{segments[2]}"
            try:
                repo = Repo.clone_from(url, repo_path, odbt=GitDB)
                logger.info(f"Clone repository from {url} to {repo_path} successfully")
            except GitCommandError as e:
                error_msg = e.stderr
                for line in e.stderr.split("\n"):
                    if line.startswith("fatal"):
                        error_msg = line.strip("\n")
                logger.error(
                    f"{self.repo_path}: Failed to clone repository {url}. {error_msg}"
                )
                # raise FileNotFoundError(
                #     f"Fail to clone repository from {url} to {repo_path}"
                # )
        return repo

    @cached_property
    def object_shas(self) -> dict[str, list[str]]:
        """use the command `git cat-file --batch-check --batch-all-objects --unordered` to list all git objects"""
        logger.info("start listing all git objects")
        object_shas = {"commit": [], "tree": [], "blob": [], "tag": []}
        if self.repo:
            try:
                output = self.repo.git.cat_file(
                    batch_check=True, batch_all_objects=True, unordered=True
                ).split("\n")

                for obj in output:
                    if len(obj.split(" ")) < 3:
                        break
                    obj_sha, obj_type, _ = obj.split(" ")
                    if obj_type in ["commit", "tree", "blob", "tag"]:
                        object_shas[obj_type].append(obj_sha)
            except Exception as e:
                logger.error(f"Object Shas error of {self.repo_path}: {e}")
        logger.info("finish listing all git objects")
        return object_shas

    @cached_property
    def tree_shas(self) -> list[str]:
        """a list of all tree object shas"""
        return self.object_shas["tree"]

    @cached_property
    def commit_shas(self) -> list[tuple[str, int]]:
        """a list of all commit object shas"""
        commits = []
        for commit in self.object_shas["commit"]:
            ts = self.repo.commit(commit).authored_date
            commits.append((commit, ts))
        commits.sort(key=lambda x: x[1])
        return commits

    @cached_property
    def tag_shas(self) -> dict[str, str]:
        """a dict of tag object names (e.g., v0.1.0) with the commit shas they point to"""
        res = {}
        if self.repo:
            for tag in self.repo.tags:
                res[tag.name] = tag.commit.hexsha
        return res

    @staticmethod
    def parse_gitmodules(content: str, base_url: str) -> dict[str, str]:
        """parse the .gitmodules file and return a dict of submodule paths and corresponding urls

        Args:
            content (str): the content of the .gitmodules file
        """
        config = configparser.ConfigParser()
        sms = {}
        try:
            config.read_string(content)
            for section in config.sections():
                path = config[section]["path"]
                url = config[section]["url"].split("\n")[0]
                if url.startswith("."):
                    url = urljoin(base_url, url)
                sms[path] = url
        except:
            pass
        return sms

    def traverse(
        self,
        tree_hexsha: str,
        repo: Repo,
        root_path: str = "",
        sms: dict = {}
        # self, root_tree: git.Tree, root_path="", sms: dict = {}
    ) -> list[tuple[str, str]]:
        """traverse the tree object and return a list of (filename, sha) pairs

        Args:
            root_tree (git.Tree): the root tree object to traverse
            root_path (str, optional): the root path of the tree. Defaults to "".
            base_folder (str, optional): the folder that stores repository and relevant data. Defaults to None.
            sms (str): a dict of submodules with submodule path and url.

        Returns:
            list[tuple[str, str]]: a list containing the filenames and corresponding hex shas.
        """

        # if the tree is already traversed, return the cached result
        files = self.tree_cache.get(tree_hexsha, [])
        if files:
            # logger.info(f"tree {tree_hexsha} is already traversed")
            return files

        logger.info(f"traversing tree {tree_hexsha} in repository {repo}")
        # logger.error(f"{tree_hexsha}")

        # # unchecked stores the tree objects that are not traversed yet
        # unchecked = [(root_tree, "")]
        # while len(unchecked) > 0:
        #     tree, path = unchecked.pop()
        for item in repo.git.cat_file("-p", tree_hexsha).split("\n"):
            if item == "":
                continue
            _, obj_type, sha_name = item.split(" ", 2)
            sha, name = sha_name.split("\t", 1)

            # if the object is a blob, add it to the list
            if obj_type == "blob":
                files.append((sha, os.path.join(root_path, name)))

                # only consider .gitmodules file in the root folder
                if (not sms) and (name == ".gitmodules"):
                    gitmodules_content = repo.git.cat_file("-p", sha)
                    # print(tree_hexsha)
                    # print(gitmodules_content)
                    sms = Repository.parse_gitmodules(gitmodules_content, self.url)
                    # only print once
                    if self.submodule_flag:
                        logger.error(f"Submodules detected for {self.repo_path}")
                        self.submodule_flag = False

            # if the object is a tree, traverse it
            elif obj_type == "tree":
                # print(sha)
                tree_files = self.traverse(
                    sha, repo, os.path.join(root_path, name), sms
                )
                files.extend(tree_files)

            # if the object is a commit (i.e., submodule), traverse its root tree.
            elif obj_type == "commit":
                sm_path = os.path.join(root_path, name)
                logger.info(f"entering submodule {sm_path}")
                if sm_path in sms:
                    url = sms[sm_path]

                    # # if base_folder is not specified, try to get it from the environment variable DATA_HOME
                    # if base_folder is None:
                    #     base_folder = os.environ.get("DATA_HOME", None)
                    # # if the DATA_HOME environment variable is not set, raise an error
                    # if base_folder is None:
                    #     raise FileNotFoundError("base_folder is not specified")

                    # traverse the submodule
                    # print(url)
                    url = normalize_git_url(url)
                    if not url:
                        continue
                    # print(url)
                    repo_path = os.path.join(
                        assemble_repo_folder(url, self.base_folder), "repo"
                    )
                    if url not in failed_urls:
                        tmp_repo = self.safe_open(repo_path, url)
                        if tmp_repo:
                            try:
                                tree_hash = (
                                    tmp_repo.git.cat_file("-p", sha)
                                    .split("\n")[0]
                                    .split(" ")[1]
                                )
                                sm_files = self.traverse(
                                    tree_hash, tmp_repo, sm_path, {}
                                )
                                files.extend(sm_files)
                            except Exception as e:
                                logger.error(
                                    f"Submodule error of {self.repo_path}: {sha} not in submodule {sm_path}: {url}"
                                )
                        else:
                            failed_urls.append(url)

        # tmp = [(sha, os.path.join(root_path, path)) for sha, path in files]
        self.tree_cache[tree_hexsha] = files
        return files

    def snapshot(self, commit_sha: str) -> list[tuple[str, str]]:
        """get the folder structure of a commit

        Args:
            commit_sha (str): the commit sha

        Returns:
            list[tuple[str, str]]: a list containing the filenames and corresponding hex shas.
        """
        tree_hash = (
            self.repo.git.cat_file("-p", commit_sha).split("\n")[0].split(" ")[1]
        )
        return self.traverse(
            tree_hexsha=tree_hash,
            repo=self.repo,
            root_path="",
            sms={},
        )

    def traverse_all(self, disable_pbar: bool = True):
        """
        traverse all commits and save the mapping and blob information to json files
        """
        snapshot_path = os.path.join(self.data_folder, "snapshot-{}.json")
        index_path = os.path.join(self.data_folder, "index.json")
        # b2c_path = os.path.join(self.data_folder, "bid2cid.json")
        num_chunks = math.ceil(len(self.commit_shas) / self.chunk_size)
        # print(len(self.commit_shas), self.chunk_size, num_chunks)

        # already traversed completely
        if os.path.exists(snapshot_path.format(num_chunks - 1)):
            return

        # LRU cache tree traverse results to speed up
        self.tree_cache = CacheDict(cache_len=self.tree_cache_size)

        blobs = set()
        filenames = set()
        edges = {}

        chunk_id = 0

        for i, commit_ts in enumerate(
            tqdm(self.commit_shas, ascii=" >=", unit="commit", disable=disable_pbar),
            start=1,
        ):
            # for i, commit_ts in enumerate(self.commit_shas, start=1):
            commit = commit_ts[0]
            logger.info(f"start listing commit {commit}")

            # print(commit)
            edges[commit] = self.snapshot(commit)
            for blob_sha, blob_name in edges[commit]:
                blobs.add(blob_sha)
                filenames.add(blob_name)

            # dump edges to snapshot.json file every `self.chunk_size` commits in case of memory explosion :(
            if i % self.chunk_size == 0:
                with open(snapshot_path.format(chunk_id), "w") as f:
                    json.dump(edges, f)
                chunk_id += 1
                edges = {}
            # logger.info(f"finish listing commit {commit}")

        # dump the remaining edges if any
        if len(edges) > 0:
            with open(snapshot_path.format(chunk_id), "w") as f:
                json.dump(edges, f)
            chunk_id += 1
            edges = {}

        # collect tree_cache in case of
        self.tree_cache = CacheDict()
        # for space efficiency, we map the blob shas, commit shas, and filenames to index
        # and replace the original shas with the indices in the snapshots
        logger.info(f"start dumping to index.json")
        blobs = list(blobs)
        blobs.sort()
        indices = {}
        indices["blob"] = {sha: i for i, sha in enumerate(blobs)}
        indices["commit"] = {
            sha: [i, ts] for i, (sha, ts) in enumerate(self.commit_shas)
        }
        filenames = list(filenames)
        filenames.sort()
        indices["filename"] = {fn: i for i, fn in enumerate(filenames)}
        with open(index_path, "w") as outf:
            json.dump(indices, outf, indent=4)
        logger.info(f"finish dumping to index.json")

        logger.info("start dumping to snapshot.json")
        for i in range(chunk_id):
            filepath = snapshot_path.format(i)
            edges = json.load(open(filepath))
            indexed_edges = {}
            for c, b_fn in edges.items():
                cid = indices["commit"][c][0]
                indexed_edges[cid] = [
                    [indices["blob"][b], indices["filename"][fn]] for b, fn in b_fn
                ]
            with open(filepath, "w") as f:
                json.dump(indexed_edges, f)
        logger.info("finish dumping to snapshot.json")

    @cached_property
    def blob_shas(self) -> list[str]:
        """return a list of all blob shas"""

        nodes_path = os.path.join(self.data_folder, "index.json")
        if not os.path.exists(nodes_path):
            logger.info(f"index.json not exists, start traversing all commits")
            self.traverse_all()
        logger.info(f"loading from index.json")
        nodes = json.load(open(nodes_path))
        return list(nodes["blob"].keys())

    def read_blob_content(self, blob_sha: str) -> str:
        """read the content of a blob object

        Args:
            blob_sha (str): the blob sha

        Returns:
            str: the content of the blob object
        """
        return self.repo.git.cat_file("-p", blob_sha)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str)
    args = parser.parse_args()
    url = args.url
    print(url)
    repo = Repository(url, "/data/kyle/pypi_data")
    repo.traverse_all(disable_pbar=False)
