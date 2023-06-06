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
        assert OSSGadget.parse_metadata(metadata2) == "https://github.com/gatom22/postbot"

