import json
import logging
import os
import shutil
from functools import cached_property
from typing import Dict, List, Tuple

from tqdm import tqdm
from git import GitCommandError, InvalidGitRepositoryError, Repo, GitDB

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Repository:
    def __init__(self, url: str, data_folder: str) -> None:
        """Create a wrapped `gitpython.Repo` object.

        Args:
            url (str): the remote repository url
            data_folder (str): the folder that stores repository data. The folder will include a `repo` folder with the cloned repository and a `commit_snapshots.json` file with the folder structure information of each commit.
        """
        self.url = url.strip("/")
        self.data_folder = data_folder
        self.repo_path = os.path.join(self.data_folder, "repo")
        self.repo = None

        # try to open the repository
        if os.path.exists(self.repo_path):
            try:
                self.repo = Repo(self.repo_path, odbt=GitDB)
                logger.info(f"Load repository from {self.repo_path} successfully")
            except InvalidGitRepositoryError as e:
                logger.error(f"{self.repo_path} is not a valid git repository")
                shutil.rmtree(self.repo_path)

        # if not a valid git repository, clone it
        if not self.repo:
            try:
                self.repo = Repo.clone_from(
                    self.url, self.repo_path, odbt=GitDB, recurse_submodules=True
                )
                logger.info(
                    f"Clone repository from {self.url} to {self.repo_path} successfully"
                )
            except GitCommandError as e:
                logger.error(f"Failed to clone repository {self.url}. {e.stderr}")
                raise FileNotFoundError(
                    f"Fail to clone repository from {self.url} to {self.repo_path}"
                )

    @cached_property
    def object_shas(self) -> Dict[str, List]:
        """a dict containing shas of all commit, tree, and blob objects."""
        logger.info("start listing all git objects")
        object_shas = {"commit": [], "tree": [], "blob": []}
        if self.repo:
            try:
                output = self.repo.git.cat_file(
                    batch_check=True, batch_all_objects=True, unordered=True
                ).split("\n")

                for obj in output:
                    obj_sha, obj_type, _ = obj.split(" ")
                    if obj_type in ["commit", "tree", "blob"]:
                        object_shas[obj_type].append(obj_sha)
            except Exception as e:
                logger.error(e)
        logger.info("finish listing all git objects")
        return object_shas

    @cached_property
    def tree_shas(self) -> List:
        """a sha list of all tree objects"""
        return self.object_shas["tree"]

    @cached_property
    def commit_shas(self) -> List:
        """ "a sha list of all commit objects"""
        return self.object_shas["commit"]

    @cached_property
    def blob_shas(self) -> List:
        """a sha list of all blob objects"""

        # this will also change object_shas due to Python's reference mechanism, but it's fine.
        res = self.object_shas["blob"]
        for sm in self.repo.submodules:
            logger.info(f"listing blobs in submodule {sm.path}")
            try:
                r = Repo(os.path.join(self.repo_path, sm.path), odbt=GitDB)
                output = r.git.cat_file(batch_check=True, batch_all_objects=True, unordered=True).split("\n")

                for obj in output:
                    obj_sha, obj_type, _ = obj.split(" ")
                    if obj_type == "blob":
                        res.append(obj_sha)
            except Exception as e:
                logger.error(e)
        
        return res

    def _snapshot(self, commit_sha: str) -> List[Tuple[str, str]]:
        """get the repository's folder structure of a commit

        Args:
            commit_sha (str): the hex sha of a commit object

        Returns:
            List[Tuple[str, str]]: a list containing the filenames and corresponding hex shas.
        """
        commit = self.repo.commit(commit_sha)
        files = []
        unchecked = [(commit.tree, "")]
        while len(unchecked) > 0:
            tree, root_path = unchecked.pop()
            for blob in tree.blobs:
                files.append((os.path.join(root_path, blob.name), blob.hexsha))
            for t in tree.trees:
                unchecked.append((t, os.path.join(root_path, t.name)))
            if len(tree) != len(tree.blobs) + len(tree.trees):
                items = []
                for row in tree.repo.git.cat_file("-p", tree.hexsha).split("\n"):
                    mode, obj_type, _ = row.split(" ")
                    if obj_type == "commit":
                        sha, name = _.split("\t")
                        sm = Repo(os.path.join(tree.abspath, name), odbt=GitDB).commit(sha).tree
                        unchecked.append((sm, os.path.join(root_path, name)))
        return files

    def commit_snapshots(self) -> Dict[str, Dict[str, List]]:
        """get the repository folder structure for all commits and dump the results to a json file.

        Returns:
            Dict[str, Dict[str, List]]: keys are hex shas of commits, values are dicts whose key are hex shas of blob objects and values are filenames. If two files' contents are the exactly same, their blob shas are also same. So a blob may correspond to multiple filenames.
        """
        save_file_path = os.path.join(self.data_folder, "commit_snapshots.json")
        if os.path.exists(save_file_path):
            logger.info(f"commit_snapshots.json already exists")
            return json.load(open(save_file_path))
        res = {}
        for commit in tqdm(self.commit_shas, ascii=" >="):
            res[commit] = {"timestamp": 0, "file_shas": []}
            res[commit]["timestamp"] = self.repo.commit(commit).authored_date
            files = self._snapshot(commit)
            for blob_name, blob_sha in files:
                res[commit]["file_shas"].append((blob_name, blob_sha))
        with open(save_file_path, "w") as outf:
            logger.info("dump commit_snapshots to commit_snapshots.json")
            json.dump(res, outf)
        return res

    def read_blob_content(self, blob_sha: str) -> str:
        return self.repo.git.cat_file("-p", blob_sha)
