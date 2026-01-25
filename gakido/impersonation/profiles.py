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
                "Sec-CH-UA",
                "Sec-CH-UA-Mobile",
                "Sec-CH-UA-Platform",
                "Sec-CH-UA-Platform-Version",
                "Sec-CH-UA-Full-Version-List",
                "Sec-CH-UA-Arch",
                "Sec-CH-UA-Bitness",
                "Sec-CH-UA-Model",
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
                (
                    "Sec-CH-UA",
                    '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                ),
                ("Sec-CH-UA-Mobile", "?0"),
                ("Sec-CH-UA-Platform", '"macOS"'),
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
        "client_hints": {
            "Sec-CH-UA": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
            "Sec-CH-UA-Platform-Version": '"14.0.0"',
            "Sec-CH-UA-Full-Version-List": '"Not_A Brand";v="8.0.0.0", "Chromium";v="120.0.6099.129", "Google Chrome";v="120.0.6099.129"',
            "Sec-CH-UA-Arch": '"arm"',
            "Sec-CH-UA-Bitness": '"64"',
            "Sec-CH-UA-Model": '""',
        },
        "canvas_webgl": {
            "webgl_vendor": "Google Inc. (Apple)",
            "webgl_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)",
            "canvas_hash": "a]@~)!@#$%^&*()_+{}|:<>?`-=[]\\;',./",
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
        "canvas_webgl": {
            "webgl_vendor": "Google Inc. (Apple)",
            "webgl_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)",
            "canvas_hash": "firefox_120_macos_canvas_fp",
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
            (
                "Sec-CH-UA",
                '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            ),
            ("Sec-CH-UA-Mobile", "?1"),
            ("Sec-CH-UA-Platform", '"Android"'),
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
    "client_hints": {
        "Sec-CH-UA": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-CH-UA-Mobile": "?1",
        "Sec-CH-UA-Platform": '"Android"',
        "Sec-CH-UA-Platform-Version": '"14.0.0"',
        "Sec-CH-UA-Full-Version-List": '"Not_A Brand";v="8.0.0.0", "Chromium";v="120.0.6099.129", "Google Chrome";v="120.0.6099.129"',
        "Sec-CH-UA-Arch": '""',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '"Pixel 7"',
    },
    "canvas_webgl": {
        "webgl_vendor": "Qualcomm",
        "webgl_renderer": "Adreno (TM) 730",
        "canvas_hash": "android_pixel7_canvas_fp",
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
    "canvas_webgl": {
        "webgl_vendor": "Apple Inc.",
        "webgl_renderer": "Apple GPU",
        "canvas_hash": "safari_macos_canvas_fp",
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
    "canvas_webgl": {
        "webgl_vendor": "Apple Inc.",
        "webgl_renderer": "Apple GPU",
        "canvas_hash": "safari_ios_canvas_fp",
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
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (Apple)",
        "webgl_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)",
        "canvas_hash": "firefox_macos_canvas_fp",
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
    "canvas_webgl": {
        "webgl_vendor": "Qualcomm",
        "webgl_renderer": "Adreno (TM) 730",
        "canvas_hash": "firefox_android_canvas_fp",
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
            (
                "Sec-CH-UA",
                '"Not A(Brand";v="99", "Microsoft Edge";v="101", "Chromium";v="101"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Windows"'),
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
    "client_hints": {
        "Sec-CH-UA": '"Not A(Brand";v="99", "Microsoft Edge";v="101", "Chromium";v="101"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Platform-Version": '"10.0.0"',
        "Sec-CH-UA-Full-Version-List": '"Not A(Brand";v="99.0.0.0", "Microsoft Edge";v="101.0.1210.47", "Chromium";v="101.0.4951.64"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "canvas_hash": "edge_windows_canvas_fp",
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
    "canvas_webgl": {
        "webgl_vendor": "Mozilla",
        "webgl_renderer": "Mozilla",
        "canvas_hash": "tor_uniform_canvas_fp",
    },
}

# Chrome 131 - Windows (latest stable as of late 2024)
PROFILES["chrome_131_windows"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Chromium";v="131", "Google Chrome";v="131", "Not_A Brand";v="24"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Windows"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ],
    },
    "client_hints": {
        "Sec-CH-UA": '"Chromium";v="131", "Google Chrome";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Platform-Version": '"10.0.0"',
        "Sec-CH-UA-Full-Version-List": '"Chromium";v="131.0.6778.85", "Google Chrome";v="131.0.6778.85", "Not_A Brand";v="24.0.0.0"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "canvas_hash": "chrome_131_windows_canvas_fp",
    },
}

# Chrome 136 - Linux (latest as of early 2025)
PROFILES["chrome_136_linux"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Chromium";v="136", "Google Chrome";v="136", "Not_A Brand";v="24"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Linux"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
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
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ],
    },
    "client_hints": {
        "Sec-CH-UA": '"Chromium";v="136", "Google Chrome";v="136", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Linux"',
        "Sec-CH-UA-Platform-Version": '"6.5.0"',
        "Sec-CH-UA-Full-Version-List": '"Chromium";v="136.0.0.0", "Google Chrome";v="136.0.0.0", "Not_A Brand";v="24.0.0.0"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Mesa Intel(R) UHD Graphics 630 (CFL GT2), OpenGL 4.6)",
        "canvas_hash": "chrome_136_linux_canvas_fp",
    },
}

# Chrome 144 - Latest (2025)
PROFILES["chrome_144"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"macOS"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
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
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ],
    },
    "client_hints": {
        "Sec-CH-UA": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
        "Sec-CH-UA-Platform-Version": '"14.5.0"',
        "Sec-CH-UA-Full-Version-List": '"Not(A:Brand";v="8.0.0.0", "Chromium";v="144.0.0.0", "Google Chrome";v="144.0.0.0"',
        "Sec-CH-UA-Arch": '"arm"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (Apple)",
        "webgl_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Unspecified Version)",
        "canvas_hash": "chrome_144_macos_canvas_fp",
    },
}

# Firefox 147 - Latest (2025)
PROFILES["firefox_147"] = {
    "tls": PROFILES["firefox_120"]["tls"],
    "http2": PROFILES["firefox_120"]["http2"],
    "http3": PROFILES["firefox_120"].get("http3", {}),
    "headers": {
        "order": [
            "Host",
            "User-Agent",
            "Accept",
            "Accept-Language",
            "Accept-Encoding",
            "Connection",
            "Upgrade-Insecure-Requests",
            "Sec-Fetch-Dest",
            "Sec-Fetch-Mode",
            "Sec-Fetch-Site",
            "Sec-Fetch-User",
            "Priority",
        ],
        "default": [
            (
                "User-Agent",
                "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            ("Sec-Fetch-Dest", "document"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-User", "?1"),
            ("Priority", "u=0, i"),
        ],
    },
    "canvas_webgl": {
        "webgl_vendor": "Intel",
        "webgl_renderer": "Mesa Intel(R) UHD Graphics 630 (CFL GT2)",
        "canvas_hash": "firefox_147_linux_canvas_fp",
    },
}

# Firefox 147 macOS
PROFILES["firefox_147_macos"] = {
    "tls": PROFILES["firefox_120"]["tls"],
    "http2": PROFILES["firefox_120"]["http2"],
    "http3": PROFILES["firefox_120"].get("http3", {}),
    "headers": {
        "order": PROFILES["firefox_147"]["headers"]["order"],
        "default": [
            (
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:147.0) Gecko/20100101 Firefox/147.0",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            ("Sec-Fetch-Dest", "document"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-User", "?1"),
            ("Priority", "u=0, i"),
        ],
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (Apple)",
        "webgl_renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Unspecified Version)",
        "canvas_hash": "firefox_147_macos_canvas_fp",
    },
}

# Safari 18.4 macOS Sonoma
PROFILES["safari_184_macos"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["safari_170"]["http2"],
    "http3": PROFILES["safari_170"].get("http3", {}),
    "headers": {
        "order": [
            "Host",
            "Connection",
            "Upgrade-Insecure-Requests",
            "User-Agent",
            "Accept",
            "Sec-Fetch-Site",
            "Sec-Fetch-Mode",
            "Sec-Fetch-Dest",
            "Accept-Language",
            "Accept-Encoding",
        ],
        "default": [
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4.1 Safari/605.1.15",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Sec-Fetch-Site", "none"),
            ("Sec-Fetch-Mode", "navigate"),
            ("Sec-Fetch-Dest", "document"),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br"),
        ],
    },
    "canvas_webgl": {
        "webgl_vendor": "Apple Inc.",
        "webgl_renderer": "Apple M3 Pro",
        "canvas_hash": "safari_184_macos_canvas_fp",
    },
}

