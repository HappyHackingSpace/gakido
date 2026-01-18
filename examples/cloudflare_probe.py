"""
Probe a Cloudflare-protected URL with different impersonation profiles.

Usage:
    uv run python examples/cloudflare_probe.py --url https://your-cf-site/ [--h2]

Notes:
    - By default, force_http1=True to avoid HTTP/2 drops; pass --h2 to allow h2.
    - Accept-Encoding is set to identity to simplify body handling.
    - You should supply a URL you control or are allowed to test.
"""

import argparse

from gakido import Client


PROFILES = [
    "chrome_120",
    "firefox_133",
    "safari_170",
    "edge_101",
    "chrome_120_macos_libressl",
]


def run(url: str, allow_h2: bool) -> None:
    for profile in PROFILES:
        try:
            c = Client(
                impersonate=profile,
                force_http1=not allow_h2,
            )
            with c:
                resp = c.get(url, headers={"Accept-Encoding": "identity"})
            status = resp.status_code
            server = resp.headers.get("server")
            cf_ray = resp.headers.get("cf-ray")
            print(
                f"{profile:25s} status={status} server={server} cf-ray={cf_ray} "
                f"body_snippet={resp.text[:120].replace('\\n', ' ')}"
            )
        except Exception as exc:
            print(f"{profile:25s} error={exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe a Cloudflare-protected URL.")
    parser.add_argument("--url", required=True, help="Target URL (CF-protected).")
    parser.add_argument(
        "--h2",
        action="store_true",
        help="Allow HTTP/2 (force_http1 will be disabled).",
    )
    args = parser.parse_args()
    run(args.url, allow_h2=args.h2)


if __name__ == "__main__":
    main()
