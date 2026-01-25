#!/usr/bin/env python3
"""
Antibot Systems Benchmark for Gakido

Benchmarks gakido's browser impersonation against various antibot detection systems.
Tests TLS fingerprinting, HTTP headers, client hints, and bot detection endpoints.

Usage:
    uv run python examples/antibot_benchmark.py
    uv run python examples/antibot_benchmark.py --profile chrome_144
    uv run python examples/antibot_benchmark.py --all-profiles
    uv run python examples/antibot_benchmark.py --async
    uv run python examples/antibot_benchmark.py --output results.json

Test Categories:
    1. TLS Fingerprint Tests (JA3/JA4)
    2. HTTP Header Analysis
    3. Bot Detection Services
    4. Cloudflare Challenge Pages
    5. Browser Consistency Checks
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from gakido import Client
from gakido.aio import AsyncClient
from gakido.impersonation import (
    get_profile,
    get_client_hints_headers,
    get_canvas_webgl_fingerprint,
)
from gakido.impersonation.profiles import PROFILES, ALIAS_MAP

try:
    from importlib.metadata import version as get_version
    GAKIDO_VERSION = get_version("gakido")
except Exception:
    GAKIDO_VERSION = "0.1.0"


# =============================================================================
# Test Endpoints
# =============================================================================

# TLS Fingerprint Analysis
TLS_ENDPOINTS = {
    "tls_browserleaks": {
        "url": "https://tls.browserleaks.com/json",
        "description": "TLS/JA3 fingerprint analysis",
        "check": lambda r: r.get("ja3_hash") is not None,
    },
    "scrapfly_ja3": {
        "url": "https://tools.scrapfly.io/api/fp/ja3",
        "description": "Scrapfly JA3 fingerprint",
        "check": lambda r: True,
    },
}

# HTTP Header Analysis
HEADER_ENDPOINTS = {
    "httpbin_headers": {
        "url": "https://httpbin.org/headers",
        "description": "HTTP header echo service",
        "check": lambda r: "headers" in r,
    },
    "httpbin_user_agent": {
        "url": "https://httpbin.org/user-agent",
        "description": "User-Agent echo",
        "check": lambda r: "user-agent" in r,
    },
}

# Bot Detection Services (public test pages)
BOT_DETECTION_ENDPOINTS = {
    "nowsecure": {
        "url": "https://nowsecure.nl/",
        "description": "NowSecure bot detection test",
        "check": lambda r: True,
        "check_status": lambda s: s == 200,
        "is_text": True,
    },
    "sannysoft": {
        "url": "https://bot.sannysoft.com/",
        "description": "Sannysoft bot detection test",
        "check": lambda r: True,
        "check_status": lambda s: s == 200,
        "is_text": True,
    },
    "incolumitas": {
        "url": "https://bot.incolumitas.com/",
        "description": "Incolumitas bot detection",
        "check": lambda r: True,
        "check_status": lambda s: s == 200,
        "is_text": True,
    },
}

# Cloudflare Protected Sites (for challenge detection)
CLOUDFLARE_ENDPOINTS = {
    "cloudflare_trace": {
        "url": "https://cloudflare.com/cdn-cgi/trace",
        "description": "Cloudflare trace endpoint",
        "check": lambda r: "fl=" in r if isinstance(r, str) else True,
        "is_text": True,
    },
    "cloudflare_1111": {
        "url": "https://1.1.1.1/cdn-cgi/trace",
        "description": "Cloudflare 1.1.1.1 trace",
        "check": lambda r: "fl=" in r if isinstance(r, str) else True,
        "is_text": True,
    },
}

# Browser Consistency Checks
CONSISTENCY_ENDPOINTS = {
    "whatismybrowser": {
        "url": "https://www.whatismybrowser.com/detect/what-http-headers-is-my-browser-sending",
        "description": "Browser header analysis",
        "check": lambda r: True,
    },
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TestResult:
    """Result of a single test."""
    endpoint_name: str
    url: str
    description: str
    success: bool
    status_code: int | None = None
    response_time_ms: float = 0.0
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileBenchmark:
    """Benchmark results for a single profile."""
    profile_name: str
    platform: str
    has_client_hints: bool
    has_canvas_webgl: bool
    user_agent: str
    tests: list[TestResult] = field(default_factory=list)
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    success_rate: float = 0.0
    avg_response_time_ms: float = 0.0

    def calculate_stats(self) -> None:
        """Calculate aggregate statistics."""
        self.total_tests = len(self.tests)
        self.passed_tests = sum(1 for t in self.tests if t.success)
        self.failed_tests = self.total_tests - self.passed_tests
        self.success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0.0
        response_times = [t.response_time_ms for t in self.tests if t.response_time_ms > 0]
        self.avg_response_time_ms = sum(response_times) / len(response_times) if response_times else 0.0


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    timestamp: str
    gakido_version: str
    total_profiles_tested: int
    total_tests_run: int
    overall_success_rate: float
    profiles: list[ProfileBenchmark] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Benchmark Runner
# =============================================================================

class AntibotBenchmark:
    """Antibot systems benchmark runner."""

    # Profiles to test by default (representative set)
    DEFAULT_PROFILES = [
        "chrome_120",
        "chrome_144",
        "chrome_131_windows",
        "chrome_136_linux",
        "firefox_133",
        "firefox_147",
        "safari_184_macos",
        "safari_187_ios",
        "edge_131",
        "edge_144",
        "brave_131",
        "opera_115",
        "tor_145",
    ]

    def __init__(
        self,
        profiles: list[str] | None = None,
        timeout: float = 15.0,
        verbose: bool = True,
    ):
        self.profiles = profiles or self.DEFAULT_PROFILES
        self.timeout = timeout
        self.verbose = verbose
        self.results: list[ProfileBenchmark] = []

    def log(self, msg: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(msg)

    def get_profile_info(self, profile_name: str) -> dict[str, Any]:
        """Get profile metadata."""
        try:
            profile = get_profile(profile_name)
            user_agent = ""
            for name, val in profile.get("headers", {}).get("default", []):
                if name == "User-Agent":
                    user_agent = val
                    break

            # Determine platform from user agent
            platform = "unknown"
            ua_lower = user_agent.lower()
            if "windows" in ua_lower:
                platform = "Windows"
            elif "macintosh" in ua_lower or "mac os" in ua_lower:
                platform = "macOS"
            elif "linux" in ua_lower and "android" not in ua_lower:
                platform = "Linux"
            elif "android" in ua_lower:
                platform = "Android"
            elif "iphone" in ua_lower:
                platform = "iOS"
            elif "ipad" in ua_lower:
                platform = "iPadOS"

            return {
                "user_agent": user_agent,
                "platform": platform,
                "has_client_hints": bool(profile.get("client_hints")),
                "has_canvas_webgl": bool(profile.get("canvas_webgl")),
                "client_hints": get_client_hints_headers(profile, include_high_entropy=False),
                "canvas_webgl": get_canvas_webgl_fingerprint(profile),
            }
        except Exception as e:
            return {
                "user_agent": "",
                "platform": "unknown",
                "has_client_hints": False,
                "has_canvas_webgl": False,
                "error": str(e),
            }

    def run_single_test(
        self,
        client: Client,
        endpoint_name: str,
        endpoint_config: dict[str, Any],
    ) -> TestResult:
        """Run a single test endpoint."""
        url = endpoint_config["url"]
        description = endpoint_config.get("description", "")
        is_text = endpoint_config.get("is_text", False)
        check_fn = endpoint_config.get("check", lambda r: True)
        check_status_fn = endpoint_config.get("check_status", lambda s: s in (200, 201, 202, 204))

        start_time = time.perf_counter()
        try:
            resp = client.get(url, headers={"Accept-Encoding": "identity"})
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            status_ok = check_status_fn(resp.status_code)

            if is_text:
                content = resp.text
                check_ok = check_fn(content)
                details = {"content_preview": content[:200]}
            else:
                try:
                    data = resp.json()
                    check_ok = check_fn(data)
                    details = {"response": data}
                except Exception:
                    check_ok = False
                    details = {"raw_content": resp.text[:500]}

            success = status_ok and check_ok

            return TestResult(
                endpoint_name=endpoint_name,
                url=url,
                description=description,
                success=success,
                status_code=resp.status_code,
                response_time_ms=elapsed_ms,
                details=details,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return TestResult(
                endpoint_name=endpoint_name,
                url=url,
                description=description,
                success=False,
                response_time_ms=elapsed_ms,
                error=str(e),
            )

    def benchmark_profile(self, profile_name: str) -> ProfileBenchmark:
        """Run all tests for a single profile."""
        self.log(f"\n{'='*60}")
        self.log(f"Testing profile: {profile_name}")
        self.log(f"{'='*60}")

        info = self.get_profile_info(profile_name)

        benchmark = ProfileBenchmark(
            profile_name=profile_name,
            platform=info["platform"],
            has_client_hints=info["has_client_hints"],
            has_canvas_webgl=info["has_canvas_webgl"],
            user_agent=info["user_agent"][:80] + "..." if len(info["user_agent"]) > 80 else info["user_agent"],
        )

        # Create client
        try:
            client = Client(
                impersonate=profile_name,
                timeout=self.timeout,
                force_http1=True,
            )
        except Exception as e:
            self.log(f"  ❌ Failed to create client: {e}")
            return benchmark

        # Run all endpoint categories
        all_endpoints = {
            **TLS_ENDPOINTS,
            **HEADER_ENDPOINTS,
            **BOT_DETECTION_ENDPOINTS,
            **CLOUDFLARE_ENDPOINTS,
        }

        with client:
            for endpoint_name, endpoint_config in all_endpoints.items():
                result = self.run_single_test(client, endpoint_name, endpoint_config)
                benchmark.tests.append(result)

                status_icon = "✅" if result.success else "❌"
                time_str = f"{result.response_time_ms:.0f}ms"
                status_str = f"HTTP {result.status_code}" if result.status_code else "ERROR"

                self.log(f"  {status_icon} {endpoint_name:25s} {status_str:10s} {time_str:8s}")

                if result.error:
                    self.log(f"      Error: {result.error[:60]}")

        benchmark.calculate_stats()

        self.log(f"\n  Summary: {benchmark.passed_tests}/{benchmark.total_tests} passed "
                 f"({benchmark.success_rate:.1f}%) | Avg: {benchmark.avg_response_time_ms:.0f}ms")

        return benchmark

    def run(self) -> BenchmarkReport:
        """Run the complete benchmark."""
        self.log("\n" + "="*70)
        self.log("  GAKIDO ANTIBOT SYSTEMS BENCHMARK")
        self.log("="*70)
        self.log(f"Profiles to test: {len(self.profiles)}")
        self.log(f"Timeout: {self.timeout}s")

        for profile_name in self.profiles:
            benchmark = self.benchmark_profile(profile_name)
            self.results.append(benchmark)

        # Generate report
        report = self.generate_report()
        self.print_summary(report)

        return report

    def generate_report(self) -> BenchmarkReport:
        """Generate the benchmark report."""
        total_tests = sum(b.total_tests for b in self.results)
        total_passed = sum(b.passed_tests for b in self.results)

        # Category breakdown
        category_stats: dict[str, dict[str, int]] = {}
        for benchmark in self.results:
            for test in benchmark.tests:
                cat = self._get_test_category(test.endpoint_name)
                if cat not in category_stats:
                    category_stats[cat] = {"total": 0, "passed": 0}
                category_stats[cat]["total"] += 1
                if test.success:
                    category_stats[cat]["passed"] += 1

        # Best/worst profiles
        sorted_profiles = sorted(self.results, key=lambda b: b.success_rate, reverse=True)

        report = BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            gakido_version=GAKIDO_VERSION,
            total_profiles_tested=len(self.results),
            total_tests_run=total_tests,
            overall_success_rate=(total_passed / total_tests * 100) if total_tests > 0 else 0.0,
            profiles=self.results,
            summary={
                "category_stats": category_stats,
                "best_profile": sorted_profiles[0].profile_name if sorted_profiles else None,
                "worst_profile": sorted_profiles[-1].profile_name if sorted_profiles else None,
                "profiles_with_100_percent": [b.profile_name for b in self.results if b.success_rate == 100.0],
            },
        )

        return report

    def _get_test_category(self, endpoint_name: str) -> str:
        """Get category for an endpoint."""
        if endpoint_name in TLS_ENDPOINTS:
            return "TLS Fingerprint"
        elif endpoint_name in HEADER_ENDPOINTS:
            return "HTTP Headers"
        elif endpoint_name in BOT_DETECTION_ENDPOINTS:
            return "Bot Detection"
        elif endpoint_name in CLOUDFLARE_ENDPOINTS:
            return "Cloudflare"
        else:
            return "Other"

    def print_summary(self, report: BenchmarkReport) -> None:
        """Print the final summary."""
        self.log("\n" + "="*70)
        self.log("  BENCHMARK SUMMARY")
        self.log("="*70)

        self.log(f"\nProfiles tested: {report.total_profiles_tested}")
        self.log(f"Total tests run: {report.total_tests_run}")
        self.log(f"Overall success rate: {report.overall_success_rate:.1f}%")

        self.log("\n--- Category Breakdown ---")
        for cat, stats in report.summary.get("category_stats", {}).items():
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            self.log(f"  {cat:20s}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")

        self.log("\n--- Profile Rankings ---")
        sorted_profiles = sorted(report.profiles, key=lambda b: b.success_rate, reverse=True)
        for i, b in enumerate(sorted_profiles[:10], 1):
            hints = "✓" if b.has_client_hints else "✗"
            self.log(f"  {i:2d}. {b.profile_name:25s} {b.success_rate:5.1f}% | hints:{hints} | {b.platform}")

        if report.summary.get("profiles_with_100_percent"):
            self.log(f"\n🏆 Perfect scores: {', '.join(report.summary['profiles_with_100_percent'])}")

    def save_report(self, report: BenchmarkReport, filepath: str) -> None:
        """Save report to JSON file."""
        data = asdict(report)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        self.log(f"\nReport saved to: {filepath}")


# =============================================================================
# Async Benchmark Runner
# =============================================================================

class AsyncAntibotBenchmark(AntibotBenchmark):
    """Async version of the antibot benchmark."""

    async def run_single_test_async(
        self,
        client: AsyncClient,
        endpoint_name: str,
        endpoint_config: dict[str, Any],
    ) -> TestResult:
        """Run a single test endpoint asynchronously."""
        url = endpoint_config["url"]
        description = endpoint_config.get("description", "")
        is_text = endpoint_config.get("is_text", False)
        check_fn = endpoint_config.get("check", lambda r: True)
        check_status_fn = endpoint_config.get("check_status", lambda s: s in (200, 201, 202, 204))

        start_time = time.perf_counter()
        try:
            resp = await client.get(url, headers={"Accept-Encoding": "identity"})
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            status_ok = check_status_fn(resp.status_code)

            if is_text:
                content = resp.text
                check_ok = check_fn(content)
                details = {"content_preview": content[:200]}
            else:
                try:
                    data = resp.json()
                    check_ok = check_fn(data)
                    details = {"response": data}
                except Exception:
                    check_ok = False
                    details = {"raw_content": resp.text[:500]}

            success = status_ok and check_ok

            return TestResult(
                endpoint_name=endpoint_name,
                url=url,
                description=description,
                success=success,
                status_code=resp.status_code,
                response_time_ms=elapsed_ms,
                details=details,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return TestResult(
                endpoint_name=endpoint_name,
                url=url,
                description=description,
                success=False,
                response_time_ms=elapsed_ms,
                error=str(e),
            )

    async def benchmark_profile_async(self, profile_name: str) -> ProfileBenchmark:
        """Run all tests for a single profile asynchronously."""
        self.log(f"\n{'='*60}")
        self.log(f"Testing profile: {profile_name}")
        self.log(f"{'='*60}")

        info = self.get_profile_info(profile_name)

        benchmark = ProfileBenchmark(
            profile_name=profile_name,
            platform=info["platform"],
            has_client_hints=info["has_client_hints"],
            has_canvas_webgl=info["has_canvas_webgl"],
            user_agent=info["user_agent"][:80] + "..." if len(info["user_agent"]) > 80 else info["user_agent"],
        )

        try:
            async with AsyncClient(
                impersonate=profile_name,
                timeout=self.timeout,
                force_http1=True,
            ) as client:
                all_endpoints = {
                    **TLS_ENDPOINTS,
                    **HEADER_ENDPOINTS,
                    **BOT_DETECTION_ENDPOINTS,
                    **CLOUDFLARE_ENDPOINTS,
                }

                # Run tests sequentially to avoid rate limiting
                for endpoint_name, endpoint_config in all_endpoints.items():
                    result = await self.run_single_test_async(client, endpoint_name, endpoint_config)
                    benchmark.tests.append(result)

                    status_icon = "✅" if result.success else "❌"
                    time_str = f"{result.response_time_ms:.0f}ms"
                    status_str = f"HTTP {result.status_code}" if result.status_code else "ERROR"

                    self.log(f"  {status_icon} {endpoint_name:25s} {status_str:10s} {time_str:8s}")

                    if result.error:
                        self.log(f"      Error: {result.error[:60]}")

        except Exception as e:
            self.log(f"  ❌ Failed to create client: {e}")

        benchmark.calculate_stats()

        self.log(f"\n  Summary: {benchmark.passed_tests}/{benchmark.total_tests} passed "
                 f"({benchmark.success_rate:.1f}%) | Avg: {benchmark.avg_response_time_ms:.0f}ms")

        return benchmark

    async def run_async(self) -> BenchmarkReport:
        """Run the complete benchmark asynchronously."""
        self.log("\n" + "="*70)
        self.log("  GAKIDO ANTIBOT SYSTEMS BENCHMARK (ASYNC)")
        self.log("="*70)
        self.log(f"Profiles to test: {len(self.profiles)}")
        self.log(f"Timeout: {self.timeout}s")

        for profile_name in self.profiles:
            benchmark = await self.benchmark_profile_async(profile_name)
            self.results.append(benchmark)

        report = self.generate_report()
        self.print_summary(report)

        return report


# =============================================================================
# CLI
# =============================================================================

def get_all_base_profiles() -> list[str]:
    """Get all base profiles (not aliases)."""
    return [name for name in PROFILES if name not in ALIAS_MAP]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark gakido against antibot detection systems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with default profiles
    uv run python examples/antibot_benchmark.py

    # Test specific profile
    uv run python examples/antibot_benchmark.py --profile chrome_144

    # Test all base profiles
    uv run python examples/antibot_benchmark.py --all-profiles

    # Run async version
    uv run python examples/antibot_benchmark.py --async

    # Save results to JSON
    uv run python examples/antibot_benchmark.py --output results.json
        """,
    )
    parser.add_argument(
        "--profile", "-p",
        action="append",
        help="Profile to test (can be specified multiple times)",
    )
    parser.add_argument(
        "--all-profiles",
        action="store_true",
        help="Test all base profiles (24 profiles)",
    )
    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use async client for testing",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=15.0,
        help="Request timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    # Determine profiles to test
    if args.all_profiles:
        profiles = get_all_base_profiles()
    elif args.profile:
        profiles = args.profile
    else:
        profiles = None  # Use defaults

    # Run benchmark
    if args.use_async:
        benchmark = AsyncAntibotBenchmark(
            profiles=profiles,
            timeout=args.timeout,
            verbose=not args.quiet,
        )
        report = asyncio.run(benchmark.run_async())
    else:
        benchmark = AntibotBenchmark(
            profiles=profiles,
            timeout=args.timeout,
            verbose=not args.quiet,
        )
        report = benchmark.run()

    # Save results
    if args.output:
        benchmark.save_report(report, args.output)


if __name__ == "__main__":
    main()
