from collections import OrderedDict

import pytest

from baselines.release import Release
from baselines.warehouse import Warehouse


class TestWarehouse:
    def test_urls(self):
        assert Warehouse.urls(Release("postbot", "0.1.0").metadata) == OrderedDict()
        assert dict(Warehouse.urls(Release("postbot", "0.1.3").metadata)) == {
            "Download": "https://github.com/GAtom22/postbot/archive/0.1.3.tar.gz",
            "Homepage": "https://github.com/GAtom22/postbot",
        }
        assert (
            Warehouse.urls(Release("client_chat_pyqt_march_22", "0.1").metadata)
            == OrderedDict()
        )

    # adapted from [`tests/unit/packaging/test_models.py`]https://github.com/pypi/warehouse/blob/main/tests/unit/packaging/test_models.py#L249
    @pytest.mark.parametrize(
        ("home_page", "download_url", "project_urls", "expected"),
        [
            (None, None, [], OrderedDict()),
            (
                "https://example.com/home/",
                None,
                {},
                OrderedDict([("Homepage", "https://example.com/home/")]),
            ),
            (
                None,
                "https://example.com/download/",
                {},
                OrderedDict([("Download", "https://example.com/download/")]),
            ),
            (
                "https://example.com/home/",
                "https://example.com/download/",
                {},
                OrderedDict(
                    [
                        ("Homepage", "https://example.com/home/"),
                        ("Download", "https://example.com/download/"),
                    ]
                ),
            ),
            (
                None,
                None,
                {"Source Code": "https://example.com/source-code/"},
                OrderedDict([("Source Code", "https://example.com/source-code/")]),
            ),
            (
                None,
                None,
                {"Source Code": "https://example.com/source-code/"},
                OrderedDict([("Source Code", "https://example.com/source-code/")]),
            ),
            (
                "https://example.com/home/",
                "https://example.com/download/",
                {"Source Code": "https://example.com/source-code/"},
                OrderedDict(
                    [
                        ("Homepage", "https://example.com/home/"),
                        ("Source Code", "https://example.com/source-code/"),
                        ("Download", "https://example.com/download/"),
                    ]
                ),
            ),
            (
                "https://example.com/home/",
                "https://example.com/download/",
                {
                    "Homepage": "https://example.com/home2/",
                    "Source Code": "https://example.com/source-code/",
                },
                OrderedDict(
                    [
                        ("Homepage", "https://example.com/home2/"),
                        ("Source Code", "https://example.com/source-code/"),
                        ("Download", "https://example.com/download/"),
                    ]
                ),
            ),
            (
                "https://example.com/home/",
                "https://example.com/download/",
                {
                    "Source Code": "https://example.com/source-code/",
                    "Download": "https://example.com/download2/",
                },
                OrderedDict(
                    [
                        ("Homepage", "https://example.com/home/"),
                        ("Source Code", "https://example.com/source-code/"),
                        ("Download", "https://example.com/download2/"),
                    ]
                ),
            ),
            # project_urls has more priority than home_page and download_url
            (
                "https://example.com/home/",
                "https://example.com/download/",
                {
                    "Homepage": "https://example.com/home2/",
                    "Source Code": "https://example.com/source-code/",
                    "Download": "https://example.com/download2/",
                },
                OrderedDict(
                    [
                        ("Homepage", "https://example.com/home2/"),
                        ("Source Code", "https://example.com/source-code/"),
                        ("Download", "https://example.com/download2/"),
                    ]
                ),
            ),
            # similar spellings of homepage/download label doesn't duplicate urls
            (
                "https://example.com/home/",
                "https://example.com/download/",
                {
                    "homepage": "https://example.com/home/",
                    "download-URL": "https://example.com/download/",
                },
                OrderedDict(
                    [
                        ("Homepage", "https://example.com/home/"),
                        ("Download", "https://example.com/download/"),
                    ]
                ),
            ),
            # the duplicate removal only happens if the urls are equal too!
            (
                "https://example.com/home1/",
                None,
                {
                    "homepage": "https://example.com/home2/",
                },
                OrderedDict(
                    [
                        ("Homepage", "https://example.com/home1/"),
                        ("homepage", "https://example.com/home2/"),
                    ]
                ),
            ),
        ],
    )
    def test_urls_warehouse(self, home_page, download_url, project_urls, expected):
        metadata = {
            "home_page": home_page,
            "download_url": download_url,
            "project_urls": project_urls,
        }

        assert dict(Warehouse.urls(metadata)) == dict(expected)

    def test_extract_repository_url(self):
        assert Warehouse.extract_repository_url(["https://tensorflow.org"]) == None
        assert (
            Warehouse.extract_repository_url(
                [
                    "https://github.com/GAtom22/postbot/archive/0.1.3.tar.gz",
                    "https://github.com/GAtom22/postbot",
                ]
            )
            == "https://github.com/gatom22/postbot"
        )

    def test_parse_metadata(self):
        metadata1 = Release("postbot", "0.1.0").metadata
        assert Warehouse.parse_metadata(metadata1) == None

        metadata2 = Release("postbot", "0.1.3").metadata
        assert (
            Warehouse.parse_metadata(metadata2) == "https://github.com/gatom22/postbot"
        )
