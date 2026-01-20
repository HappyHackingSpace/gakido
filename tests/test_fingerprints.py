"""Tests for gakido.fingerprints module."""

import pytest
from gakido.fingerprints import ExtraFingerprints


class TestExtraFingerprints:
    """Tests for ExtraFingerprints class."""

    def test_default_initialization(self):
        """Test default initialization with empty lists."""
        fp = ExtraFingerprints()
        assert fp.alpn == []
        assert fp.ciphers == []
        assert fp.curves == []
        assert fp.sig_algs == []
        assert fp.extensions == []

    def test_initialization_with_alpn(self):
        """Test initialization with ALPN protocols."""
        fp = ExtraFingerprints(alpn=["h2", "http/1.1"])
        assert fp.alpn == ["h2", "http/1.1"]
        assert fp.ciphers == []

    def test_initialization_with_ciphers(self):
        """Test initialization with cipher suites."""
        ciphers = ["TLS_AES_128_GCM_SHA256", "TLS_AES_256_GCM_SHA384"]
        fp = ExtraFingerprints(ciphers=ciphers)
        assert fp.ciphers == ciphers

    def test_initialization_with_curves(self):
        """Test initialization with elliptic curves."""
        curves = ["X25519", "prime256v1"]
        fp = ExtraFingerprints(curves=curves)
        assert fp.curves == curves

    def test_initialization_with_sig_algs(self):
        """Test initialization with signature algorithms."""
        sig_algs = ["ecdsa_secp256r1_sha256", "rsa_pss_rsae_sha256"]
        fp = ExtraFingerprints(sig_algs=sig_algs)
        assert fp.sig_algs == sig_algs

    def test_initialization_with_extensions(self):
        """Test initialization with TLS extensions."""
        extensions = ["server_name", "supported_versions"]
        fp = ExtraFingerprints(extensions=extensions)
        assert fp.extensions == extensions

    def test_initialization_with_all_params(self):
        """Test initialization with all parameters."""
        fp = ExtraFingerprints(
            alpn=["h2"],
            ciphers=["cipher1"],
            curves=["X25519"],
            sig_algs=["sig1"],
            extensions=["ext1"],
        )
        assert fp.alpn == ["h2"]
        assert fp.ciphers == ["cipher1"]
        assert fp.curves == ["X25519"]
        assert fp.sig_algs == ["sig1"]
        assert fp.extensions == ["ext1"]

    def test_none_values_become_empty_lists(self):
        """Test None values are converted to empty lists."""
        fp = ExtraFingerprints(
            alpn=None,
            ciphers=None,
            curves=None,
            sig_algs=None,
            extensions=None,
        )
        assert fp.alpn == []
        assert fp.ciphers == []
        assert fp.curves == []
        assert fp.sig_algs == []
        assert fp.extensions == []

    def test_lists_are_stored_by_reference(self):
        """Test lists passed in are stored (not copied)."""
        alpn_list = ["h2"]
        fp = ExtraFingerprints(alpn=alpn_list)
        # Modifying the original list affects the stored value
        # (This is expected Python behavior, documenting it)
        alpn_list.append("http/1.1")
        assert "http/1.1" in fp.alpn
