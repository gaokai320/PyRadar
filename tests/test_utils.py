from baselines.utils import get_latest_version

def test_get_latest_version():
    assert get_latest_version("numpy") == "1.24.2"
    assert get_latest_version("torch") == "1.13.1"
    assert get_latest_version("fake_package") == None