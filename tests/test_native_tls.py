"""Tests for the native TLS backend bridge and its Client integration."""

import base64
import json

import pytest

from gakido import native_tls
from gakido.client import Client, _resolve_tls_backend
from gakido.impersonation import get_profile


class TestResolveTLSBackend:
    def test_stdlib_never_uses_native(self):
        assert _resolve_tls_backend("stdlib") is None

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            _resolve_tls_backend("bogus")

    def test_auto_falls_back_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(native_tls, "is_available", lambda: False)
        assert _resolve_tls_backend("auto") is None

    def test_native_requires_library(self, monkeypatch):
        monkeypatch.setattr(native_tls, "is_available", lambda: False)
        with pytest.raises(RuntimeError):
            _resolve_tls_backend("native")

    def test_auto_uses_native_when_available(self, monkeypatch):
        monkeypatch.setattr(native_tls, "is_available", lambda: True)
        assert _resolve_tls_backend("auto") is native_tls


class _FakeBackend:
    """Captures the spec and returns a canned ResponseSpec-shaped dict."""

    def __init__(self):
        self.spec = None

    def request(self, spec):
        self.spec = spec
        return {
            "status": 200,
            "proto": "HTTP/2.0",
            "headers": [["content-type", "text/plain"]],
            "body": b"hello",
            "error": "",
        }


class TestNativeRequestIntegration:
    def _client(self):
        # Build on the stdlib path (no library needed) then inject the fake.
        client = Client(impersonate="chrome_120", tls_backend="stdlib")
        return client

    def test_spec_mapping_and_response(self):
        client = self._client()
        fake = _FakeBackend()
        client._native_tls = fake

        merged = [("Host", "example.com"), ("User-Agent", "UA"), ("Accept", "*/*")]
        resp = client._native_request(
            "GET", "https://example.com/p", merged, None, None
        )

        # Response mapping.
        assert resp.status_code == 200
        assert resp.http_version == "2"
        assert resp.content == b"hello"

        # Spec was built from the merged headers, in order, with the mapped
        # tls-client profile and no proxy.
        spec = fake.spec
        assert spec["method"] == "GET"
        assert spec["url"] == "https://example.com/p"
        assert spec["headers"] == [list(h) for h in merged]
        assert spec["header_order"] == ["Host", "User-Agent", "Accept"]
        assert spec["profile"] == get_profile("chrome_120")["tls_client_profile"]
        assert spec["proxy"] == ""
        assert spec["body_b64"] == ""
        # chrome is Chromium -> extension order is permuted per connection.
        assert spec["permute_extensions"] is True

    def test_permute_extensions_off_for_firefox(self):
        client = Client(impersonate="firefox_133", tls_backend="stdlib")
        fake = _FakeBackend()
        client._native_tls = fake
        client._native_request(
            "GET", "https://example.com", [("Host", "example.com")], None, None
        )
        # Firefox sends a fixed extension order.
        assert fake.spec["permute_extensions"] is False

    def test_body_is_base64_encoded(self):
        client = self._client()
        fake = _FakeBackend()
        client._native_tls = fake

        client._native_request(
            "POST", "https://example.com", [("Host", "example.com")], b"payload", None
        )
        assert base64.b64decode(fake.spec["body_b64"]) == b"payload"

    def test_proxy_passed_through(self):
        client = self._client()
        fake = _FakeBackend()
        client._native_tls = fake

        client._native_request(
            "GET",
            "https://example.com",
            [("Host", "example.com")],
            None,
            "http://user:pass@127.0.0.1:8080",
        )
        assert fake.spec["proxy"] == "http://user:pass@127.0.0.1:8080"


class TestProfileMapping:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("chrome_120", "chrome_120"),
            ("chrome144", "chrome_131"),
            ("firefox_120", "firefox_120"),
            ("firefox147", "firefox_133"),
            ("safari172_ios", "safari_ios_17_0"),
            ("edge144", "chrome_131"),
            ("opera115", "opera_91"),
            ("brave131", "chrome_131"),
            ("tor145", "firefox_117"),
        ],
    )
    def test_profiles_carry_tls_client_profile(self, name, expected):
        assert get_profile(name)["tls_client_profile"] == expected

    @pytest.mark.parametrize(
        "name", ["chrome_120", "chrome144", "edge144", "opera115", "brave131", "vivaldi7"]
    )
    def test_chromium_permutes_extensions(self, name):
        assert get_profile(name).get("tls_permute_extensions") is True

    @pytest.mark.parametrize(
        "name", ["firefox_120", "firefox133", "safari172_ios", "tor145"]
    )
    def test_non_chromium_does_not_permute(self, name):
        # Fixed extension order -> flag absent (falsy).
        assert not get_profile(name).get("tls_permute_extensions")


@pytest.mark.skipif(
    not native_tls.is_available(),
    reason="native TLS library not built (run `make -C native build`)",
)
class TestNativeBackendLive:
    def test_chrome_fingerprint(self):
        spec = {
            "method": "GET",
            "url": "https://tls.peet.ws/api/all",
            "profile": "chrome_120",
            "headers": [
                ["User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                 "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"],
                ["Accept", "*/*"],
            ],
            "timeout_seconds": 30,
        }
        try:
            result = native_tls.request(spec)
        except native_tls.NativeBackendError as exc:
            pytest.skip(f"network/backend unavailable: {exc}")

        data = json.loads(result["body"])
        assert data["tls"]["ja4"] == "t13d1516h2_8daaf6152771_02713d6af862"
        assert (
            data["http2"]["akamai_fingerprint"]
            == "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p"
        )
