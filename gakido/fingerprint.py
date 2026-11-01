"""
Fingerprint self-test: show the TLS/HTTP2 fingerprint servers actually see.

Hits a fingerprint echo service (tls.peet.ws by default) with one or more
impersonation profiles and prints the observed JA3/JA4/HTTP2-Akamai values.
When a verified reference print is stored for a profile, the observed values
are compared against it.

Usage:
    python -m gakido.fingerprint chrome_120
    python -m gakido.fingerprint --all --json
    python -m gakido.fingerprint chrome144 --echo-url https://my-echo/api/all
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import cast

from gakido.client import Client
from gakido.impersonation.profiles import ALIAS_MAP, PROFILES

DEFAULT_ECHO_URL = "https://tls.peet.ws/api/all"

# Reference prints measured against tls.peet.ws with the native backend and
# recorded in docs/antibot-benchmark.md and tests/test_native_tls.py. JA3 is
# intentionally absent for Chromium profiles: the TLS extension order is
# randomized per connection (as real Chrome does), so the JA3 hash varies by
# design while JA4 (order-insensitive) and the HTTP/2 Akamai fingerprint stay
# stable. Only honestly sourced values belong here — do not guess.
REFERENCE_FINGERPRINTS: dict[str, dict[str, str]] = {
    "chrome_120": {
        "ja4": "t13d1516h2_8daaf6152771_02713d6af862",
        "http2_akamai": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
    },
}


@dataclass
class FingerprintResult:
    profile: str
    echo_url: str
    ok: bool
    error: str | None = None
    http_version: str | None = None
    user_agent: str | None = None
    ja3: str | None = None
    ja3_hash: str | None = None
    ja4: str | None = None
    http2_akamai: str | None = None
    reference: dict[str, str] | None = None
    matches: dict[str, bool] | None = None

    @property
    def mismatched(self) -> bool:
        return bool(self.matches) and not all(self.matches.values())


def canonical_profile(name: str) -> str:
    """Resolve an alias (e.g. "chrome120") to its base profile name."""
    resolved = ALIAS_MAP.get(name, name)
    if resolved not in PROFILES:
        raise KeyError(f"Unknown impersonation profile '{name}'")
    return resolved


def base_profiles() -> list[str]:
    """Base profile names, excluding the materialized aliases."""
    return sorted(name for name in PROFILES if name not in ALIAS_MAP)


def get_reference(profile: str) -> dict[str, str] | None:
    try:
        return REFERENCE_FINGERPRINTS.get(canonical_profile(profile))
    except KeyError:
        return None


def _get_item(mapping: object, key: str) -> object:
    if isinstance(mapping, dict):
        return cast("dict[str, object]", mapping).get(key)
    return None


def _get_str(mapping: object, key: str) -> str | None:
    value = _get_item(mapping, key)
    if isinstance(value, str) and value:
        return value
    return None


def parse_echo_payload(data: object) -> dict[str, str | None]:
    """
    Extract the fingerprint fields from a tls.peet.ws /api/all style payload.

    Missing sections (e.g. no "http2" on an HTTP/1.1 connection) yield None
    values instead of raising.
    """
    tls = _get_item(data, "tls")
    http2 = _get_item(data, "http2")
    return {
        "http_version": _get_str(data, "http_version"),
        "user_agent": _get_str(data, "user_agent"),
        "ja3": _get_str(tls, "ja3"),
        "ja3_hash": _get_str(tls, "ja3_hash"),
        "ja4": _get_str(tls, "ja4"),
        "http2_akamai": _get_str(http2, "akamai_fingerprint"),
    }


def _compare(
    parsed: dict[str, str | None], reference: dict[str, str] | None
) -> dict[str, bool] | None:
    if not reference:
        return None
    matches: dict[str, bool] = {}
    for key, expected in reference.items():
        observed = parsed.get(key)
        if observed is not None:
            matches[key] = observed == expected
    return matches or None


def collect_fingerprint(
    profile: str,
    echo_url: str = DEFAULT_ECHO_URL,
    timeout: float = 30.0,
    tls_backend: str = "auto",
) -> FingerprintResult:
    """Request the echo service with one profile and parse what it reports."""
    reference = get_reference(profile)
    try:
        canonical_profile(profile)
    except KeyError as exc:
        message = str(exc.args[0]) if exc.args else str(exc)
        return FingerprintResult(
            profile=profile, echo_url=echo_url, ok=False, error=message
        )
    try:
        with Client(
            impersonate=profile, timeout=timeout, tls_backend=tls_backend
        ) as client:
            response = client.get(echo_url)
    except Exception as exc:
        return FingerprintResult(
            profile=profile,
            echo_url=echo_url,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            reference=reference,
        )
    if response.status_code != 200:
        return FingerprintResult(
            profile=profile,
            echo_url=echo_url,
            ok=False,
            error=f"echo service returned HTTP {response.status_code}",
            reference=reference,
        )
    try:
        payload = response.json()
    except ValueError:
        return FingerprintResult(
            profile=profile,
            echo_url=echo_url,
            ok=False,
            error="echo service returned non-JSON response",
            reference=reference,
        )
    parsed = parse_echo_payload(payload)
    return FingerprintResult(
        profile=profile,
        echo_url=echo_url,
        ok=True,
        http_version=parsed["http_version"],
        user_agent=parsed["user_agent"],
        ja3=parsed["ja3"],
        ja3_hash=parsed["ja3_hash"],
        ja4=parsed["ja4"],
        http2_akamai=parsed["http2_akamai"],
        reference=reference,
        matches=_compare(parsed, reference),
    )


def _annotation(result: FingerprintResult, key: str) -> str:
    if result.matches is None or key not in result.matches:
        return ""
    if result.matches[key]:
        return "  (matches reference)"
    expected = (result.reference or {}).get(key, "")
    return f"  (MISMATCH, expected {expected})"


def format_text(result: FingerprintResult) -> str:
    lines = [f"Profile: {result.profile}  (echo: {result.echo_url})"]
    if not result.ok:
        lines.append(f"  ERROR: {result.error}")
        return "\n".join(lines)
    if result.http_version:
        lines.append(f"  HTTP:          {result.http_version}")
    ja3 = result.ja3_hash or result.ja3 or "n/a"
    lines.append(f"  JA3:           {ja3}")
    lines.append(f"  JA4:           {result.ja4 or 'n/a'}{_annotation(result, 'ja4')}")
    lines.append(
        "  HTTP/2 Akamai: "
        f"{result.http2_akamai or 'n/a'}{_annotation(result, 'http2_akamai')}"
    )
    if result.reference is None:
        lines.append(
            "  No stored reference print for this profile; values are as observed."
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m gakido.fingerprint",
        description=(
            "Show the TLS/HTTP2 fingerprint an echo service sees for gakido's "
            "impersonation profiles."
        ),
    )
    parser.add_argument(
        "profiles",
        nargs="*",
        help="impersonation profile names (default: chrome_120)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="test every base profile",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit results as JSON",
    )
    parser.add_argument(
        "--echo-url",
        default=DEFAULT_ECHO_URL,
        help=f"fingerprint echo endpoint (default: {DEFAULT_ECHO_URL})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--tls-backend",
        choices=["auto", "native", "stdlib"],
        default="auto",
        help="TLS backend to use (default: auto)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.all:
        profiles = base_profiles()
    elif args.profiles:
        profiles = list(args.profiles)
    else:
        profiles = ["chrome_120"]

    results = [
        collect_fingerprint(
            profile,
            echo_url=args.echo_url,
            timeout=args.timeout,
            tls_backend=args.tls_backend,
        )
        for profile in profiles
    ]

    if args.as_json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print("\n\n".join(format_text(result) for result in results))

    failed = any(not result.ok or result.mismatched for result in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
