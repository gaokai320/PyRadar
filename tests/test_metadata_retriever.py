from typing import Optional

import pytest

from baselines.release import Release
from pyradar.metadata_retriever import MetadataRetriever, github_repo_redirection


class TestMetadataRetriever:
    @pytest.mark.parametrize(
        ("name", "version", "expected"),
        [
            ("dapr", "1.9.0", "https://github.com/dapr/python-sdk"),
            ("tensorflow", "2.3.1", "https://github.com/tensorflow/tensorflow"),
            ("numpy", "1.20.0", "https://github.com/numpy/numpy"),
            ("gflex", "0.8", "https://github.com/awickert/gflex"),
            ("hatch", "1.0.0rc9", "https://github.com/ofek/hatch"),
            ("postbot", "0.1.4", "https://github.com/gatom22/postbot"),
        ],
    )
    def test_search_fields(self, name: str, version: Optional[str], expected: str):
        metadata = Release(name, version).metadata
        home_page = metadata.get("home_page")
        download_url = metadata.get("download_url")
        project_urls = metadata.get("project_urls", {})
        assert (
            MetadataRetriever.search_fields(home_page, download_url, project_urls)
            == expected
        )

    @pytest.mark.parametrize(
        ("name", "version", "expected"),
        [
            ("twitter", "1.19.6", "https://github.com/python-twitter-tools/twitter"),
            ("django-postgres-tweaks", "0.1.3", None),
            ("cffi", "1.15.1", None),
        ],
    )
    def test_search_description(self, name: str, version: Optional[str], expected: str):
        metadata = Release(name, version).metadata
        description = metadata.get("description")
        assert MetadataRetriever.search_description(name, description) == expected

    @pytest.mark.parametrize(
        ("name", "version", "expected"),
        [
            ("twitter", "1.17.1", "https://github.com/sixohsix/twitter"),
            ("pytz", "2022.7.1", "https://github.com/stub42/pytz"),
            ("cffi", "1.15.1", None),
        ],
    )
    def test_search_webpage(self, name: str, version: Optional[str], expected: str):
        metadata = Release(name, version).metadata
        project_urls = metadata.get("project_urls")
        webpage_urls = MetadataRetriever.select_homepage_doc_url(project_urls)
        assert MetadataRetriever.search_webpage(name, webpage_urls)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/sixohsix/twitter",
            "https://github.com/python-twitter-tools/twitter",
        ),
        ("https://github.com/gatom22/postbot", "https://github.com/gatom22/postbot"),
        ("https://github.com/cestoliv/pygtk_form", None),
    ],
)
def test_github_repo_redirection(url: str, expected: str):
    assert github_repo_redirection(url) == expected
