from gakido.impersonation import PROFILES, get_profile


def test_get_profile_returns_copy():
    profile = get_profile("chrome_120")
    profile["headers"]["default"][0] = ("User-Agent", "modified")
    assert PROFILES["chrome_120"]["headers"]["default"][0][0] == "Connection"