# Safari 18.7 iOS 18
PROFILES["safari_187_ios"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["safari_170"]["http2"],
    "headers": {
        "order": PROFILES["safari_170"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.7 Mobile/15E148 Safari/604.1",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br"),
        ],
    },
    "canvas_webgl": {
        "webgl_vendor": "Apple Inc.",
        "webgl_renderer": "Apple GPU",
        "canvas_hash": "safari_187_ios_canvas_fp",
    },
}

# Safari 26 iOS (2025 - new versioning scheme)
PROFILES["safari_26_ios"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["safari_170"]["http2"],
    "headers": {
        "order": PROFILES["safari_170"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br"),
        ],
    },
    "canvas_webgl": {
        "webgl_vendor": "Apple Inc.",
        "webgl_renderer": "Apple GPU",
        "canvas_hash": "safari_26_ios_canvas_fp",
    },
}

# Safari iPad
PROFILES["safari_184_ipad"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["safari_170"]["http2"],
    "headers": {
        "order": PROFILES["safari_170"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (iPad; CPU OS 18_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            ("Accept-Language", "en-US,en;q=0.9"),
            ("Accept-Encoding", "gzip, deflate, br"),
        ],
    },
    "canvas_webgl": {
        "webgl_vendor": "Apple Inc.",
        "webgl_renderer": "Apple GPU",
        "canvas_hash": "safari_184_ipad_canvas_fp",
    },
}

# Edge 131 Windows
PROFILES["edge_131"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Windows"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
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
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ],
    },
    "client_hints": {
        "Sec-CH-UA": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Platform-Version": '"10.0.0"',
        "Sec-CH-UA-Full-Version-List": '"Microsoft Edge";v="131.0.2903.86", "Chromium";v="131.0.6778.85", "Not_A Brand";v="24.0.0.0"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "canvas_hash": "edge_131_windows_canvas_fp",
    },
}

