# Cookie Persistence

Gakido's `Session` and `AsyncSession` classes provide automatic cookie handling with optional file persistence. This allows sessions to maintain state across program restarts.

## Quick Start

Enable cookie persistence with a single parameter:

```python
from gakido import Session

# Create session with persistent cookies
with Session(cookie_file="~/.gakido/cookies.json") as session:
    # Login
    session.post("https://api.example.com/login", json={
        "username": "john",
        "password": "secret"
    })

    # Subsequent requests automatically include cookies
    response = session.get("https://api.example.com/profile")
    print(response.json())

# Program exits...
# When you run again, cookies are automatically loaded

with Session(cookie_file="~/.gakido/cookies.json") as session:
    # Still authenticated! Cookies were loaded from file
    response = session.get("https://api.example.com/profile")
    print(response.json())
```

## How It Works

### Automatic Cookie Management

The `Session` class automatically:
1. **Loads cookies** from the file on creation (if file exists)
2. **Sends cookies** with each request to matching hosts
3. **Receives cookies** from `Set-Cookie` headers in responses
4. **Filters expired cookies** before sending

### Manual Save/Load

For more control, use manual methods:

```python
from gakido import Session

# Create session without persistence
session = Session()

# Login and get cookies
session.post("https://api.example.com/login", json={"user": "john"})

# Manually save cookies
session.save_cookies("cookies.json")

# ... later ...

# Load cookies in a new session
new_session = Session()
new_session.load_cookies("cookies.json")
```

## Configuration

### Cookie File Path

| Option | Default | Description |
|--------|---------|-------------|
| `cookie_file` | `None` | Path to JSON file for persistence |

```python
# Default location
Session(cookie_file="~/.gakido/cookies.json")

# Custom location
Session(cookie_file="/path/to/my/cookies.json")
```

### File Format

Cookies are stored in JSON format:

```json
{
  "api.example.com": {
    "session": {
      "value": "abc123",
      "expires": 1234567890,
      "path": "/",
      "secure": false,
      "httponly": true,
      "samesite": "Lax"
    }
  }
}
```

## Cookie Attributes

Gakido preserves standard cookie attributes:

| Attribute | Description |
|-----------|-------------|
| `value` | Cookie value |
| `expires` | Expiration timestamp (Unix epoch) |
| `path` | URL path scope (default: `/`) |
| `secure` | HTTPS-only flag |
| `httponly` | JavaScript inaccessible flag |
| `samesite` | Cross-site request policy |

## Domain and Path Matching

### Host-Only Cookies

Cookies without a `Domain` attribute are "host-only" and apply only to the exact host:

```python
# Set on www.example.com
session.get("https://www.example.com/")
# Cookie: session=abc123

# Won't be sent to other hosts
session.get("https://api.example.com/")  # No cookie
session.get("https://other.com/")         # No cookie
```

### Domain Cookies

Cookies with a `Domain` attribute apply to the domain and all subdomains:

```python
# Set on www.example.com with Domain=.example.com
# Cookie applies to:
# - www.example.com
# - api.example.com
# - blog.example.com
# - Any *.example.com
```

### Path Matching

The `Path` attribute controls which URLs receive the cookie:

```python
# Cookie with Path=/api
# Sent to: /api/users, /api/items
# Not sent to: /, /about, /blog
```

## Cookie Expiration

### Automatic Expiration

Expired cookies are automatically filtered:

```python
# Max-Age based expiration
response.set_cookie("session", "abc123", max_age=3600)  # 1 hour

# Expires header based expiration
response.set_cookie("session", "abc123", expires="Wed, 21 Oct 2025 07:28:00 GMT")

# Session cookies (no expiration)
response.set_cookie("temp", "value")  # Deleted when browser closes
```

### Manual Cleanup

Clear all cookies:

```python
# Clear from memory and delete file
session.clear_cookies()

# Or just clear memory
session.cookies.store.clear()
```

## Security

### File Permissions

Cookie files use restrictive permissions:

- **File**: `0o600` (user read/write only)
- **Directory**: `0o700` (user read/write/execute only)

```python
# ~/.gakido/cookies.json permissions: -rw-------
# ~/.gakido/ directory permissions: drwx------
```

### Secure and HttpOnly

These attributes are preserved but **not enforced** by Gakido:

```python
# Secure cookie
Set-Cookie: token=secret; Secure

# HttpOnly cookie
Set-Cookie: session=abc123; HttpOnly
```

> **Note**: Gakido is not a browser. It stores all cookie attributes but doesn't enforce security policies like a browser would.

## Async Sessions

The `AsyncSession` class supports the same cookie persistence:

```python
import asyncio
from gakido import AsyncSession

async def main():
    async with AsyncSession(cookie_file="~/.gakido/cookies.json") as session:
        await session.post("https://api.example.com/login", json={
            "username": "john",
            "password": "secret"
        })

        response = await session.get("https://api.example.com/profile")
        print(response.json())

asyncio.run(main())
```

