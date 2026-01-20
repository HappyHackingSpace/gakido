import copy

PROFILES: dict[str, dict] = {
    "chrome_120": {
        "tls": {
            "ciphers": (
                "TLS_AES_128_GCM_SHA256:"
                "TLS_AES_256_GCM_SHA384:"
                "TLS_CHACHA20_POLY1305_SHA256:"
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:"
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256:"
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:"
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:"
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:"
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:"
                "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA:"
                "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA:"
                "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA:"
                "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA:"
                "TLS_RSA_WITH_AES_128_GCM_SHA256:"
                "TLS_RSA_WITH_AES_256_GCM_SHA384:"
                "TLS_RSA_WITH_AES_128_CBC_SHA:"
                "TLS_RSA_WITH_AES_256_CBC_SHA"
            ),
            "alpn": ["h2", "http/1.1"],
            "curves": ["X25519", "prime256v1", "secp521r1", "secp384r1"],
            "sig_algs": [
                "ecdsa_secp256r1_sha256",
                "rsa_pss_rsae_sha256",
                "rsa_pkcs1_sha256",
                "ecdsa_secp384r1_sha384",
                "rsa_pss_rsae_sha384",
                "rsa_pkcs1_sha384",
                "rsa_pss_rsae_sha512",
                "rsa_pkcs1_sha512",
            ],
        },
        "http2": {
            "settings": {
                "HEADER_TABLE_SIZE": 65536,
                "ENABLE_PUSH": 0,
                "MAX_CONCURRENT_STREAMS": 1000,
                "INITIAL_WINDOW_SIZE": 6291456,
                "MAX_HEADER_LIST_SIZE": 262144,
            },
            "pseudo_header_order": [":method", ":path", ":authority", ":scheme"],
            "alpn": ["h2", "http/1.1"],
        },
        # HTTP/3 (QUIC) settings for Cloudflare/CDN targets
        "http3": {
            "max_stream_data": 1048576,  # 1MB per stream (Chrome-like)
            "max_data": 10485760,  # 10MB total
            "idle_timeout": 30.0,
            "max_streams_bidi": 100,
        },
        "headers": {
            "order": [
                "Host",
                "Connection",
                "Pragma",
                "Cache-Control",
                "Upgrade-Insecure-Requests",
                "User-Agent",
                "Accept",
                "Sec-Fetch-Site",
                "Sec-Fetch-Mode",
                "Sec-Fetch-User",
                "Sec-Fetch-Dest",
                "Accept-Encoding",
                "Accept-Language",
            ],
            "default": [
                ("Connection", "keep-alive"),
                ("Pragma", "no-cache"),
                ("Cache-Control", "no-cache"),
                ("Upgrade-Insecure-Requests", "1"),
                (
                    "User-Agent",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36",
                ),
                (
                    "Accept",
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7",
                ),
                ("Sec-Fetch-Site", "none"),
                ("Sec-Fetch-Mode", "navigate"),
                ("Sec-Fetch-User", "?1"),
                ("Sec-Fetch-Dest", "document"),
                ("Accept-Encoding", "gzip, deflate, br"),
                ("Accept-Language", "en-US,en;q=0.9"),
            ],
        },
    },
    "firefox_120": {
        "tls": {
            "ciphers": (
                "TLS_AES_128_GCM_SHA256:"
                "TLS_CHACHA20_POLY1305_SHA256:"
                "TLS_AES_256_GCM_SHA384:"
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:"
                "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256:"
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:"
                "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:"
                "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:"
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:"
                "TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA:"
                "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA:"
                "TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA:"
                "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA"
            ),
            "alpn": ["h2", "http/1.1"],
            "curves": ["X25519", "secp256r1", "secp384r1"],
            "sig_algs": [
                "ecdsa_secp256r1_sha256",
                "rsa_pss_rsae_sha256",
                "rsa_pkcs1_sha256",
                "ecdsa_secp384r1_sha384",
                "rsa_pss_rsae_sha384",
                "rsa_pkcs1_sha384",
                "rsa_pss_rsae_sha512",
                "rsa_pkcs1_sha512",
            ],
        },
        "http2": {
            "settings": {
                "HEADER_TABLE_SIZE": 65536,
                "ENABLE_PUSH": 0,
                "MAX_CONCURRENT_STREAMS": 256,
                "INITIAL_WINDOW_SIZE": 131072,
                "MAX_HEADER_LIST_SIZE": 8000,
            },
            "pseudo_header_order": [":method", ":path", ":authority", ":scheme"],
            "alpn": ["h2", "http/1.1"],
        },
        # HTTP/3 (QUIC) settings - Firefox has different defaults
        "http3": {
            "max_stream_data": 262144,  # 256KB per stream (Firefox-like)
            "max_data": 1048576,  # 1MB total
            "idle_timeout": 30.0,
            "max_streams_bidi": 100,
        },
        "headers": {
            "order": [
                "Host",
                "User-Agent",
                "Accept",
                "Accept-Language",
                "Accept-Encoding",
                "Connection",
                "Upgrade-Insecure-Requests",
                "Pragma",
                "Cache-Control",
            ],
            "default": [
                (
                    "User-Agent",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) "
                    "Gecko/20100101 Firefox/120.0",
                ),
                (
                    "Accept",
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                ),
                ("Accept-Language", "en-US,en;q=0.5"),
                ("Accept-Encoding", "gzip, deflate, br"),
                ("Connection", "keep-alive"),
                ("Upgrade-Insecure-Requests", "1"),
                ("Pragma", "no-cache"),
                ("Cache-Control", "no-cache"),
            ],
        },
    },
}

