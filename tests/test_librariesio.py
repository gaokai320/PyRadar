from typing import Optional

import pytest
from baselines.librariesio import LibrariesIO
from baselines.release import Release


class TestLibrariesIO:
    @pytest.mark.parametrize(
        ("metadata", "homepage"),
        [
            ({}, None),
            ({"home_page": ""}, None),
            ({"home_page": " "}, " "),
            ({"home_page": "https://example.com"}, "https://example.com"),
            ({"project_urls": {}}, None),
            ({"project_urls": {"home_page": "a"}}, None),
            (
                {"project_urls": {"Homepage": "https://example.com"}},
                "https://example.com",
            ),
            (
                {
                    "home_page": "https://example.com",
                    "project_urls": {"Homepage": "https://example2.com"},
                },
                "https://example.com",
            ),
            (
                {"home_page": "", "project_urls": {"Homepage": "https://example2.com"}},
                "https://example2.com",
            ),
        ],
    )
    def test_select_homepage_url(
        self,
        metadata: dict[str, Optional[str | dict[str, str]]],
        homepage: Optional[str],
    ):
        assert LibrariesIO.select_homepge_url(metadata) == homepage

    # adapted from [`spec/models/package_manager/pypi_spec.rb`](https://github.com/librariesio/libraries.io/blob/main/spec/models/package_manager/pypi_spec.rb#L317)
    @pytest.mark.parametrize(
        ("metadata", "repository_url"),
        [
            ({"project_urls": {"Code": "wow"}}, "wow"),
            ({"project_urls": {"Source": "cool", "Code": "wow"}}, "cool"),
            ({"project_urls": {}}, None),
        ],
    )
    def test_select_repository_url(
        self,
        metadata: dict[str, Optional[str | dict[str, str]]],
        repository_url: Optional[str],
    ):
        assert LibrariesIO.select_repository_url(metadata) == repository_url

    # adapted from [`spec/models/package_manager/base_spec.rb`](https://github.com/librariesio/libraries.io/blob/main/spec/models/package_manager/base_spec.rb)
    @pytest.mark.parametrize(
        ("repo", "homepage", "expected"),
        [
            (None, None, None),
            (None, "test", None),
            (None, "http://homepage", None),
            (
                None,
                "https://github.com/librariesio/libraries.io",
                "https://github.com/librariesio/libraries.io",
            ),
            (
                "test",
                "https://github.com/librariesio/libraries.io",
                "https://github.com/librariesio/libraries.io",
            ),
            ("http://repo", "http://homepage", None),
        ],
    )
    def test_repo_fallback(
        self, repo: Optional[str], homepage: Optional[str], expected: Optional[str]
    ):
        assert LibrariesIO.repo_fallback(repo, homepage) == expected

    def test_find_repository_urls(self):
        # adapted from https://github.com/librariesio/libraries.io/blob/main/spec/models/package_manager/pypi_spec.rb#L32
        assert (
            LibrariesIO.parse_metadata(Release("attrs", "19.1.0").metadata)
            == "https://github.com/python-attrs/attrs"
        )
