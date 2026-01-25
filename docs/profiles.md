# Browser Profiles

Gakido includes **24 base browser profiles** with **72 aliases** for a total of **96 available profile names**.

## Quick Reference

```python
from gakido import Client

# Use any profile by name
client = Client(impersonate="chrome_144")
client = Client(impersonate="firefox_147")
client = Client(impersonate="safari_184_macos")
client = Client(impersonate="brave_131")
```

## Profile Summary

| Browser | Base Profiles | Aliases | Total |
|---------|---------------|---------|-------|
| Chrome | 6 | 26 | 32 |
| Firefox | 5 | 10 | 15 |
| Safari | 6 | 12 | 18 |
| Edge | 3 | 10 | 13 |
| Opera | 1 | 3 | 4 |
| Brave | 1 | 3 | 4 |
| Vivaldi | 1 | 2 | 3 |
| Tor | 1 | 2 | 3 |
| **Total** | **24** | **72** | **96** |

---

## Chrome Profiles (6 base + 26 aliases)

### Base Profiles

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `chrome_120` | macOS | ✅ | Chrome 120 on macOS (default) |
| `chrome_120_android` | Android | ✅ | Chrome 120 on Android (Pixel 7) |
| `chrome_120_macos_libressl` | macOS | ✅ | Chrome 120 with LibreSSL cipher suite |
| `chrome_131_windows` | Windows | ✅ | Chrome 131 on Windows 10 |
| `chrome_136_linux` | Linux | ✅ | Chrome 136 on Linux x86_64 |
| `chrome_144` | macOS | ✅ | Chrome 144 on macOS (latest 2025) |

### Aliases

```
chrome99, chrome100, chrome101, chrome104, chrome107, chrome110,
chrome116, chrome119, chrome120, chrome123, chrome124 → chrome_120

chrome131, chrome131_windows, chrome132, chrome133, chrome133a → chrome_131_windows

chrome134, chrome135, chrome136, chrome136_linux → chrome_136_linux

chrome144, chrome144_macos → chrome_144

chrome99_android, chrome131_android, chrome132_android, chrome133_android,
chrome134_android, chrome135_android, chrome144_android → chrome_120_android
```

---

## Firefox Profiles (5 base + 10 aliases)

### Base Profiles

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `firefox_120` | macOS | ❌ | Firefox 120 on macOS |
| `firefox_133` | macOS | ❌ | Firefox 133 on macOS |
| `firefox_135_android` | Android | ❌ | Firefox 135 on Android |
| `firefox_147` | Linux | ❌ | Firefox 147 on Linux (latest 2025) |
| `firefox_147_macos` | macOS | ❌ | Firefox 147 on macOS |

### Aliases

```
firefox133, firefox135 → firefox_133

firefox140, firefox145, firefox147, firefox147_linux → firefox_147

firefox147_macos → firefox_147_macos

firefox135_android, firefox147_android → firefox_135_android
```

---

## Safari Profiles (6 base + 12 aliases)

### Base Profiles

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `safari_170` | macOS | ❌ | Safari 17.0 on macOS |
| `safari_170_ios` | iOS | ❌ | Safari 17.0 on iOS |
| `safari_184_macos` | macOS Sonoma | ❌ | Safari 18.4 on macOS 14.7 |
| `safari_184_ipad` | iPadOS | ❌ | Safari 18.4 on iPad |
| `safari_187_ios` | iOS 18 | ❌ | Safari 18.7 on iOS 18.7 |
| `safari_26_ios` | iOS 18 | ❌ | Safari 26.0 on iOS (2025 versioning) |

### Aliases

```
safari153, safari155, safari170 → safari_170

safari180, safari184, safari184_macos, safari260 → safari_184_macos

safari172_ios → safari_170_ios

safari180_ios, safari184_ios, safari187_ios → safari_187_ios

safari260_ios, safari26_ios → safari_26_ios

safari184_ipad, safari186_ipad → safari_184_ipad
```

---

## Edge Profiles (3 base + 10 aliases)