# Derived profiles added after base definitions to avoid forward references.
PROFILES["chrome_120_macos_libressl"] = {
    "tls": {
        "ciphers": (
            "ECDHE-ECDSA-AES128-GCM-SHA256:"
            "ECDHE-RSA-AES128-GCM-SHA256:"
            "ECDHE-ECDSA-CHACHA20-POLY1305:"
            "ECDHE-RSA-CHACHA20-POLY1305:"
            "ECDHE-ECDSA-AES256-GCM-SHA384:"
            "ECDHE-RSA-AES256-GCM-SHA384:"
            "ECDHE-ECDSA-AES128-SHA:"
            "ECDHE-RSA-AES128-SHA:"
            "ECDHE-ECDSA-AES256-SHA:"
            "ECDHE-RSA-AES256-SHA:"
            "AES128-GCM-SHA256:"
            "AES256-GCM-SHA384:"
            "AES128-SHA:"
            "AES256-SHA"
        ),
        "alpn": ["h2", "http/1.1"],
        "curves": ["X25519", "prime256v1", "secp384r1"],
        "sig_algs": [
            "ecdsa_secp256r1_sha256",
            "rsa_pss_rsae_sha256",
            "rsa_pkcs1_sha256",
            "ecdsa_secp384r1_sha384",
            "rsa_pss_rsae_sha384",
            "rsa_pkcs1_sha384",
            "rsa_pss_rsae_sha512",
            "rsa_pkcs1_sha512",
        ],
    },
    "http2": PROFILES["chrome_120"]["http2"],
    "headers": PROFILES["chrome_120"]["headers"],
}

PROFILES["chrome_120_android"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            ),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-User", "?1"),
            ("Sec-Fetch-Dest", "document"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ],
    },
}

PROFILES["safari_170"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": {
        "settings": {
            "HEADER_TABLE_SIZE": 65536,
            "ENABLE_PUSH": 0,
            "MAX_CONCURRENT_STREAMS": 100,
            "INITIAL_WINDOW_SIZE": 1048576,
            "MAX_HEADER_LIST_SIZE": 262144,
        },
        "pseudo_header_order": [":method", ":path", ":authority", ":scheme"],
        "alpn": ["h2", "http/1.1"],
    },
    # HTTP/3 (QUIC) settings - Safari/macOS style
    "http3": {
        "max_stream_data": 1048576,  # 1MB per stream
        "max_data": 10485760,  # 10MB total
        "idle_timeout": 30.0,
        "max_streams_bidi": 100,
    },
    "headers": {
        "order": [
            "Host",
            "Connection",
            "Upgrade-Insecure-Requests",
            "User-Agent",
            "Accept",
            "Accept-Language",
            "Accept-Encoding",
        ],
        "default": [
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br"),
        ],
    },
}

