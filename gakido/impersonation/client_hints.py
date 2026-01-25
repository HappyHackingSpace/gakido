"""
Sec-CH-UA Client Hints and Canvas/WebGL fingerprint utilities.

This module provides functions to generate and customize browser client hints
headers for better impersonation, as well as canvas/webgl fingerprint data.
"""

from __future__ import annotations

from typing import Any


def generate_sec_ch_ua(
    browser: str,
    version: str,
    chromium_version: str | None = None,
) -> str:
    """
    Generate a Sec-CH-UA header value.

    Args:
        browser: Browser name (e.g., "Google Chrome", "Microsoft Edge")
        version: Browser major version (e.g., "120")
        chromium_version: Chromium version if different from browser version

    Returns:
        Formatted Sec-CH-UA header value
    """
    chromium_ver = chromium_version or version
    # Use a "Not A Brand" placeholder that varies by version
    not_a_brand_ver = str(int(version) % 24) if version.isdigit() else "8"
    return f'"Not_A Brand";v="{not_a_brand_ver}", "Chromium";v="{chromium_ver}", "{browser}";v="{version}"'


def generate_sec_ch_ua_full_version_list(
    browser: str,
    full_version: str,
    chromium_full_version: str | None = None,
) -> str:
    """
    Generate a Sec-CH-UA-Full-Version-List header value.

    Args:
        browser: Browser name (e.g., "Google Chrome", "Microsoft Edge")
        full_version: Full browser version (e.g., "120.0.6099.129")
        chromium_full_version: Full Chromium version if different

    Returns:
        Formatted Sec-CH-UA-Full-Version-List header value
    """
    chromium_ver = chromium_full_version or full_version
    major = full_version.split(".")[0] if "." in full_version else full_version
    not_a_brand_ver = str(int(major) % 24) if major.isdigit() else "8"
    return (
        f'"Not_A Brand";v="{not_a_brand_ver}.0.0.0", '
        f'"Chromium";v="{chromium_ver}", '
        f'"{browser}";v="{full_version}"'
    )


def get_client_hints_headers(
    profile: dict[str, Any],
    include_high_entropy: bool = False,
) -> dict[str, str]:
    """
    Extract client hints headers from a profile.

    Args:
        profile: Browser impersonation profile
        include_high_entropy: Include high-entropy hints (platform version, arch, etc.)

    Returns:
        Dictionary of client hints headers
    """
    client_hints = profile.get("client_hints", {})
    if not client_hints:
        return {}

    # Basic client hints (low entropy, sent by default)
    headers = {}
    basic_hints = ["Sec-CH-UA", "Sec-CH-UA-Mobile", "Sec-CH-UA-Platform"]
    for hint in basic_hints:
        if hint in client_hints:
            headers[hint] = client_hints[hint]

    # High-entropy hints (only sent when requested via Accept-CH)
    if include_high_entropy:
        high_entropy_hints = [
            "Sec-CH-UA-Platform-Version",
            "Sec-CH-UA-Full-Version-List",
            "Sec-CH-UA-Arch",
            "Sec-CH-UA-Bitness",
            "Sec-CH-UA-Model",
        ]
        for hint in high_entropy_hints:
            if hint in client_hints:
                headers[hint] = client_hints[hint]

    return headers


def get_canvas_webgl_fingerprint(profile: dict[str, Any]) -> dict[str, str]:
    """
    Extract canvas/WebGL fingerprint data from a profile.

    Args:
        profile: Browser impersonation profile

    Returns:
        Dictionary with webgl_vendor, webgl_renderer, and canvas_hash
    """
    return profile.get("canvas_webgl", {})


