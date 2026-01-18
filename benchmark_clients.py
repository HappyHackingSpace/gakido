import argparse
import statistics
import sys
import time
from collections.abc import Callable

import httpx
import requests
from gakido import Client


def measure(
    fn: Callable[[], None], runs: int, capture_errors: bool
) -> tuple[list[float], int, list[str]]:
    latencies: list[float] = []
    failures = 0
    errors: list[str] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception as exc:
            failures += 1
            if capture_errors:
                errors.append(f"{type(exc).__name__}: {exc}")
            continue
        t1 = time.perf_counter()
        latencies.append(t1 - t0)
    return latencies, failures, errors


def summary(
    label: str,
    latencies: list[float],
    failures: int,
    runs: int,
    errors: list[str],
) -> None:
    if not latencies:
        print(f"{label:10s} | no successes (failures: {failures}/{runs})")
        if errors:
            from collections import Counter

            top = Counter(errors).most_common(3)
            for err, count in top:
                print(f"  {label:10s} | {count}× {err}")
        return
    latencies_ms = [x * 1000 for x in latencies]
    p50 = statistics.median(latencies_ms)
    p95 = statistics.quantiles(latencies_ms, n=100)[94]
    mean = statistics.fmean(latencies_ms)
    print(
        f"{label:10s} | mean {mean:7.2f} ms | p50 {p50:7.2f} ms | p95 {p95:7.2f} ms | "
        f"min {min(latencies_ms):7.2f} | max {max(latencies_ms):7.2f} | "
        f"fail {failures}/{runs}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Gakido vs requests/httpx.")
    parser.add_argument("url", help="URL to GET")
    parser.add_argument("-n", "--runs", type=int, default=50, help="Number of requests per client")
    parser.add_argument("--impersonate", default="chrome_120", help="Gakido impersonation profile")
    parser.add_argument(
        "--log-failures", action="store_true", help="Print top failure reasons per client"
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print one probe result (status + key headers) per client before timing.",
    )
    args = parser.parse_args()

    url = args.url
    runs = args.runs

    def print_inspect(label: str, status: int, headers: dict[str, str]) -> None:
        cf_ray = headers.get("cf-ray") or headers.get("cf-ray".lower())
        server = headers.get("server")
        print(f"{label:10s} inspect | status {status} | server={server} | cf-ray={cf_ray}")

    with requests.Session() as s:
        def do_requests() -> None:
            resp = s.get(url)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")

        if args.inspect:
            r = s.get(url)
            print_inspect(
                "requests",
                r.status_code,
                {k.lower(): v for k, v in r.headers.items()},
            )

        latencies, failures, errors = measure(do_requests, runs, args.log_failures)
        summary("requests", latencies, failures, runs, errors)

    with httpx.Client(http2=False, follow_redirects=True) as s:
        def do_httpx() -> None:
            resp = s.get(url, follow_redirects=True)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")

        if args.inspect:
            r = s.get(url, follow_redirects=True)
            print_inspect(
                "httpx",
                r.status_code,
                {k.lower(): v for k, v in r.headers.items()},
            )

        latencies, failures, errors = measure(do_httpx, runs, args.log_failures)
        summary("httpx", latencies, failures, runs, errors)

    with Client(impersonate=args.impersonate) as c:
        def do_gakido() -> None:
            resp = c.get(url)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")

        if args.inspect:
            r = c.get(url)
            print_inspect(
                "gakido",
                r.status_code,
                {k.lower(): v for k, v in r.raw_headers},
            )

        latencies, failures, errors = measure(do_gakido, runs, args.log_failures)
        summary("gakido", latencies, failures, runs, errors)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