# Edge 144 (latest 2025)
PROFILES["edge_144"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Windows"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
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
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Accept-Language", "en-US,en;q=0.9"),
        ],
    },
    "client_hints": {
        "Sec-CH-UA": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Platform-Version": '"10.0.0"',
        "Sec-CH-UA-Full-Version-List": '"Not(A:Brand";v="8.0.0.0", "Chromium";v="144.0.0.0", "Microsoft Edge";v="144.0.0.0"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "canvas_hash": "edge_144_windows_canvas_fp",
    },
}

# Opera 115 (Chromium-based)
PROFILES["opera_115"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Chromium";v="129", "Opera";v="115", "Not=A?Brand";v="8"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Windows"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 OPR/115.0.0.0",
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
    "client_hints": {
        "Sec-CH-UA": '"Chromium";v="129", "Opera";v="115", "Not=A?Brand";v="8"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Platform-Version": '"10.0.0"',
        "Sec-CH-UA-Full-Version-List": '"Chromium";v="129.0.0.0", "Opera";v="115.0.0.0", "Not=A?Brand";v="8.0.0.0"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "canvas_hash": "opera_115_windows_canvas_fp",
    },
}

# Brave Browser (Chromium-based, privacy-focused)
PROFILES["brave_131"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Windows"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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
    "client_hints": {
        "Sec-CH-UA": '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Platform-Version": '"10.0.0"',
        "Sec-CH-UA-Full-Version-List": '"Brave";v="131.0.0.0", "Chromium";v="131.0.6778.85", "Not_A Brand";v="24.0.0.0"',
        "Sec-CH-UA-Arch": '"x86"',
        "Sec-CH-UA-Bitness": '"64"',
        "Sec-CH-UA-Model": '""',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "canvas_hash": "brave_131_windows_canvas_fp",
    },
}

