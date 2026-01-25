# Antibot Systems Benchmark

Gakido includes a comprehensive benchmark tool to test browser impersonation against various antibot detection systems.

## Quick Start

```bash
# Run with default profiles (13 profiles)
uv run python examples/antibot_benchmark.py

# Test specific profile
uv run python examples/antibot_benchmark.py --profile chrome_144

# Test all 24 base profiles
uv run python examples/antibot_benchmark.py --all-profiles
```

## Test Categories

The benchmark tests **9 endpoints** across **4 categories**:

### 1. TLS Fingerprint Tests

| Endpoint | URL | Description |
|----------|-----|-------------|
| `tls_browserleaks` | tls.browserleaks.com | JA3/JA4 fingerprint analysis |
| `scrapfly_ja3` | tools.scrapfly.io | Scrapfly JA3 fingerprint |

### 2. HTTP Header Analysis

| Endpoint | URL | Description |
|----------|-----|-------------|
| `httpbin_headers` | httpbin.org/headers | HTTP header echo service |
| `httpbin_user_agent` | httpbin.org/user-agent | User-Agent verification |

### 3. Bot Detection Services

| Endpoint | URL | Description |
|----------|-----|-------------|
| `nowsecure` | nowsecure.nl | NowSecure bot detection test |
| `sannysoft` | bot.sannysoft.com | Sannysoft bot detection |
| `incolumitas` | bot.incolumitas.com | Incolumitas bot detection |

### 4. Cloudflare Endpoints

| Endpoint | URL | Description |
|----------|-----|-------------|
| `cloudflare_trace` | cloudflare.com/cdn-cgi/trace | Cloudflare trace endpoint |
| `cloudflare_1111` | 1.1.1.1/cdn-cgi/trace | Cloudflare 1.1.1.1 trace |

## Usage

### Basic Usage

```bash
# Default profiles
uv run python examples/antibot_benchmark.py

# Single profile
uv run python examples/antibot_benchmark.py --profile chrome_144

# Multiple profiles
uv run python examples/antibot_benchmark.py -p chrome_144 -p firefox_147 -p brave_131

# All base profiles (24 profiles)
uv run python examples/antibot_benchmark.py --all-profiles
```

### Options

| Option | Description |
|--------|-------------|
| `--profile`, `-p` | Profile to test (can be specified multiple times) |
| `--all-profiles` | Test all 24 base profiles |
| `--async` | Use async client for testing |
| `--timeout`, `-t` | Request timeout in seconds (default: 15) |
| `--output`, `-o` | Save results to JSON file |
| `--quiet`, `-q` | Suppress verbose output |

### Examples

```bash
# Async mode (faster for multiple profiles)
uv run python examples/antibot_benchmark.py --async

# Custom timeout
uv run python examples/antibot_benchmark.py --timeout 30

# Save results to JSON
uv run python examples/antibot_benchmark.py --output results.json

# Quiet mode with JSON output
uv run python examples/antibot_benchmark.py -q -o results.json
```

## Default Profiles Tested

The benchmark tests these 13 profiles by default:

| Profile | Platform | Client Hints |
|---------|----------|--------------|
| `chrome_120` | macOS | ✅ |
| `chrome_144` | macOS | ✅ |
| `chrome_131_windows` | Windows | ✅ |
| `chrome_136_linux` | Linux | ✅ |
| `firefox_133` | macOS | ❌ |
| `firefox_147` | Linux | ❌ |
| `safari_184_macos` | macOS | ❌ |
| `safari_187_ios` | iOS | ❌ |
| `edge_131` | Windows | ✅ |
| `edge_144` | Windows | ✅ |
| `brave_131` | Windows | ✅ |
| `opera_115` | Windows | ✅ |
| `tor_145` | Windows | ❌ |

## Sample Output

```
======================================================================
  GAKIDO ANTIBOT SYSTEMS BENCHMARK
======================================================================
Profiles to test: 4
Timeout: 10.0s

============================================================
Testing profile: chrome_144
============================================================
  ✅ tls_browserleaks          HTTP 200   711ms
  ✅ scrapfly_ja3              HTTP 200   950ms
  ✅ httpbin_headers           HTTP 200   873ms
  ✅ httpbin_user_agent        HTTP 200   260ms
  ✅ nowsecure                 HTTP 200   2389ms
  ✅ sannysoft                 HTTP 200   608ms
  ✅ incolumitas               HTTP 200   1087ms
  ✅ cloudflare_trace          HTTP 200   469ms
  ✅ cloudflare_1111           HTTP 200   419ms

  Summary: 9/9 passed (100.0%) | Avg: 895ms

======================================================================
  BENCHMARK SUMMARY
======================================================================

Profiles tested: 4
Total tests run: 36
Overall success rate: 100.0%

--- Category Breakdown ---
  TLS Fingerprint     : 8/8 (100.0%)
  HTTP Headers        : 8/8 (100.0%)
  Bot Detection       : 12/12 (100.0%)
  Cloudflare          : 8/8 (100.0%)

--- Profile Rankings ---
   1. chrome_144                100.0% | hints:✓ | macOS
   2. firefox_147               100.0% | hints:✗ | Linux
   3. safari_184_macos          100.0% | hints:✗ | macOS
   4. brave_131                 100.0% | hints:✓ | Windows

🏆 Perfect scores: chrome_144, firefox_147, safari_184_macos, brave_131
```

