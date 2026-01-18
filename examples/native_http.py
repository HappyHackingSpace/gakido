"""
Demonstrate the native gakido_core HTTP fast-path (HTTP/1.1, no TLS).
"""

from gakido import Client


def main() -> None:
    c = Client(use_native=True)
    r = c.get("http://httpbin.org/get")
    print("Native HTTP status:", r.status_code)
    print("Native HTTP body:", r.text[:200])


if __name__ == "__main__":
    main()
