from baselines.ossgadget import OSSGadget


class TestOSSGadget:
    def test_get_metadata(self):
        o = OSSGadget("numpy", "1.24.1")
        assert type(o.metadata) == dict
        assert o.metadata["version"] == "1.24.1"

        assert OSSGadget("numpy").metadata["version"] == "1.24.2"

        assert OSSGadget("fake_package").metadata == None

    def test_extractGitHubURL(self):
        assert OSSGadget.extractGitHubURL("https://tensorflow.org") == []
        assert OSSGadget.extractGitHubURL(
            "https://github.com/GAtom22/postbot/archive/0.1.1.tar.gz"
        ) == ["https://github.com/gatom22/postbot"]

    def test_parse_metadata(self):
        metadata1 = OSSGadget("postbot", "0.1.0").metadata
        assert OSSGadget.parse_metadata(metadata1) == []

        metadata2 = OSSGadget("postbot", "0.1.3").metadata
        assert set(OSSGadget.parse_metadata(metadata2)) == set(
            ["https://github.com/gatom22/postbot"]
        )

    def test_search_source(self):
        assert OSSGadget("postbot", "0.1.0").search_source() == None
        assert (
            OSSGadget("postbot", "0.1.3").search_source()
            == "https://github.com/gatom22/postbot"
        )
