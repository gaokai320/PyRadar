import logging
from collections import OrderedDict


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