PROFILES["safari_170_ios"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["safari_170"]["http2"],
    "headers": {
        "order": PROFILES["safari_170"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br"),
        ],
    },
}

PROFILES["firefox_133"] = {
    "tls": PROFILES["firefox_120"]["tls"],
    "http2": PROFILES["firefox_120"]["http2"],
    "headers": {
        "order": PROFILES["firefox_120"]["headers"]["order"],
        "default": [
            (
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) "
                "Gecko/20100101 Firefox/133.0",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.5"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
        ],
    },
}

PROFILES["firefox_135_android"] = {
    "tls": PROFILES["firefox_120"]["tls"],
    "http2": PROFILES["firefox_120"]["http2"],
    "headers": {
        "order": PROFILES["firefox_120"]["headers"]["order"],
        "default": [
            (
                "User-Agent",
                "Mozilla/5.0 (Android 14; Mobile; rv:135.0) Gecko/135.0 Firefox/135.0",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.5"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
        ],
    },
}

PROFILES["edge_101"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.47",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            ),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-User", "?1"),
            ("Sec-Fetch-Dest", "document"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ],
    },
}

PROFILES["tor_145"] = {
    "tls": PROFILES["firefox_120"]["tls"],
    "http2": PROFILES["firefox_120"]["http2"],
    "headers": {
        "order": PROFILES["firefox_120"]["headers"]["order"],
        "default": [
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; rv:115.0) Gecko/20100101 Firefox/115.0",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.5"),
            ("Accept-Encoding", "gzip, deflate, br"),
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
        ],
    },
}

# Aliases mapping many version labels to a smaller set of base profiles above.
ALIAS_MAP = {
    # Chrome desktop
    "chrome99": "chrome_120",
    "chrome100": "chrome_120",
    "chrome101": "chrome_120",
    "chrome104": "chrome_120",
    "chrome107": "chrome_120",
    "chrome110": "chrome_120",
    "chrome116": "chrome_120",
    "chrome119": "chrome_120",
    "chrome120": "chrome_120",
    "chrome123": "chrome_120",
    "chrome124": "chrome_120",
    "chrome131": "chrome_120",
    "chrome132": "chrome_120",
    "chrome133a": "chrome_120",
    "chrome134": "chrome_120",
    "chrome135": "chrome_120",
    "chrome136": "chrome_120",
    # Chrome Android
    "chrome99_android": "chrome_120_android",
    "chrome131_android": "chrome_120_android",
    "chrome132_android": "chrome_120_android",
    "chrome133_android": "chrome_120_android",
    "chrome134_android": "chrome_120_android",
    "chrome135_android": "chrome_120_android",
    # Safari desktop
    "safari153": "safari_170",
    "safari155": "safari_170",
    "safari170": "safari_170",
    "safari180": "safari_170",
    "safari184": "safari_170",
    "safari260": "safari_170",
    # Safari iOS
    "safari172_ios": "safari_170_ios",
    "safari180_ios": "safari_170_ios",
    "safari184_ios": "safari_170_ios",
    "safari260_ios": "safari_170_ios",
    # Firefox
    "firefox133": "firefox_133",
    "firefox135": "firefox_133",
    # Firefox Android
    "firefox135_android": "firefox_135_android",
    # Tor
    "tor145": "tor_145",
    # Edge
    "edge99": "edge_101",
    "edge101": "edge_101",
    "edge133": "edge_101",
    "edge135": "edge_101",
}

# Materialize aliases into PROFILES for lookup.
for alias, target in list(ALIAS_MAP.items()):
    if alias not in PROFILES and target in PROFILES:
        PROFILES[alias] = PROFILES[target]


def get_profile(name: str) -> dict:
    try:
        return copy.deepcopy(PROFILES[name])
    except KeyError as exc:
        raise KeyError(f"Unknown impersonation profile '{name}'") from exc
