# Client Hints & Browser Fingerprints

Gakido includes comprehensive support for Sec-CH-UA client hints and Canvas/WebGL fingerprint data for better browser impersonation.

## Sec-CH-UA Client Hints

Client hints are HTTP headers that provide information about the browser and platform. Modern browsers (Chrome, Edge) send these automatically, and anti-bot systems check for their presence and consistency.

### Automatic Client Hints

Chrome and Edge profiles automatically include basic client hints in requests:

```python
from gakido import Client

# Client hints are sent automatically with Chrome/Edge profiles
with Client(impersonate="chrome_120") as c:
    r = c.get("https://httpbin.org/headers")
    print(r.json()["headers"])
    # Includes: Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform
```

### Available Client Hints

| Header | Type | Description |
|--------|------|-------------|
| `Sec-CH-UA` | Low entropy | Browser brand and version |
| `Sec-CH-UA-Mobile` | Low entropy | Mobile device indicator (`?0` or `?1`) |
| `Sec-CH-UA-Platform` | Low entropy | Operating system name |
| `Sec-CH-UA-Platform-Version` | High entropy | OS version |
| `Sec-CH-UA-Full-Version-List` | High entropy | Full browser version |
| `Sec-CH-UA-Arch` | High entropy | CPU architecture |
| `Sec-CH-UA-Bitness` | High entropy | CPU bitness (32/64) |
| `Sec-CH-UA-Model` | High entropy | Device model (mobile) |

### Extracting Client Hints from Profiles

```python
from gakido.impersonation import get_profile, get_client_hints_headers

profile = get_profile("chrome_120")

# Get basic hints (always sent)
basic = get_client_hints_headers(profile, include_high_entropy=False)
# {'Sec-CH-UA': '"Not_A Brand";v="8", ...', 'Sec-CH-UA-Mobile': '?0', ...}

# Get all hints including high-entropy
all_hints = get_client_hints_headers(profile, include_high_entropy=True)
# Includes: Sec-CH-UA-Platform-Version, Sec-CH-UA-Arch, etc.
```

### Building Custom Client Hints

```python
from gakido.impersonation import build_client_hints_for_platform

# Build hints for a custom platform
hints = build_client_hints_for_platform(
    browser="Google Chrome",
    version="120",
    platform="Windows",
    mobile=False,
    platform_version="10.0.0",
    arch="x86",
    bitness="64",
)
```

### Handling Accept-CH Response Headers

Servers can request additional client hints via the `Accept-CH` response header:

```python
from gakido.impersonation import parse_accept_ch, get_profile

# Parse server's Accept-CH header
accept_ch = "Sec-CH-UA-Platform-Version, Sec-CH-UA-Arch"
requested = parse_accept_ch(accept_ch)
# ['Sec-CH-UA-Platform-Version', 'Sec-CH-UA-Arch']

# Get hints to send in next request
profile = get_profile("chrome_120")
hints = profile.get("client_hints", {})
for name in requested:
    if name in hints:
        print(f"{name}: {hints[name]}")
```

## Canvas/WebGL Fingerprints

Canvas and WebGL fingerprints are used by anti-bot systems to identify browsers. Each profile includes realistic fingerprint data.

### Accessing Fingerprint Data

```python
from gakido.impersonation import get_profile, get_canvas_webgl_fingerprint

profile = get_profile("chrome_120")
fp = get_canvas_webgl_fingerprint(profile)

print(fp["webgl_vendor"])   # "Google Inc. (Apple)"
print(fp["webgl_renderer"]) # "ANGLE (Apple, ANGLE Metal Renderer: ...)"
print(fp["canvas_hash"])    # Unique canvas hash
```

### Platform-Specific Fingerprints

Different profiles have appropriate fingerprints for their platform:

| Profile | WebGL Vendor | WebGL Renderer |
|---------|--------------|----------------|
| `chrome_120` (macOS) | Google Inc. (Apple) | ANGLE Metal Renderer: Apple M1 |
| `chrome_120_android` | Qualcomm | Adreno (TM) 730 |
| `edge_101` (Windows) | Google Inc. (NVIDIA) | ANGLE NVIDIA GeForce RTX 3080 |
| `safari_170` | Apple Inc. | Apple GPU |
| `firefox_133` | Google Inc. (Apple) | ANGLE Metal Renderer |
| `tor_145` | Mozilla | Mozilla |

### Predefined WebGL Renderers

```python
from gakido.impersonation import WEBGL_RENDERERS, get_webgl_renderer

# Available presets
print(WEBGL_RENDERERS.keys())
# chrome_macos_m1, chrome_macos_intel, chrome_windows_nvidia,
# chrome_windows_amd, chrome_android_adreno, chrome_android_mali,
# firefox_macos, safari_macos, safari_ios, tor

# Get specific renderer
renderer = get_webgl_renderer("chrome_windows_nvidia")
print(renderer["vendor"])   # "Google Inc. (NVIDIA)"
print(renderer["renderer"]) # "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 ...)"
```

## Profile Client Hints Support

| Profile | Client Hints | Canvas/WebGL |
|---------|--------------|--------------|
| `chrome_120` | ✅ Full | ✅ |
| `chrome_120_android` | ✅ Full | ✅ |
| `edge_101` | ✅ Full | ✅ |
| `safari_170` | ❌ (Safari doesn't send) | ✅ |
| `safari_170_ios` | ❌ | ✅ |
| `firefox_133` | ❌ (Firefox doesn't send) | ✅ |
| `tor_145` | ❌ | ✅ (uniform) |

## API Reference

### Functions

```python
from gakido.impersonation import (
    # Client hints
    generate_sec_ch_ua,              # Generate Sec-CH-UA header value
    generate_sec_ch_ua_full_version_list,  # Generate full version list
    get_client_hints_headers,        # Extract hints from profile
    build_client_hints_for_platform, # Build custom hints
    parse_accept_ch,                 # Parse Accept-CH header
    should_send_hint,                # Check if hint should be sent

    # Canvas/WebGL
    get_canvas_webgl_fingerprint,    # Get fingerprint from profile
    get_webgl_renderer,              # Get predefined renderer
    WEBGL_RENDERERS,                 # Dict of renderer presets
)
```

### generate_sec_ch_ua

```python
def generate_sec_ch_ua(
    browser: str,           # Browser name (e.g., "Google Chrome")
    version: str,           # Major version (e.g., "120")
    chromium_version: str | None = None,  # Chromium version if different
) -> str
```

### get_client_hints_headers

```python
def get_client_hints_headers(
    profile: dict,                    # Browser profile
    include_high_entropy: bool = False,  # Include high-entropy hints
) -> dict[str, str]
```

### get_canvas_webgl_fingerprint

```python
def get_canvas_webgl_fingerprint(
    profile: dict,  # Browser profile
) -> dict[str, str]  # Returns {webgl_vendor, webgl_renderer, canvas_hash}
```

## Example: Full Impersonation

```python
from gakido import Client
from gakido.impersonation import (
    get_profile,
    get_client_hints_headers,
    get_canvas_webgl_fingerprint,
)

# Create client with Chrome impersonation
client = Client(impersonate="chrome_120")
profile = get_profile("chrome_120")

# View what's being sent
print("TLS:", len(profile["tls"]["ciphers"]), "chars cipher string")
print("HTTP/2:", list(profile["http2"]["settings"].keys()))
print("Client Hints:", list(get_client_hints_headers(profile, True).keys()))
print("WebGL:", get_canvas_webgl_fingerprint(profile)["webgl_renderer"])

# Make request with full impersonation
response = client.get("https://example.com")
client.close()
```