## JSON Output Format

When using `--output`, results are saved in this format:

```json
{
  "timestamp": "2025-01-25T16:15:00.000000",
  "gakido_version": "0.1.0",
  "total_profiles_tested": 4,
  "total_tests_run": 36,
  "overall_success_rate": 100.0,
  "profiles": [
    {
      "profile_name": "chrome_144",
      "platform": "macOS",
      "has_client_hints": true,
      "has_canvas_webgl": true,
      "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
      "tests": [
        {
          "endpoint_name": "tls_browserleaks",
          "url": "https://tls.browserleaks.com/json",
          "description": "TLS/JA3 fingerprint analysis",
          "success": true,
          "status_code": 200,
          "response_time_ms": 711.5,
          "error": null,
          "details": {"response": {"ja3_hash": "..."}}
        }
      ],
      "total_tests": 9,
      "passed_tests": 9,
      "failed_tests": 0,
      "success_rate": 100.0,
      "avg_response_time_ms": 895.2
    }
  ],
  "summary": {
    "category_stats": {
      "TLS Fingerprint": {"total": 8, "passed": 8},
      "HTTP Headers": {"total": 8, "passed": 8},
      "Bot Detection": {"total": 12, "passed": 12},
      "Cloudflare": {"total": 8, "passed": 8}
    },
    "best_profile": "chrome_144",
    "worst_profile": "tor_145",
    "profiles_with_100_percent": ["chrome_144", "firefox_147"]
  }
}
```

## Programmatic Usage

```python
from examples.antibot_benchmark import AntibotBenchmark, AsyncAntibotBenchmark
import asyncio

# Sync benchmark
benchmark = AntibotBenchmark(
    profiles=["chrome_144", "firefox_147"],
    timeout=15.0,
    verbose=True,
)
report = benchmark.run()

# Access results
print(f"Success rate: {report.overall_success_rate}%")
for profile in report.profiles:
    print(f"{profile.profile_name}: {profile.success_rate}%")

# Save to JSON
benchmark.save_report(report, "results.json")

# Async benchmark
async def run_async():
    benchmark = AsyncAntibotBenchmark(
        profiles=["chrome_144", "firefox_147"],
        timeout=15.0,
    )
    return await benchmark.run_async()

report = asyncio.run(run_async())
```

## Adding Custom Endpoints

You can extend the benchmark by adding custom endpoints:

```python
from examples.antibot_benchmark import AntibotBenchmark, BOT_DETECTION_ENDPOINTS

# Add custom endpoint
BOT_DETECTION_ENDPOINTS["my_endpoint"] = {
    "url": "https://example.com/bot-check",
    "description": "My custom bot check",
    "check": lambda r: r.get("is_bot") == False,  # Custom validation
    "check_status": lambda s: s == 200,
}

# Run benchmark with custom endpoint included
benchmark = AntibotBenchmark(profiles=["chrome_144"])
report = benchmark.run()
```

## Interpreting Results

### Success Criteria

- **TLS Fingerprint**: Returns valid JA3/JA4 hash
- **HTTP Headers**: Returns expected header structure
- **Bot Detection**: HTTP 200 response (page loads without block)
- **Cloudflare**: Contains `fl=` in trace response

### What Affects Results

| Factor | Impact |
|--------|--------|
| TLS Configuration | JA3/JA4 fingerprint matching |
| HTTP/2 Settings | SETTINGS frame fingerprint |
| Header Order | Header ordering detection |
| Client Hints | Sec-CH-UA consistency |
| User-Agent | Browser identification |

### Recommendations

- Use **Chrome profiles** for best compatibility
- Enable **client hints** for Chromium-based detection
- Use **platform-specific profiles** (e.g., `chrome_131_windows` for Windows targets)
- Rotate profiles to avoid fingerprint-based blocking
