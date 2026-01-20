"""Pytest configuration and fixtures."""

import pytest
from gakido.models import Response


@pytest.fixture
def sample_response():
    """Create a sample Response object."""
    return Response(
        status_code=200,
        reason="OK",
        http_version="1.1",
        headers=[
            ("Content-Type", "application/json"),
            ("Content-Length", "13"),
        ],
        body=b'{"key":"val"}',
    )


@pytest.fixture
def sample_profile():
    """Create a sample browser profile."""
    return {
        "tls": {
            "ciphers": "TLS_AES_128_GCM_SHA256",
            "alpn": ["h2", "http/1.1"],
            "curves": ["X25519"],
        },
        "http2": {
            "settings": {"HEADER_TABLE_SIZE": 65536},
            "alpn": ["h2", "http/1.1"],
        },
        "http3": {
            "max_stream_data": 1048576,
            "max_data": 10485760,
            "idle_timeout": 30.0,
        },
        "headers": {
            "order": ["Host", "User-Agent", "Accept"],
            "default": [
                ("User-Agent", "TestAgent/1.0"),
                ("Accept", "*/*"),
                ("Accept-Encoding", "gzip, deflate, br"),
            ],
        },
    }


@pytest.fixture
def mock_socket(mocker):
    """Create a mock socket."""
    return mocker.MagicMock()
