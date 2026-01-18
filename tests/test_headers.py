from gakido.headers import canonicalize_headers


def test_header_ordering_merges_and_respects_order():
    default = [("User-Agent", "ua"), ("Accept", "*/*")]
    user = {"Accept": "json", "X-Test": "1"}
    order = ["Accept", "User-Agent", "X-Test"]
    merged = canonicalize_headers(default, user, order)
    assert merged == [
        ("Accept", "json"),
        ("User-Agent", "ua"),
        ("X-Test", "1"),
    ]