def build_client_hints_for_platform(
    browser: str,
    version: str,
    platform: str,
    mobile: bool = False,
    platform_version: str = "",
    arch: str = "",
    bitness: str = "64",
    model: str = "",
) -> dict[str, str]:
    """
    Build a complete set of client hints for a given platform.

    Args:
        browser: Browser name (e.g., "Google Chrome")
        version: Browser major version
        platform: Platform name (e.g., "macOS", "Windows", "Android")
        mobile: Whether this is a mobile device
        platform_version: Platform version (e.g., "14.0.0" for macOS)
        arch: Architecture (e.g., "arm", "x86")
        bitness: Bitness (e.g., "64", "32")
        model: Device model (e.g., "Pixel 7" for Android)

    Returns:
        Dictionary of all client hints headers
    """
    sec_ch_ua = generate_sec_ch_ua(browser, version)
    full_version = f"{version}.0.0.0"
    sec_ch_ua_full = generate_sec_ch_ua_full_version_list(browser, full_version)

    return {
        "Sec-CH-UA": sec_ch_ua,
        "Sec-CH-UA-Mobile": "?1" if mobile else "?0",
        "Sec-CH-UA-Platform": f'"{platform}"',
        "Sec-CH-UA-Platform-Version": f'"{platform_version}"' if platform_version else '""',
        "Sec-CH-UA-Full-Version-List": sec_ch_ua_full,
        "Sec-CH-UA-Arch": f'"{arch}"' if arch else '""',
        "Sec-CH-UA-Bitness": f'"{bitness}"',
        "Sec-CH-UA-Model": f'"{model}"' if model else '""',
    }


def parse_accept_ch(accept_ch_header: str) -> list[str]:
    """
    Parse an Accept-CH header to determine which client hints are requested.

    Args:
        accept_ch_header: Value of the Accept-CH response header

    Returns:
        List of requested client hint names
    """
    if not accept_ch_header:
        return []
    return [hint.strip() for hint in accept_ch_header.split(",") if hint.strip()]


def should_send_hint(hint_name: str, accept_ch_hints: list[str]) -> bool:
    """
    Determine if a specific client hint should be sent based on Accept-CH.

    Args:
        hint_name: Name of the client hint header
        accept_ch_hints: List of hints from Accept-CH header

    Returns:
        True if the hint should be sent
    """
    # Basic hints are always sent
    basic_hints = {"Sec-CH-UA", "Sec-CH-UA-Mobile", "Sec-CH-UA-Platform"}
    if hint_name in basic_hints:
        return True

    # High-entropy hints only sent if requested
    return hint_name in accept_ch_hints


# Common WebGL renderer strings for various platforms
WEBGL_RENDERERS = {
    "chrome_macos_m1": {
        "vendor": "Google Inc. (Apple)",
        "renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)",
    },
    "chrome_macos_intel": {
        "vendor": "Google Inc. (Intel Inc.)",
        "renderer": "ANGLE (Intel Inc., Intel(R) Iris(TM) Plus Graphics 655, OpenGL 4.1)",
    },
    "chrome_windows_nvidia": {
        "vendor": "Google Inc. (NVIDIA)",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    "chrome_windows_amd": {
        "vendor": "Google Inc. (AMD)",
        "renderer": "ANGLE (AMD, AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    "chrome_android_adreno": {
        "vendor": "Qualcomm",
        "renderer": "Adreno (TM) 730",
    },
    "chrome_android_mali": {
        "vendor": "ARM",
        "renderer": "Mali-G78",
    },
    "firefox_macos": {
        "vendor": "Google Inc. (Apple)",
        "renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)",
    },
    "safari_macos": {
        "vendor": "Apple Inc.",
        "renderer": "Apple GPU",
    },
    "safari_ios": {
        "vendor": "Apple Inc.",
        "renderer": "Apple GPU",
    },
    "tor": {
        "vendor": "Mozilla",
        "renderer": "Mozilla",
    },
}


def get_webgl_renderer(platform_key: str) -> dict[str, str]:
    """
    Get WebGL renderer info for a specific platform.

    Args:
        platform_key: Key from WEBGL_RENDERERS dict

    Returns:
        Dictionary with vendor and renderer strings
    """
    return WEBGL_RENDERERS.get(platform_key, WEBGL_RENDERERS["chrome_macos_m1"])
