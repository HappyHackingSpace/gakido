"""Tests for gakido.impersonation.ja3 module."""

import pytest
from gakido.impersonation.ja3 import (
    apply_ja3_overrides,
    apply_tls_configuration_options,
    SIGNATURES,
)
from gakido.fingerprints import ExtraFingerprints


class TestApplyJa3Overrides:
    """Tests for apply_ja3_overrides function."""

    def test_no_overrides_returns_unchanged(self):
        """Test empty ja3 dict returns profile unchanged."""
        profile = {"tls": {"alpn": ["h2"]}}
        result = apply_ja3_overrides(profile, None)
        assert result == profile

    def test_empty_dict_returns_unchanged(self):
        """Test empty ja3 dict returns profile unchanged."""
        profile = {"tls": {"alpn": ["h2"]}}
        result = apply_ja3_overrides(profile, {})
        assert result == profile

    def test_override_ciphers(self):
        """Test overriding ciphers."""
        profile = {}
        ja3 = {"ciphers": ["TLS_AES_128_GCM_SHA256"]}
        result = apply_ja3_overrides(profile, ja3)
        assert result["tls"]["ciphers"] == ["TLS_AES_128_GCM_SHA256"]

    def test_override_alpn(self):
        """Test overriding ALPN protocols."""
        profile = {}
        ja3 = {"alpn": ["h2", "http/1.1"]}
        result = apply_ja3_overrides(profile, ja3)
        assert result["tls"]["alpn"] == ["h2", "http/1.1"]
        # Also mirrored to http2
        assert result["http2"]["alpn"] == ["h2", "http/1.1"]

    def test_override_curves(self):
        """Test overriding elliptic curves."""
        profile = {}
        ja3 = {"curves": ["X25519", "prime256v1"]}
        result = apply_ja3_overrides(profile, ja3)
        assert result["tls"]["curves"] == ["X25519", "prime256v1"]

    def test_override_sig_algs(self):
        """Test overriding signature algorithms."""
        profile = {}
        ja3 = {"sig_algs": ["ecdsa_secp256r1_sha256"]}
        result = apply_ja3_overrides(profile, ja3)
        assert result["tls"]["sig_algs"] == ["ecdsa_secp256r1_sha256"]

    def test_override_multiple(self):
        """Test overriding multiple fields."""
        profile = {}
        ja3 = {
            "ciphers": ["cipher1"],
            "alpn": ["h2"],
            "curves": ["X25519"],
        }
        result = apply_ja3_overrides(profile, ja3)
        assert result["tls"]["ciphers"] == ["cipher1"]
        assert result["tls"]["alpn"] == ["h2"]
        assert result["tls"]["curves"] == ["X25519"]

    def test_override_preserves_existing_profile(self):
        """Test overriding preserves other profile fields."""
        profile = {"headers": {"default": [("User-Agent", "test")]}}
        ja3 = {"alpn": ["h2"]}
        result = apply_ja3_overrides(profile, ja3)
        assert result["headers"]["default"] == [("User-Agent", "test")]

    def test_override_replaces_existing_tls(self):
        """Test overriding replaces existing TLS values."""
        profile = {"tls": {"alpn": ["http/1.1"]}}
        ja3 = {"alpn": ["h2"]}
        result = apply_ja3_overrides(profile, ja3)
        assert result["tls"]["alpn"] == ["h2"]

    def test_empty_override_value_ignored(self):
        """Test empty override values are ignored."""
        profile = {"tls": {"alpn": ["h2"]}}
        ja3 = {"alpn": [], "ciphers": None}
        result = apply_ja3_overrides(profile, ja3)
        assert result["tls"]["alpn"] == ["h2"]

    def test_signatures_constant(self):
        """Test SIGNATURES constant contains expected keys."""
        assert "ciphers" in SIGNATURES
        assert "alpn" in SIGNATURES
        assert "curves" in SIGNATURES
        assert "sig_algs" in SIGNATURES


class TestApplyTlsConfigurationOptions:
    """Tests for apply_tls_configuration_options function."""

    def test_no_options_returns_unchanged(self):
        """Test None options returns profile unchanged."""
        profile = {"tls": {"alpn": ["h2"]}}
        result = apply_tls_configuration_options(profile, None)
        assert result == profile

    def test_empty_options_returns_unchanged(self):
        """Test empty options returns profile unchanged."""
        profile = {"tls": {"alpn": ["h2"]}}
        result = apply_tls_configuration_options(profile, {})
        assert result == profile

    def test_ja3_str_stored(self):
        """Test ja3_str is stored on profile."""
        profile = {}
        opts = {"ja3_str": "771,4866-4867,0-11-10,29,0"}
        result = apply_tls_configuration_options(profile, opts)
        assert result["ja3_str"] == "771,4866-4867,0-11-10,29,0"

    def test_akamai_str_stored(self):
        """Test akamai_str is stored on profile."""
        profile = {}
        opts = {"akamai_str": "1:65536;3:1000"}
        result = apply_tls_configuration_options(profile, opts)
        assert result["akamai_str"] == "1:65536;3:1000"

    def test_extra_fp_stored(self):
        """Test extra_fp is stored on profile."""
        profile = {}
        extra_fp = ExtraFingerprints(alpn=["h2"])
        opts = {"extra_fp": extra_fp}
        result = apply_tls_configuration_options(profile, opts)
        assert result["extra_fp"] is extra_fp

    def test_extra_fp_alpn_applied(self):
        """Test extra_fp ALPN is applied to profile."""
        profile = {}
        extra_fp = ExtraFingerprints(alpn=["h2", "http/1.1"])
        opts = {"extra_fp": extra_fp}
        result = apply_tls_configuration_options(profile, opts)
        assert result["tls"]["alpn"] == ["h2", "http/1.1"]
        assert result["http2"]["alpn"] == ["h2", "http/1.1"]

    def test_extra_fp_ciphers_applied(self):
        """Test extra_fp ciphers are applied to profile."""
        profile = {}
        extra_fp = ExtraFingerprints(ciphers=["cipher1", "cipher2"])
        opts = {"extra_fp": extra_fp}
        result = apply_tls_configuration_options(profile, opts)
        assert result["tls"]["ciphers"] == "cipher1:cipher2"

    def test_extra_fp_curves_applied(self):
        """Test extra_fp curves are applied to profile."""
        profile = {}
        extra_fp = ExtraFingerprints(curves=["X25519"])
        opts = {"extra_fp": extra_fp}
        result = apply_tls_configuration_options(profile, opts)
        assert result["tls"]["curves"] == ["X25519"]

    def test_extra_fp_sig_algs_applied(self):
        """Test extra_fp sig_algs are applied to profile."""
        profile = {}
        extra_fp = ExtraFingerprints(sig_algs=["ecdsa_secp256r1_sha256"])
        opts = {"extra_fp": extra_fp}
        result = apply_tls_configuration_options(profile, opts)
        assert result["tls"]["sig_algs"] == ["ecdsa_secp256r1_sha256"]

    def test_extra_fp_empty_values_not_applied(self):
        """Test extra_fp with empty values doesn't add empty entries."""
        profile = {}
        extra_fp = ExtraFingerprints()  # All empty
        opts = {"extra_fp": extra_fp}
        result = apply_tls_configuration_options(profile, opts)
        assert "tls" not in result or "alpn" not in result.get("tls", {})

    def test_preserves_existing_profile(self):
        """Test options preserve existing profile fields."""
        profile = {"headers": {"default": []}}
        opts = {"ja3_str": "test"}
        result = apply_tls_configuration_options(profile, opts)
        assert result["headers"]["default"] == []
