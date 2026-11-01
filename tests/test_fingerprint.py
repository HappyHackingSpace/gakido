"""Tests for gakido.fingerprint module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from gakido import fingerprint
from gakido.fingerprint import (
    DEFAULT_ECHO_URL,
    REFERENCE_FINGERPRINTS,
    FingerprintResult,
    base_profiles,
    canonical_profile,
    collect_fingerprint,
    format_text,
    get_reference,
    main,
    parse_echo_payload,
)
from gakido.impersonation.profiles import ALIAS_MAP, PROFILES
from gakido.models import Response

CHROME_120_JA4 = "t13d1516h2_8daaf6152771_02713d6af862"
CHROME_120_AKAMAI = "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p"

PEET_PAYLOAD = {
    "ip": "203.0.113.7",
    "http_version": "h2",
    "method": "GET",
    "user_agent": "Mozilla/5.0 (Macintosh) Chrome/120.0.0.0",
    "tls": {
        "ja3": "771,4865-4866,0-23-65281,29-23-24,0",
        "ja3_hash": "cd08e31494f9531f560d64c695473da9",
        "ja4": CHROME_120_JA4,
    },
    "http2": {
        "akamai_fingerprint": CHROME_120_AKAMAI,
        "akamai_fingerprint_hash": "52d84b11737d980aef856699f885ca86",
    },
}


def make_response(payload, status_code=200):
    body = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
    return Response(
        status_code=status_code,
        reason="OK" if status_code == 200 else "Error",
        http_version="2",
        headers=[("Content-Type", "application/json")],
        body=body,
    )


def make_client_mock(response):
    client = MagicMock()
    client.get.return_value = response
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    return client


class TestProfileResolution:
    def test_canonical_base_profile(self):
        assert canonical_profile("chrome_120") == "chrome_120"

    def test_canonical_alias(self):
        assert canonical_profile("chrome120") == "chrome_120"
        assert canonical_profile("firefox133") == "firefox_133"

    def test_canonical_unknown_raises(self):
        with pytest.raises(KeyError):
            canonical_profile("netscape_4")

    def test_base_profiles_exclude_aliases(self):
        bases = base_profiles()
        assert "chrome_120" in bases
        assert "firefox_147" in bases
        assert all(name not in ALIAS_MAP for name in bases)
        assert all(name in PROFILES for name in bases)

    def test_reference_lookup_via_alias(self):
        assert get_reference("chrome120") == REFERENCE_FINGERPRINTS["chrome_120"]

    def test_reference_lookup_missing(self):
        assert get_reference("firefox_147") is None
        assert get_reference("netscape_4") is None

    def test_reference_values_match_documented_prints(self):
        ref = REFERENCE_FINGERPRINTS["chrome_120"]
        assert ref["ja4"] == CHROME_120_JA4
        assert ref["http2_akamai"] == CHROME_120_AKAMAI


class TestParseEchoPayload:
    def test_full_payload(self):
        parsed = parse_echo_payload(PEET_PAYLOAD)
        assert parsed["http_version"] == "h2"
        assert parsed["ja3"] == PEET_PAYLOAD["tls"]["ja3"]
        assert parsed["ja3_hash"] == "cd08e31494f9531f560d64c695473da9"
        assert parsed["ja4"] == CHROME_120_JA4
        assert parsed["http2_akamai"] == CHROME_120_AKAMAI

    def test_missing_http2_section(self):
        payload = {k: v for k, v in PEET_PAYLOAD.items() if k != "http2"}
        parsed = parse_echo_payload(payload)
        assert parsed["http2_akamai"] is None
        assert parsed["ja4"] == CHROME_120_JA4

    def test_non_dict_payload(self):
        parsed = parse_echo_payload(["not", "a", "dict"])
        assert all(value is None for value in parsed.values())

    def test_empty_strings_become_none(self):
        payload = {"tls": {"ja3": "", "ja4": ""}, "http_version": ""}
        parsed = parse_echo_payload(payload)
        assert parsed["ja3"] is None
        assert parsed["ja4"] is None
        assert parsed["http_version"] is None


class TestCollectFingerprint:
    @patch("gakido.fingerprint.Client")
    def test_success_with_reference_match(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        result = collect_fingerprint("chrome_120")

        assert result.ok is True
        assert result.ja4 == CHROME_120_JA4
        assert result.http2_akamai == CHROME_120_AKAMAI
        assert result.matches == {"ja4": True, "http2_akamai": True}
        assert result.mismatched is False
        mock_client_cls.assert_called_once_with(
            impersonate="chrome_120", timeout=30.0, tls_backend="auto"
        )
        mock_client_cls.return_value.get.assert_called_once_with(DEFAULT_ECHO_URL)

    @patch("gakido.fingerprint.Client")
    def test_mismatch_detected(self, mock_client_cls):
        payload = json.loads(json.dumps(PEET_PAYLOAD))
        payload["tls"]["ja4"] = "t13d0000h2_dead_beef"
        mock_client_cls.return_value = make_client_mock(make_response(payload))
        result = collect_fingerprint("chrome_120")

        assert result.ok is True
        assert result.matches is not None
        assert result.matches["ja4"] is False
        assert result.matches["http2_akamai"] is True
        assert result.mismatched is True

    @patch("gakido.fingerprint.Client")
    def test_profile_without_reference(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        result = collect_fingerprint("firefox_147")

        assert result.ok is True
        assert result.reference is None
        assert result.matches is None
        assert result.mismatched is False

    @patch("gakido.fingerprint.Client")
    def test_unknown_profile(self, mock_client_cls):
        result = collect_fingerprint("netscape_4")
        assert result.ok is False
        assert result.error is not None
        assert "netscape_4" in result.error
        mock_client_cls.assert_not_called()

    @patch("gakido.fingerprint.Client")
    def test_request_error(self, mock_client_cls):
        client = make_client_mock(None)
        client.get.side_effect = OSError("connection refused")
        mock_client_cls.return_value = client
        result = collect_fingerprint("chrome_120")

        assert result.ok is False
        assert result.error is not None
        assert "OSError" in result.error

    @patch("gakido.fingerprint.Client")
    def test_non_200_response(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock(
            make_response(PEET_PAYLOAD, status_code=503)
        )
        result = collect_fingerprint("chrome_120")
        assert result.ok is False
        assert result.error is not None
        assert "503" in result.error

    @patch("gakido.fingerprint.Client")
    def test_non_json_response(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock(make_response(b"<html>nope"))
        result = collect_fingerprint("chrome_120")
        assert result.ok is False
        assert result.error is not None
        assert "non-JSON" in result.error

    @patch("gakido.fingerprint.Client")
    def test_custom_echo_url_and_backend(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        result = collect_fingerprint(
            "chrome_120",
            echo_url="https://echo.example/api/all",
            timeout=5.0,
            tls_backend="stdlib",
        )
        assert result.ok is True
        assert result.echo_url == "https://echo.example/api/all"
        mock_client_cls.assert_called_once_with(
            impersonate="chrome_120", timeout=5.0, tls_backend="stdlib"
        )
        mock_client_cls.return_value.get.assert_called_once_with(
            "https://echo.example/api/all"
        )


class TestFormatText:
    @patch("gakido.fingerprint.Client")
    def test_match_annotations(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        text = format_text(collect_fingerprint("chrome_120"))

        assert "Profile: chrome_120" in text
        assert "JA3:           cd08e31494f9531f560d64c695473da9" in text
        assert f"JA4:           {CHROME_120_JA4}  (matches reference)" in text
        assert f"HTTP/2 Akamai: {CHROME_120_AKAMAI}  (matches reference)" in text

    @patch("gakido.fingerprint.Client")
    def test_mismatch_annotation(self, mock_client_cls):
        payload = json.loads(json.dumps(PEET_PAYLOAD))
        payload["tls"]["ja4"] = "t13d0000h2_dead_beef"
        mock_client_cls.return_value = make_client_mock(make_response(payload))
        text = format_text(collect_fingerprint("chrome_120"))
        assert f"(MISMATCH, expected {CHROME_120_JA4})" in text

    @patch("gakido.fingerprint.Client")
    def test_no_reference_note(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        text = format_text(collect_fingerprint("firefox_147"))
        assert "No stored reference print" in text
        assert "(matches reference)" not in text

    def test_error_result(self):
        result = FingerprintResult(
            profile="chrome_120",
            echo_url=DEFAULT_ECHO_URL,
            ok=False,
            error="boom",
        )
        text = format_text(result)
        assert "ERROR: boom" in text


class TestMain:
    @patch("gakido.fingerprint.Client")
    def test_default_profile_text_output(self, mock_client_cls, capsys):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        exit_code = main([])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Profile: chrome_120" in out
        mock_client_cls.assert_called_once_with(
            impersonate="chrome_120", timeout=30.0, tls_backend="auto"
        )

    @patch("gakido.fingerprint.Client")
    def test_json_output(self, mock_client_cls, capsys):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        exit_code = main(["chrome_120", "--json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["profile"] == "chrome_120"
        assert data[0]["ja4"] == CHROME_120_JA4
        assert data[0]["matches"] == {"ja4": True, "http2_akamai": True}

    @patch("gakido.fingerprint.Client")
    def test_multiple_profiles(self, mock_client_cls, capsys):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        exit_code = main(["chrome_120", "firefox_147", "--json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert [entry["profile"] for entry in data] == ["chrome_120", "firefox_147"]
        assert mock_client_cls.call_count == 2

    @patch("gakido.fingerprint.collect_fingerprint")
    def test_all_runs_every_base_profile(self, mock_collect, capsys):
        mock_collect.side_effect = lambda profile, **kwargs: FingerprintResult(
            profile=profile, echo_url=DEFAULT_ECHO_URL, ok=True
        )
        exit_code = main(["--all"])

        assert exit_code == 0
        tested = [call.args[0] for call in mock_collect.call_args_list]
        assert tested == base_profiles()

    @patch("gakido.fingerprint.Client")
    def test_mismatch_exit_code(self, mock_client_cls, capsys):
        payload = json.loads(json.dumps(PEET_PAYLOAD))
        payload["tls"]["ja4"] = "t13d0000h2_dead_beef"
        mock_client_cls.return_value = make_client_mock(make_response(payload))
        assert main(["chrome_120"]) == 1

    @patch("gakido.fingerprint.Client")
    def test_unknown_profile_exit_code(self, mock_client_cls, capsys):
        exit_code = main(["netscape_4"])
        assert exit_code == 1
        assert "ERROR" in capsys.readouterr().out
        mock_client_cls.assert_not_called()

    @patch("gakido.fingerprint.Client")
    def test_echo_url_flag(self, mock_client_cls, capsys):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        exit_code = main(
            ["chrome_120", "--echo-url", "https://echo.example/api/all", "--json"]
        )

        assert exit_code == 0
        mock_client_cls.return_value.get.assert_called_once_with(
            "https://echo.example/api/all"
        )
        data = json.loads(capsys.readouterr().out)
        assert data[0]["echo_url"] == "https://echo.example/api/all"

    @patch("gakido.fingerprint.Client")
    def test_tls_backend_flag(self, mock_client_cls, capsys):
        mock_client_cls.return_value = make_client_mock(make_response(PEET_PAYLOAD))
        assert main(["chrome_120", "--tls-backend", "stdlib"]) == 0
        mock_client_cls.assert_called_once_with(
            impersonate="chrome_120", timeout=30.0, tls_backend="stdlib"
        )

    def test_module_is_importable_as_main_target(self):
        assert hasattr(fingerprint, "main")
