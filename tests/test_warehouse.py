from collections import OrderedDict

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