# Vivaldi Browser (Chromium-based)
PROFILES["vivaldi_7"] = {
    "tls": PROFILES["chrome_120"]["tls"],
    "http2": PROFILES["chrome_120"]["http2"],
    "http3": PROFILES["chrome_120"]["http3"],
    "headers": {
        "order": PROFILES["chrome_120"]["headers"]["order"],
        "default": [
            ("Connection", "keep-alive"),
            ("Pragma", "no-cache"),
            ("Cache-Control", "no-cache"),
            (
                "Sec-CH-UA",
                '"Chromium";v="130", "Not_A Brand";v="24"',
            ),
            ("Sec-CH-UA-Mobile", "?0"),
            ("Sec-CH-UA-Platform", '"Windows"'),
            ("Upgrade-Insecure-Requests", "1"),
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
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
    "client_hints": {
        "Sec-CH-UA": '"Chromium";v="130", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    "canvas_webgl": {
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "canvas_hash": "vivaldi_7_windows_canvas_fp",
    },
}

# Aliases mapping many version labels to a smaller set of base profiles above.
ALIAS_MAP = {
    # Chrome desktop (older versions -> chrome_120)
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
    # Chrome desktop (newer versions -> specific profiles)
    "chrome131": "chrome_131_windows",
    "chrome131_windows": "chrome_131_windows",
    "chrome132": "chrome_131_windows",
    "chrome133": "chrome_131_windows",
    "chrome133a": "chrome_131_windows",
    "chrome134": "chrome_136_linux",
    "chrome135": "chrome_136_linux",
    "chrome136": "chrome_136_linux",
    "chrome136_linux": "chrome_136_linux",
    "chrome144": "chrome_144",
    "chrome144_macos": "chrome_144",
    # Chrome Android
    "chrome99_android": "chrome_120_android",
    "chrome131_android": "chrome_120_android",
    "chrome132_android": "chrome_120_android",
    "chrome133_android": "chrome_120_android",
    "chrome134_android": "chrome_120_android",
    "chrome135_android": "chrome_120_android",
    "chrome144_android": "chrome_120_android",
    # Safari desktop
    "safari153": "safari_170",
    "safari155": "safari_170",
    "safari170": "safari_170",
    "safari180": "safari_184_macos",
    "safari184": "safari_184_macos",
    "safari184_macos": "safari_184_macos",
    "safari260": "safari_184_macos",
    # Safari iOS
    "safari172_ios": "safari_170_ios",
    "safari180_ios": "safari_187_ios",
    "safari184_ios": "safari_187_ios",
    "safari187_ios": "safari_187_ios",
    "safari260_ios": "safari_26_ios",
    "safari26_ios": "safari_26_ios",
    # Safari iPad
    "safari184_ipad": "safari_184_ipad",
    "safari186_ipad": "safari_184_ipad",
    # Firefox desktop
    "firefox133": "firefox_133",
    "firefox135": "firefox_133",
    "firefox140": "firefox_147",
    "firefox145": "firefox_147",
    "firefox147": "firefox_147",
    "firefox147_linux": "firefox_147",
    "firefox147_macos": "firefox_147_macos",
    # Firefox Android
    "firefox135_android": "firefox_135_android",
    "firefox147_android": "firefox_135_android",
    # Tor
    "tor145": "tor_145",
    "tor150": "tor_145",
    # Edge
    "edge99": "edge_101",
    "edge101": "edge_101",
    "edge131": "edge_131",
    "edge131_windows": "edge_131",
    "edge133": "edge_131",
    "edge135": "edge_131",
    "edge140": "edge_144",
    "edge144": "edge_144",
    "edge144_windows": "edge_144",
    # Opera
    "opera115": "opera_115",
    "opera115_windows": "opera_115",
    "opera120": "opera_115",
    # Brave
    "brave131": "brave_131",
    "brave131_windows": "brave_131",
    "brave135": "brave_131",
    # Vivaldi
    "vivaldi7": "vivaldi_7",
    "vivaldi7_windows": "vivaldi_7",
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
