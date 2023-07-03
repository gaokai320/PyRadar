import pytest

from baselines.ossgadget import OSSGadget
from baselines.release import Release


class TestOSSGadget:
    def test_extract_repository_url(self):
        assert OSSGadget.extract_repository_url("https://tensorflow.org") == []
        assert OSSGadget.extract_repository_url(
            "https://github.com/GAtom22/postbot/archive/0.1.1.tar.gz"
        ) == ["https://github.com/gatom22/postbot"]

    def test_parse_metadata(self):
        metadata1 = Release("postbot", "0.1.0").metadata
        assert OSSGadget.parse_metadata(metadata1) == None

        metadata2 = Release("postbot", "0.1.3").metadata
        assert (
            OSSGadget.parse_metadata(metadata2) == "https://github.com/gatom22/postbot"
        )

    # adapted from [src/oss-tests/FindSourceTests.cs](https://github.com/microsoft/OSSGadget/blob/main/src/oss-tests/FindSourceTests.cs#L95)
    @pytest.mark.parametrize(
        "name,repo_url",
        [
            ("hjkfashfkjafhakfjsa", None),
            ("moment", "https://github.com/zachwill/moment"),
            ("django", "https://github.com/django/django"),
            ("pylint", "https://github.com/pycqa/pylint"),
            ("arrow", "https://github.com/arrow-py/arrow"),
        ],
    )
    def test_parse_metadata_OSSGadget(self, name: str, repo_url: str):
        assert OSSGadget.parse_metadata(Release(name).metadata) == repo_url
