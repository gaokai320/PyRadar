import hashlib
import logging
import tarfile
import zipfile
from collections import OrderedDict
from typing import Optional, Union


def calculate_sha(
    content: Union[bytes, str], logger: logging.Logger = None
) -> Optional[str]:
    logger = logger or logging.getLogger(__name__)
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
    def __init__(self, file_path: str, logger: logging.Logger = None) -> None:
        self.file_path = file_path
        self.file = zipfile.ZipFile(self.file_path)
        self.logger = logger or logging.getLogger(__name__)

    def file_shas(self) -> list[tuple[str, str]]:
        res = []
        for name in self.file.namelist():
            content = self.get_file_content(name)
            res.append((name, calculate_sha(content, self.logger)))
        return res

    def get_file_content(self, filename: str) -> str:
        ## translate \r\n to \n
        return b"\n".join(self.file.open(filename).read().splitlines())


class TarReader:
    def __init__(self, file_path: str, logger: logging.Logger = None) -> None:
        self.file_path = file_path
        self.file = tarfile.open(self.file_path)
        self.logger = logger or logging.getLogger(__name__)

    def file_shas(self) -> list[tuple[str, str]]:
        res = []
        for member in self.file.getmembers():
            if member.isreg():
                content = self.get_file_content(member)
                res.append(
                    (
                        member.name,
                        calculate_sha(content, self.logger),
                    )
                )
        return res

    def get_file_content(self, filename: str) -> str:
        ## translate \r\n to \n
        return b"\n".join(self.file.extractfile(filename).read().splitlines())


class DistReader:
    def __init__(self, file_path: str, logger: logging.Logger = None) -> None:
        if file_path.endswith(".tar.gz"):
            self.reader = TarReader(file_path, logger)
        elif any(file_path.endswith(suffix) for suffix in [".zip", ".whl", ".egg"]):
            self.reader = ZipReader(file_path, logger)

    def file_shas(self) -> list[tuple[str, str]]:
        return self.reader.file_shas()

    def get_file_content(self, filename: str) -> str:
        return self.reader.get_file_content(filename)