## Advanced Usage

### Access CookieJar Directly

For low-level cookie manipulation:

```python
from gakido import Session

session = Session()

# Access the underlying CookieJar
print(session.cookies.store)

# Get cookies for specific host
cookies = session.cookies.get_cookies_for_host("example.com")
print(cookies)

# Manual cookie manipulation
session.cookies.store["example.com"] = {
    "custom": {"value": "123", "path": "/", "expires": None}
}
```

### Custom Cookie Storage

You can implement your own cookie storage backend by manipulating `CookieJar`:

```python
import redis
from gakido import Session
from gakido.cookies import CookieJar

class RedisCookieJar(CookieJar):
    """Cookie jar that stores cookies in Redis."""

    def __init__(self, redis_client, key="gakido:cookies"):
        super().__init__(None)
        self._redis = redis_client
        self._key = key
        self._load_from_redis()

    def _load_from_redis(self):
        data = self._redis.get(self._key)
        if data:
            import json
            self.store = json.loads(data)

    def save_cookies(self, cookie_file=None):
        import json
        self._redis.set(self._key, json.dumps(self.store))

# Usage
redis_client = redis.Redis()
session = Session()
session.cookies = RedisCookieJar(redis_client)
```

## Troubleshooting

### Cookies Not Persisting

Checklist:

1. **Verify file path is set**:
   ```python
   Session(cookie_file="path/to/cookies.json")  # ✓ Persistence enabled
   Session()                                     # ✗ No persistence
   ```

2. **Check file permissions**:
   ```bash
   ls -la ~/.gakido/cookies.json
   # Should show: -rw------- (owner only)
   ```

3. **Verify cookies are being set**:
   ```python
   response = session.get("https://example.com/")
   print(session.cookies.store)  # Check if cookies were captured
   ```

### Cookies Not Being Sent

1. **Check domain matching**:
   ```python
   # Cookie set for 'example.com'
   # Won't be sent to 'www.example.com' unless Domain=.example.com
   ```

2. **Check expiration**:
   ```python
   cookies = session.cookies.get_cookies_for_host("example.com")
   for name, data in cookies.items():
       if data.get("expires") and data["expires"] < time.time():
           print(f"Cookie '{name}' is expired")
   ```

3. **Verify path matching**:
   ```python
   # Cookie with Path=/api
   # Won't be sent to / (root path)
   ```

### Clearing Cookies

```python
# Remove specific cookie
del session.cookies.store["example.com"]["session"]

# Remove all cookies for host
session.cookies.store.pop("example.com", None)

# Clear everything and delete file
session.clear_cookies()
```

## API Reference

### Session

```python
Session(
    auto_referer: bool = True,
    cookie_file: str | Path | None = None,
    **client_kwargs
)
```

Methods:
- `save_cookies(cookie_file=None)` - Save cookies to file
- `load_cookies(cookie_file=None)` - Load cookies from file
- `clear_cookies()` - Clear all cookies and delete file

### CookieJar

```python
CookieJar(cookie_file: str | Path | None = None)
```

Methods:
- `set_from_headers(headers, host)` - Parse and store cookies from headers
- `cookie_header(host)` - Get Cookie header string for host
- `save_cookies(cookie_file=None)` - Save to JSON file
- `load_cookies(cookie_file=None)` - Load from JSON file
- `clear_cookies()` - Clear all cookies and delete file
- `get_cookies_for_host(host)` - Get all cookies for a host

## Examples

### Login and Maintain Session

```python
from gakido import Session

def login_and_fetch():
    with Session(cookie_file="~/.gakido/session.json") as session:
        # Login
        response = session.post(
            "https://api.example.com/auth/login",
            json={"username": "john", "password": "secret"}
        )

        if response.status_code != 200:
            raise Exception("Login failed")

        # Fetch protected resource
        response = session.get("https://api.example.com/user/profile")
        return response.json()

# First run: logs in and saves cookies
profile = login_and_fetch()

# Second run: uses saved cookies, no need to login again
profile = login_and_fetch()
```

### Multi-Step Workflow

```python
from gakido import Session

with Session(cookie_file="~/.gakido/workflow.json") as session:
    # Step 1: Get CSRF token
    response = session.get("https://example.com/form")
    csrf = extract_csrf(response.text)

    # Step 2: Submit form (includes CSRF cookie)
    response = session.post(
        "https://example.com/submit",
        data={"csrf": csrf, "field": "value"}
    )

    # Step 3: Check status (session cookie persists)
    response = session.get("https://example.com/status")
```

### Separate Cookie Files per Account

```python
from gakido import Session

# Account A
with Session(cookie_file="~/.gakido/account_a.json") as session_a:
    session_a.post("https://api.example.com/login", json={"user": "alice"})

# Account B
with Session(cookie_file="~/.gakido/account_b.json") as session_b:
    session_b.post("https://api.example.com/login", json={"user": "bob"})

# Each session maintains separate cookies
```
