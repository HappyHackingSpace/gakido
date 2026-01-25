"""
Example: Using Sec-CH-UA Client Hints and Canvas/WebGL Fingerprints

This example demonstrates how to use the client hints and canvas/webgl
fingerprint features for better browser impersonation.
"""

from gakido import Client
from gakido.impersonation import (
    get_profile,
    get_client_hints_headers,
    get_canvas_webgl_fingerprint,
    build_client_hints_for_platform,
    generate_sec_ch_ua,
    parse_accept_ch,
    WEBGL_RENDERERS,
)


def example_basic_client_hints():
    """Basic usage: Client hints are automatically included in Chrome/Edge profiles."""
    print("=" * 60)
    print("Example 1: Basic Client Hints (automatic)")
    print("=" * 60)

    # Chrome profiles automatically include Sec-CH-UA headers
    client = Client(impersonate="chrome_120")

    # The profile includes client hints in default headers
    profile = get_profile("chrome_120")
    print("\nDefault headers include Sec-CH-UA:")
    for name, value in profile["headers"]["default"]:
        if name.startswith("Sec-CH"):
            print(f"  {name}: {value}")

    # Make a request - client hints are sent automatically
    # response = client.get("https://httpbin.org/headers")
    # print(response.json())

    client.close()


def example_extract_client_hints():
    """Extract client hints from a profile for custom use."""
    print("\n" + "=" * 60)
    print("Example 2: Extract Client Hints from Profile")
    print("=" * 60)

    profile = get_profile("chrome_120")

    # Get basic client hints (always sent)
    basic_hints = get_client_hints_headers(profile, include_high_entropy=False)
    print("\nBasic client hints (low entropy, always sent):")
    for name, value in basic_hints.items():
        print(f"  {name}: {value}")

    # Get all client hints including high-entropy ones
    all_hints = get_client_hints_headers(profile, include_high_entropy=True)
    print("\nAll client hints (including high entropy):")
    for name, value in all_hints.items():
        print(f"  {name}: {value}")


def example_canvas_webgl_fingerprint():
    """Access canvas/WebGL fingerprint data from profiles."""
    print("\n" + "=" * 60)
    print("Example 3: Canvas/WebGL Fingerprint Data")
    print("=" * 60)

    profiles_to_check = [
        "chrome_120",
        "chrome_120_android",
        "safari_170",
        "firefox_133",
        "edge_101",
    ]

    for profile_name in profiles_to_check:
        profile = get_profile(profile_name)
        fingerprint = get_canvas_webgl_fingerprint(profile)
        print(f"\n{profile_name}:")
        print(f"  WebGL Vendor: {fingerprint.get('webgl_vendor', 'N/A')}")
        print(f"  WebGL Renderer: {fingerprint.get('webgl_renderer', 'N/A')}")


def example_build_custom_client_hints():
    """Build custom client hints for a specific platform."""
    print("\n" + "=" * 60)
    print("Example 4: Build Custom Client Hints")
    print("=" * 60)

    # Build client hints for a custom Chrome on Windows setup
    hints = build_client_hints_for_platform(
        browser="Google Chrome",
        version="120",
        platform="Windows",
        mobile=False,
        platform_version="10.0.0",
        arch="x86",
        bitness="64",
    )

    print("\nCustom Windows Chrome client hints:")
    for name, value in hints.items():
        print(f"  {name}: {value}")

    # Build client hints for Android mobile
    mobile_hints = build_client_hints_for_platform(
        browser="Google Chrome",
        version="120",
        platform="Android",
        mobile=True,
        platform_version="14.0.0",
        model="Pixel 8 Pro",
    )

    print("\nCustom Android Chrome client hints:")
    for name, value in mobile_hints.items():
        print(f"  {name}: {value}")


def example_generate_sec_ch_ua():
    """Generate Sec-CH-UA header values programmatically."""
    print("\n" + "=" * 60)
    print("Example 5: Generate Sec-CH-UA Headers")
    print("=" * 60)

    # Generate for different browsers
    chrome_ua = generate_sec_ch_ua("Google Chrome", "120")
    edge_ua = generate_sec_ch_ua("Microsoft Edge", "120", chromium_version="120")
    brave_ua = generate_sec_ch_ua("Brave", "120", chromium_version="120")

    print(f"\nChrome: {chrome_ua}")
    print(f"Edge: {edge_ua}")
    print(f"Brave: {brave_ua}")


def example_handle_accept_ch():
    """Handle Accept-CH response header to send appropriate hints."""
    print("\n" + "=" * 60)
    print("Example 6: Handle Accept-CH Response Header")
    print("=" * 60)

    # Simulate receiving Accept-CH header from server
    accept_ch = "Sec-CH-UA-Platform-Version, Sec-CH-UA-Full-Version-List, Sec-CH-UA-Arch"

    # Parse which hints are requested
    requested_hints = parse_accept_ch(accept_ch)
    print(f"\nServer requested hints: {requested_hints}")

    # Get profile and prepare response with requested hints
    profile = get_profile("chrome_120")
    all_hints = profile.get("client_hints", {})

    print("\nHints to send in next request:")
    for hint_name, hint_value in all_hints.items():
        if hint_name in requested_hints or hint_name in [
            "Sec-CH-UA",
            "Sec-CH-UA-Mobile",
            "Sec-CH-UA-Platform",
        ]:
            print(f"  {hint_name}: {hint_value}")


def example_webgl_renderers():
    """Access predefined WebGL renderer strings."""
    print("\n" + "=" * 60)
    print("Example 7: Predefined WebGL Renderers")
    print("=" * 60)

    print("\nAvailable WebGL renderer presets:")
    for key, value in WEBGL_RENDERERS.items():
        print(f"\n  {key}:")
        print(f"    Vendor: {value['vendor']}")
        print(f"    Renderer: {value['renderer']}")


def example_full_impersonation():
    """Complete example showing full browser impersonation."""
    print("\n" + "=" * 60)
    print("Example 8: Full Browser Impersonation Request")
    print("=" * 60)

    # Create client with Chrome impersonation
    client = Client(impersonate="chrome_120")

    # Get profile data for reference
    profile = get_profile("chrome_120")

    print("\nImpersonation profile includes:")
    print(f"  - TLS fingerprint: {len(profile['tls']['ciphers'])} chars cipher string")
    print(f"  - HTTP/2 settings: {list(profile['http2']['settings'].keys())}")
    print(f"  - Client hints: {list(profile.get('client_hints', {}).keys())}")
    print(f"  - Canvas/WebGL: {list(profile.get('canvas_webgl', {}).keys())}")

    # Headers that will be sent (Sec-CH-UA included automatically)
    print("\nHeaders with Sec-CH-UA (sent automatically):")
    for name, value in profile["headers"]["default"][:6]:
        print(f"  {name}: {value[:60]}..." if len(str(value)) > 60 else f"  {name}: {value}")

    # Example request (uncomment to run)
    # response = client.get("https://tls.browserleaks.com/json")
    # print(response.json())

    client.close()


if __name__ == "__main__":
    example_basic_client_hints()
    example_extract_client_hints()
    example_canvas_webgl_fingerprint()
    example_build_custom_client_hints()
    example_generate_sec_ch_ua()
    example_handle_accept_ch()
    example_webgl_renderers()
    example_full_impersonation()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
