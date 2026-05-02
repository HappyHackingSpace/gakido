"""
Cookie Persistence Example
==========================

This example demonstrates how to use Gakido's persistent cookie storage
to maintain session state across program restarts.

Features shown:
- Persistent cookies with Session
- Manual save/load of cookies
- Cookie expiration handling
- Clearing cookies
"""

import time
from pathlib import Path
from tempfile import gettempdir

from gakido import Session


def persistent_session_example():
    """Demonstrate persistent session across program restarts."""
    print("=" * 60)
    print("Example 1: Persistent Session")
    print("=" * 60)

    cookie_file = Path(gettempdir()) / "gakido_cookies_example.json"

    # Simulate "Program Run 1" - Login and save cookies
    print("\n--- Program Run 1 ---")
    with Session(cookie_file=cookie_file) as session:
        # Login (simulated with httpbin)
        print("Logging in...")
        response = session.get("https://httpbin.org/cookies/set/session/abc123")
        print(f"Login response: {response.status_code}")

        # Cookies are automatically available for subsequent requests
        print("Making authenticated request...")
        response = session.get("https://httpbin.org/cookies")
        print(f"Cookies received: {response.json()}")

    print(f"\nCookies saved to: {cookie_file}")

    # Simulate "Program Run 2" - Load saved cookies
    print("\n--- Program Run 2 ---")
    with Session(cookie_file=cookie_file) as session:
        # Cookies are automatically loaded from file
        print("Cookies loaded from file")
        print("Making request with loaded cookies...")
        response = session.get("https://httpbin.org/cookies")
        print(f"Cookies received: {response.json()}")

    # Cleanup
    cookie_file.unlink(missing_ok=True)
    print("\n✓ Cookies persisted across program restarts!")


def manual_save_load_example():
    """Demonstrate manual cookie save and load."""
    print("\n" + "=" * 60)
    print("Example 2: Manual Save and Load")
    print("=" * 60)

    cookie_file = Path(gettempdir()) / "gakido_manual_cookies.json"

    # Create session without cookie file
    print("\n1. Creating session without persistence...")
    session = Session()

    # Set some cookies
    print("2. Setting cookies...")
    session.get("https://httpbin.org/cookies/set/user/john_doe")
    session.get("https://httpbin.org/cookies/set/preferences/dark_mode")

    # Check current cookies
    response = session.get("https://httpbin.org/cookies")
    print(f"   Current cookies: {response.json()}")

    # Manually save cookies
    print(f"\n3. Manually saving cookies to: {cookie_file}")
    session.save_cookies(cookie_file)

    # Close session
    session.close()

    # Create new session and load cookies
    print("\n4. Creating new session...")
    new_session = Session()

    print("5. Loading cookies from file...")
    new_session.load_cookies(cookie_file)

    response = new_session.get("https://httpbin.org/cookies")
    print(f"   Loaded cookies: {response.json()}")

    new_session.close()

    # Cleanup
    cookie_file.unlink(missing_ok=True)
    print("\n✓ Manual save/load works!")


def cookie_expiration_example():
    """Demonstrate cookie expiration handling."""
    print("\n" + "=" * 60)
    print("Example 3: Cookie Expiration")
    print("=" * 60)

    from gakido.cookies import CookieJar

    jar = CookieJar()

    # Add cookies with different expiration times
    print("\n1. Adding cookies...")

    # Permanent cookie
    jar.set_from_headers(
        [("Set-Cookie", "permanent=value1; Path=/")],
        "example.com"
    )
    print("   - Permanent cookie (no expiration)")

    # Short-lived cookie (2 seconds)
    jar.set_from_headers(
        [("Set-Cookie", "short_lived=value2; Max-Age=2; Path=/")],
        "example.com"
    )
    print("   - Short-lived cookie (2 seconds)")

    # Check cookies immediately
    print("\n2. Checking cookies immediately:")
    header = jar.cookie_header("example.com")
    print(f"   Cookies: {header}")

    # Wait for expiration
    print("\n3. Waiting 3 seconds for short cookie to expire...")
    time.sleep(3)

    # Check cookies after expiration
    print("4. Checking cookies after expiration:")
    header = jar.cookie_header("example.com")
    print(f"   Cookies: {header}")
    print("   (Only permanent cookie remains)")

    print("\n✓ Expired cookies automatically removed!")


