import hashlib
import logging
import os
import tarfile
import zipfile
from collections import OrderedDict
from typing import Optional, Union

logger = logging.getLogger(__name__)


def calculate_sha(content: Union[bytes, str]) -> Optional[str]:
    if isinstance(content, str):
        content = content.encode()
    if not isinstance(content, bytes):
        logger.error("Please pass in a bytes-like or str-like data")
        return None
    sha1 = hashlib.sha1()
    sha1.update(f"blob {len(content)}\0".encode())
    sha1.update(content)
    return sha1.hexdigest()


def configure_logger(name: str, log_file: str, level: int):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    fh = logging.FileHandler(log_file, "a")
    fh.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


class CacheDict(OrderedDict):
    """Dict with a limited length, ejecting LRUs as needed. Code copies from: https://gist.github.com/davesteele/44793cd0348f59f8fadd49d7799bd306"""

    def __init__(self, *args, cache_len: int = 10, **kwargs):
        assert cache_len > 0
        self.cache_len = cache_len

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        super().move_to_end(key)

        while len(self) > self.cache_len:
            oldkey = next(iter(self))
            super().__delitem__(oldkey)

    def __getitem__(self, key):
        val = super().__getitem__(key)
        super().move_to_end(key)

        return val


class ZipReader:
    def __init__(
        self,
        file_path: str,
        translate_newline: bool = False,
    ) -> None:
        self.file_path = file_path
        self.translate_newline = translate_newline
        self.file = zipfile.ZipFile(self.file_path)

    @property
    def top_level_modules(self):
        top_level = []
        if self.file_path.endswith(".whl"):
            try:
                name, version = os.path.basename(self.file_path).split("-")[:2]
                top_level = (
                    self.file.open(f"{name}-{version}.dist-info/top_level.txt")
                    .read()
                    .decode()
                    .splitlines()
                )
            except:
                pass
        elif self.file_path.endswith(".egg"):
            try:
                top_level = (
                    self.file.open("EGG-INFO/top_level.txt")
                    .read()
                    .decode()
                    .splitlines()
                )
            except:
                pass
        return top_level

    def file_shas(self) -> list[tuple[str, str]]:
        res = []
        for name in self.file.namelist():
            if name.endswith("/"):
                continue
            if self.top_level_modules and (
                name.split("/")[0] not in self.top_level_modules
            ):
                continue

            if name.rsplit("/", 1)[-1] == "PKG-INFO":
                continue

            if name.rsplit("/", 1)[0].endswith("EGG-INFO"):
                continue

            if name.rsplit("/", 1)[0].endswith(".dist-info"):
                continue

            if name.rsplit("/", 1)[0].endswith(".egg-info"):
                continue

            content = self.get_file_content(name)
            res.append((name, calculate_sha(content)))
        return res

    def get_file_content(self, filename: str) -> str:
        ## translate \r\n to \n
        res = self.file.open(filename).read()
        if self.translate_newline:
            res = res.replace(b"\r\n", b"\n")
            res = res.replace(b"\r", b"\n")

        return res


class TarReader:
    def __init__(self, file_path: str, translate_newline: bool = False) -> None:
        self.file_path = file_path
        self.translate_newline = translate_newline
        self.file = tarfile.open(self.file_path)

    def file_shas(self) -> list[tuple[str, str]]:
        res = []
        for member in self.file.getmembers():
            if member.isreg():
                if member.name.rsplit("/", 1)[-1] == "PKG-INFO":
                    continue
                if member.name.rsplit("/", 1)[0].endswith(".egg-info"):
                    continue
                content = self.get_file_content(member)
                res.append(
                    (
                        member.name,
                        calculate_sha(content),
                    )
                )
        return res

    def get_file_content(self, filename: str) -> str:
        res = self.file.extractfile(filename).read()
        ## translate \r\n to \n
        if self.translate_newline:
            res = res.replace(b"\r\n", b"\n")
            res = res.replace(b"\r", b"\n")

        return res


class DistReader:
    def __init__(self, file_path: str, translate_newline: bool = False) -> None:
        if file_path.endswith(".tar.gz"):
            self.reader = TarReader(file_path, translate_newline)
        elif any(file_path.endswith(suffix) for suffix in [".zip", ".whl", ".egg"]):
            self.reader = ZipReader(file_path, translate_newline)

    def file_shas(self) -> list[tuple[str, str]]:
        return self.reader.file_shas()

    def get_file_content(self, filename: str) -> str:
        return self.reader.get_file_content(filename)