### Base Profiles

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `edge_101` | Windows | ✅ | Edge 101 on Windows 10 |
| `edge_131` | Windows | ✅ | Edge 131 on Windows 10 |
| `edge_144` | Windows | ✅ | Edge 144 on Windows (latest 2025) |

### Aliases

```
edge99, edge101 → edge_101

edge131, edge131_windows, edge133, edge135 → edge_131

edge140, edge144, edge144_windows → edge_144
```

---

## Other Browsers (4 base + 10 aliases)

### Opera (1 base + 3 aliases)

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `opera_115` | Windows | ✅ | Opera 115 on Windows (Chromium 129) |

```
opera115, opera115_windows, opera120 → opera_115
```

### Brave (1 base + 3 aliases)

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `brave_131` | Windows | ✅ | Brave 131 on Windows (privacy-focused) |

```
brave131, brave131_windows, brave135 → brave_131
```

### Vivaldi (1 base + 2 aliases)

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `vivaldi_7` | Windows | ✅ | Vivaldi 7 on Windows (Chromium 130) |

```
vivaldi7, vivaldi7_windows → vivaldi_7
```

### Tor Browser (1 base + 2 aliases)

| Profile | Platform | Client Hints | Description |
|---------|----------|--------------|-------------|
| `tor_145` | Windows | ❌ | Tor Browser 14.5 (Firefox-based, uniform fingerprint) |

```
tor145, tor150 → tor_145
```

---

## Profile Features

Each profile includes:

| Feature | Chrome/Edge/Opera/Brave/Vivaldi | Firefox | Safari | Tor |
|---------|--------------------------------|---------|--------|-----|
| TLS Configuration | ✅ | ✅ | ✅ | ✅ |
| HTTP/2 Settings | ✅ | ✅ | ✅ | ✅ |
| HTTP/3 Settings | ✅ | ✅ | ✅ | ❌ |
| Header Order | ✅ | ✅ | ✅ | ✅ |
| Default Headers | ✅ | ✅ | ✅ | ✅ |
| Sec-CH-UA Client Hints | ✅ | ❌ | ❌ | ❌ |
| Canvas/WebGL Fingerprint | ✅ | ✅ | ✅ | ✅ (uniform) |

---

## Accessing Profile Data

```python
from gakido.impersonation import get_profile, PROFILES

# Get a specific profile
profile = get_profile("chrome_144")

# Access profile components
print(profile["tls"]["ciphers"])      # TLS cipher suite
print(profile["http2"]["settings"])   # HTTP/2 settings
print(profile["headers"]["order"])    # Header order
print(profile["headers"]["default"])  # Default headers
print(profile.get("client_hints"))    # Sec-CH-UA headers (if available)
print(profile.get("canvas_webgl"))    # WebGL fingerprint data

# List all available profiles
print(f"Total profiles: {len(PROFILES)}")
print(list(PROFILES.keys()))
```

---

## Recommended Profiles by Use Case

| Use Case | Recommended Profile |
|----------|---------------------|
| General scraping | `chrome_120` or `chrome_144` |
| Windows target | `chrome_131_windows` or `edge_131` |
| Linux server | `chrome_136_linux` or `firefox_147` |
| macOS | `chrome_144` or `safari_184_macos` |
| Mobile iOS | `safari_187_ios` or `safari_26_ios` |
| Mobile Android | `chrome_120_android` |
| iPad | `safari_184_ipad` |
| Privacy-focused | `brave_131` or `tor_145` |
| Anti-detection | Rotate between multiple profiles |

---

## User Agent Strings

### Chrome 144 (macOS)
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36
```

### Chrome 131 (Windows)
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
```

### Firefox 147 (Linux)
```
Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0
```

### Safari 18.4 (macOS)
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4.1 Safari/605.1.15
```

### Safari 18.7 (iOS)
```
Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.7 Mobile/15E148 Safari/604.1
```

### Edge 144 (Windows)
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0
```

### Brave 131 (Windows)
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
```

### Tor Browser 14.5
```
Mozilla/5.0 (Windows NT 10.0; rv:115.0) Gecko/20100101 Firefox/115.0
```
