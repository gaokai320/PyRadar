import configparser
import json
import logging
import os
import shutil
from functools import cached_property
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import git
from git import GitCommandError, GitDB, InvalidGitRepositoryError, Repo
from tqdm import tqdm

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def assemble_repo_folder(url: str, base_folder: str) -> str:
    """Assemble the folder path for a repository based on its remote url.

    Args:
        url (str): the remote repository url
        base_folder (str): the folder that stores repository and relevant data.

    Returns:
        str: the folder path for the repository
    """
    parsed = urlparse(url)
    return os.path.join(
        base_folder, "repository", parsed.netloc, parsed.path.strip("/")
    )


class Repository:
    def __init__(self, url: str, base_folder: str) -> None:
        """Create a wrapped `gitpython.Repo` object.

        Args:
            url (str): the remote repository url
            base_folder (str): the folder that stores repository and relevant data.
        """
        self.url = url.strip("/")
        self.data_folder = assemble_repo_folder(url, base_folder)
        self.repo_path = os.path.join(self.data_folder, "repo")
        self.repo = Repository.safe_open(self.repo_path, self.url)
        self.tree_cache = {}

    @staticmethod
    def safe_open(repo_path: str, url: str) -> Optional[Repo]:
        """Open a repository from `repo_path`. If not a valid git repository, clone it from `url`.

        Args:
            repo_path (str): the path to the repository
            url (str): the url of the remote repository

        Raises:
            FileNotFoundError: if failed to open the repository

        Returns:
            Optional[Repo]: the git.Repo object
        """
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
            try:
                repo = Repo.clone_from(url, repo_path, odbt=GitDB)
                logger.info(f"Clone repository from {url} to {repo_path} successfully")
            except GitCommandError as e:
                logger.error(f"Failed to clone repository {url}. {e.stderr}")
                raise FileNotFoundError(
                    f"Fail to clone repository from {url} to {repo_path}"
                )
        return repo

    @cached_property
    def object_shas(self) -> Dict[str, List[str]]:
        """use the command `git cat-file --batch-check --batch-all-objects --unordered` to list all git objects"""
        logger.info("start listing all git objects")
        object_shas = {"commit": [], "tree": [], "blob": [], "tag": []}
        if self.repo:
            try:
                output = self.repo.git.cat_file(
                    batch_check=True, batch_all_objects=True, unordered=True
                ).split("\n")

                for obj in output:
                    obj_sha, obj_type, _ = obj.split(" ")
                    if obj_type in ["commit", "tree", "blob", "tag"]:
                        object_shas[obj_type].append(obj_sha)
            except Exception as e:
                logger.error(e)
        logger.info("finish listing all git objects")
        return object_shas

    @cached_property
    def tree_shas(self) -> List[str]:
        """a list of all tree object shas"""
        return self.object_shas["tree"]

    @cached_property
    def commit_shas(self) -> List[str]:
        """a list of all commit object shas"""
        return self.object_shas["commit"]

    @cached_property
    def tag_shas(self) -> Dict[str, str]:
        """a dict of tag object names (e.g., v0.1.0) with the commit shas they point to"""
        res = {}
        for tag in self.repo.tags:
            res[tag.name] = tag.commit.hexsha
        return res

    @staticmethod
    def parse_gitmodules(content: str) -> Dict[str, str]:
        """parse the .gitmodules file and return a dict of submodule paths and corresponding urls

        Args:
            content (str): the content of the .gitmodules file
        """
        config = configparser.ConfigParser()
        config.read_string(content)
        sms = {}
        for section in config.sections():
            path = config[section]["path"]
            url = config[section]["url"]
            sms[path] = url
        return sms

    def traverse(
        self, root_tree: git.Tree, root_path="", base_folder: str = None, sms: dict = {}
    ) -> List[Tuple[str, str]]:
        """traverse the tree object and return a list of (filename, sha) pairs

        Args:
            root_tree (git.Tree): the root tree object to traverse
            root_path (str, optional): the root path of the tree. Defaults to "".
            base_folder (str, optional): the folder that stores repository and relevant data. Defaults to None.
            sms (str): a dict of submodules with submodule path and url.

        Returns:
            List[Tuple[str, str]]: a list containing the filenames and corresponding hex shas.
        """

        # if the tree is already traversed, return the cached result
        files = self.tree_cache.get(root_tree.hexsha, [])
        if files:
            logger.info(f"tree {root_tree.hexsha} is already traversed")
            return files

        repo = root_tree.repo
        logger.info(f"traversing tree {root_tree.hexsha} in repository {repo}")

        # # unchecked stores the tree objects that are not traversed yet
        # unchecked = [(root_tree, "")]
        # while len(unchecked) > 0:
        #     tree, path = unchecked.pop()
        for item in repo.git.cat_file("-p", root_tree.hexsha).split("\n"):
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
                    sms = Repository.parse_gitmodules(gitmodules_content)
                    logger.info(f"submodules detected: {sms}")

            # if the object is a tree, traverse it
            elif obj_type == "tree":
                tree_files = self.traverse(
                    repo.tree(sha), os.path.join(root_path, name), base_folder, sms
                )
                files.extend(tree_files)

            # if the object is a commit (i.e., submodule), traverse its root tree.
            elif obj_type == "commit":
                sm_path = os.path.join(root_path, name)
                logger.info(f"entering submodule {sm_path}")
                if sm_path in sms:
                    url = sms[sm_path]

                    # if base_folder is not specified, try to get it from the environment variable DATA_HOME
                    if base_folder is None:
                        base_folder = os.environ.get("DATA_HOME", None)
                    # if the DATA_HOME environment variable is not set, raise an error
                    if base_folder is None:
                        raise FileNotFoundError("base_folder is not specified")

                    # traverse the submodule
                    repo_path = os.path.join(
                        assemble_repo_folder(url, base_folder), "repo"
                    )
                    tmp_repo = Repository.safe_open(repo_path, url)
                    sm_files = self.traverse(
                        tmp_repo.commit(sha).tree, sm_path, base_folder, {}
                    )
                    files.extend(sm_files)

        # tmp = [(sha, os.path.join(root_path, path)) for sha, path in files]
        self.tree_cache[root_tree.hexsha] = files
        return files

    def snapshot(self, commit_sha: str) -> List[Tuple[str, str]]:
        """get the folder structure of a commit

        Args:
            commit_sha (str): the commit sha

        Returns:
            List[Tuple[str, str]]: a list containing the filenames and corresponding hex shas.
        """
        commit = self.repo.commit(commit_sha)
        return self.traverse(
            root_tree=commit.tree,
            root_path="",
            base_folder=os.environ.get("DATA_HOME", None),
            sms={},
        )

    def traverse_all_commits(self):
        """
        traverse all commits and save the mapping and blob information to json files
        """

        graph_path = os.path.join(self.data_folder, "b2fc.json")
        nodes_path = os.path.join(self.data_folder, "idx2sha.json")
        if os.path.exists(graph_path):
            return

        blobs = []
        commits = []
        edges = []

        for commit in tqdm(self.commit_shas, ascii=" >="):
            logger.info(f"start listing commit {commit}")
            ts = self.repo.commit(commit).authored_date
            commits.append((commit, ts))

            # different files may have the same blob sha
            tmp = {}
            for blob_sha, blob_name in self.snapshot(commit):
                blobs.append(blob_sha)
                tmp[blob_sha] = tmp.get(blob_sha, [])
                tmp[blob_sha].append(blob_name)
            for blob_sha, blob_names in tmp.items():
                edges.append((commit, blob_sha, blob_names))
            logger.info(f"finish listing commit {commit}")

        # for space efficiency, we map the blob shas and commit shas to index
        # and replace the original shas with the indices in the graph
        logger.info(f"start dumping nodes to idx2sha.json")
        blobs = list(set(blobs))
        nodes = {}
        nodes["blob"] = {sha: i for i, sha in enumerate(blobs)}
        num_blobs = len(blobs)
        nodes["commit"] = {
            sha: (num_blobs + i, ts) for i, (sha, ts) in enumerate(commits)
        }
        with open(nodes_path, "w") as outf:
            json.dump(nodes, outf, indent=4)
        logger.info(f"finish dumping nodes to idx2sha.json")

        logger.info("start dumping to b2fc.json")
        # {blob_sha: {filename: [commmit_shas], ....}}
        minified_edges = {
            i: {} for i in range(num_blobs)
        }  # type: Dict[int, Dict[str, List[int]]]
        for c, b, fs in edges:
            bid = nodes["blob"][b]
            cid = nodes["commit"][c][0]
            for f in fs:
                minified_edges[bid][f] = minified_edges[bid].get(f, [])
                minified_edges[bid][f].append(cid)
        with open(graph_path, "w") as outf:
            json.dump(minified_edges, outf)
        logger.info("finish dumping to b2fc.json")

    @cached_property
    def blob_shas(self) -> List[str]:
        """return a list of all blob shas"""

        nodes_path = os.path.join(self.data_folder, "idx2sha.json")
        if not os.path.exists(nodes_path):
            logger.info(f"idx2sha.json not exists, start traversing all commits")
            self.traverse_all_commits()
        logger.info(f"loading from idx2sha.json")
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