def domain_cookie_example():
    """Demonstrate domain cookie handling."""
    print("\n" + "=" * 60)
    print("Example 4: Domain Cookies (Subdomain Support)")
    print("=" * 60)

    from gakido.cookies import CookieJar

    jar = CookieJar()

    # Set domain cookie (applies to all subdomains)
    print("\n1. Setting domain cookie for '.example.com'...")
    jar.set_from_headers(
        [("Set-Cookie", "session=shared; Domain=.example.com; Path=/")],
        "www.example.com"
    )

    # Set host-only cookie
    print("2. Setting host-only cookie for 'www.example.com'...")
    jar.set_from_headers(
        [("Set-Cookie", "token=secret123; Path=/")],
        "www.example.com"
    )

    # Check which cookies apply to which hosts
    print("\n3. Checking cookies for different hosts:")

    hosts = [
        "www.example.com",
        "api.example.com",
        "blog.example.com",
    ]

    for host in hosts:
        header = jar.cookie_header(host)
        print(f"   {host}: {header}")

    print("\n✓ Domain cookies work across subdomains!")
    print("   Host-only cookies stay on specific host")


def secure_cookie_example():
    """Demonstrate secure and httponly cookie attributes."""
    print("\n" + "=" * 60)
    print("Example 5: Cookie Attributes (Secure, HttpOnly, SameSite)")
    print("=" * 60)

    from gakido.cookies import CookieJar

    jar = CookieJar()

    # Set cookies with various attributes
    print("\n1. Setting cookies with attributes...")

    jar.set_from_headers(
        [("Set-Cookie", "session=abc123; Secure; HttpOnly; SameSite=Strict; Path=/")],
        "example.com"
    )
    print("   Set cookie with Secure, HttpOnly, SameSite=Strict")

    # Check stored attributes
    print("\n2. Stored cookie attributes:")
    cookie_data = jar.store["example.com"]["session"]
    print(f"   Value: {cookie_data['value']}")
    print(f"   Secure: {cookie_data['secure']}")
    print(f"   HttpOnly: {cookie_data['httponly']}")
    print(f"   SameSite: {cookie_data['samesite']}")
    print(f"   Path: {cookie_data['path']}")

    print("\n✓ Cookie attributes are preserved!")


def clear_cookies_example():
    """Demonstrate clearing cookies."""
    print("\n" + "=" * 60)
    print("Example 6: Clearing Cookies")
    print("=" * 60)

    from gakido.cookies import CookieJar
    from tempfile import gettempdir

    cookie_file = Path(gettempdir()) / "clear_cookies_example.json"

    # Create jar with file
    jar = CookieJar(cookie_file=cookie_file)

    # Add some cookies
    print("\n1. Adding cookies...")
    jar.set_from_headers(
        [("Set-Cookie", "a=1; Path=/"), ("Set-Cookie", "b=2; Path=/")],
        "example.com"
    )
    print(f"   Cookie count: {len(jar.store['example.com'])}")

    # Save to file
    jar.save_cookies()
    print(f"   Saved to: {cookie_file}")
    print(f"   File exists: {cookie_file.exists()}")

    # Clear cookies
    print("\n2. Clearing cookies...")
    jar.clear_cookies()

    print(f"   Cookie count after clear: {len(jar.store)}")
    print(f"   File exists after clear: {cookie_file.exists()}")

    print("\n✓ Cookies and file cleared!")


if __name__ == "__main__":
    # Run all examples
    persistent_session_example()
    manual_save_load_example()
    cookie_expiration_example()
    domain_cookie_example()
    secure_cookie_example()
    clear_cookies_example()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print("\nKey takeaways:")
    print("- Use Session(cookie_file='path') for automatic persistence")
    print("- Use save_cookies() / load_cookies() for manual control")
    print("- Expired cookies are automatically cleaned up")
    print("- Domain cookies work across subdomains")
    print("- Cookie attributes (Secure, HttpOnly, SameSite) are preserved")
    print("- Clear cookies with clear_cookies()")
