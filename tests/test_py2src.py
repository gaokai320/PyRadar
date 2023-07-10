import pytest

from baselines.py2src import Py2Src, URLFinder
from baselines.release import Release


class TestURLFinder:
    @pytest.mark.parametrize(
        ("name", "version", "expected"),
        [
            ("twitter", "1.19.6", "https://github.com/python-twitter-tools/twitter"),
            (
                "django-postgres-tweaks",
                "0.1.3",
                "https://github.com/jazzband/django-postgres-utils",
            ),
            ("numpy", None, None),
        ],
    )
    def test_find_github_url_from_pypi_badge(self, name, version, expected):
        metadata = Release(name, version).metadata
        assert URLFinder.find_github_url_from_pypi_badge(metadata) == expected

    def test_find_github_url_metadata(self):
        metadata = Release("urllib3", "1.26.14").metadata
        url = URLFinder.get_homepage(metadata)
        assert url and not URLFinder.is_valid_github_url(url)

        url = URLFinder.get_codepage(metadata)
        assert url and url == "https://github.com/urllib3/urllib3"
        assert (
            URLFinder.find_github_url_metadata(metadata)
            == "https://github.com/urllib3/urllib3"
        )

        metadata = Release("adsafdsafda").metadata
        assert URLFinder.get_homepage(metadata) is None
        assert URLFinder.get_codepage(metadata) is None

        assert URLFinder.find_github_url_metadata(metadata) is None

    @pytest.mark.parametrize(
        ("name", "version", "expected"),
        [
            ("urllib3", "1.26.14", "https://github.com/urllib3/urllib3"),
            ("adsafdsafda", None, None),
        ],
    )
    def test_mode_1(self, name, version, expected):
        metadata = Release(name, version).metadata
        assert URLFinder.find_github_url_metadata(metadata) == expected

    @pytest.mark.parametrize(
        ("name", "version", "expected"),
        [
            ("twitter", "1.19.6", "https://github.com/python-twitter-tools/twitter"),
            ("numpy", None, "https://github.com/numpy/numpy"),
        ],
    )
    def test_mode_2(self, name, version, expected):
        metadata = Release(name, version).metadata
        assert URLFinder.mode_2(metadata) == expected

    @pytest.mark.parametrize(
        ("name", "version", "expected"),
        [
            ("pymongo", "4.3.3", "https://github.com/mongodb/mongo-python-driver"),
            ("requests", "2.28.2", "https://github.com/psf/requests"),
            ("numpy", None, None),
        ],
    )
    def test_find_github_url_from_readthedocs(self, name, version, expected):
        metadata = Release(name, version).metadata
        assert URLFinder.find_github_url_from_readthedocs(metadata) == expected
