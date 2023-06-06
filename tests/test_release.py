from baselines.release import Release

class TestRelease:
    def test_metadata(self):
        assert Release("numpy", "1.24.1").metadata["version"] == "1.24.1"
        assert Release("numpy").metadata["version"] == "1.24.2"
        assert Release("fake_package").metadata == None