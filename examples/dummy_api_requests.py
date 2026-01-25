#!/usr/bin/env python3
"""
Dummy API Requests Example

Demonstrates gakido with various free public API endpoints for testing HTTP requests.
All endpoints are free, require no authentication, and are great for development/testing.

Usage:
    uv run python examples/dummy_api_requests.py
    uv run python examples/dummy_api_requests.py --async
    uv run python examples/dummy_api_requests.py --profile firefox_147
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any

from gakido import Client
from gakido.aio import AsyncClient


# =============================================================================
# Free Dummy API Endpoints
# =============================================================================

DUMMY_APIS = {
    # JSONPlaceholder - Fake REST API
    "jsonplaceholder": {
        "base_url": "https://jsonplaceholder.typicode.com",
        "endpoints": {
            "posts": "/posts",
            "post_1": "/posts/1",
            "comments": "/comments?postId=1",
            "users": "/users",
            "user_1": "/users/1",
            "todos": "/todos",
            "albums": "/albums",
            "photos": "/photos?albumId=1",
        },
        "description": "Fake REST API for testing and prototyping",
    },
    # HTTPBin - HTTP Request & Response Service
    "httpbin": {
        "base_url": "https://httpbin.org",
        "endpoints": {
            "get": "/get",
            "headers": "/headers",
            "ip": "/ip",
            "user_agent": "/user-agent",
            "uuid": "/uuid",
            "delay_1": "/delay/1",
            "status_200": "/status/200",
            "json": "/json",
            "gzip": "/gzip",
            "deflate": "/deflate",
            "brotli": "/brotli",
            "cookies": "/cookies",
            "response_headers": "/response-headers?foo=bar",
        },
        "description": "HTTP Request & Response Service",
    },
    # ReqRes - Fake User API
    "reqres": {
        "base_url": "https://reqres.in",
        "endpoints": {
            "users": "/api/users",
            "users_page2": "/api/users?page=2",
            "user_2": "/api/users/2",
            "resources": "/api/unknown",
            "resource_2": "/api/unknown/2",
        },
        "description": "Fake user data API",
    },
    # DummyJSON - More comprehensive fake data
    "dummyjson": {
        "base_url": "https://dummyjson.com",
        "endpoints": {
            "products": "/products",
            "product_1": "/products/1",
            "products_search": "/products/search?q=phone",
            "categories": "/products/categories",
            "users": "/users",
            "user_1": "/users/1",
            "posts": "/posts",
            "comments": "/comments",
            "quotes": "/quotes",
            "recipes": "/recipes",
            "carts": "/carts",
        },
        "description": "Comprehensive fake JSON data API",
    },
    # Random Data APIs
    "random_data": {
        "base_url": "",
        "endpoints": {
            "random_user": "https://randomuser.me/api/",
            "random_dog": "https://dog.ceo/api/breeds/image/random",
            "random_cat": "https://api.thecatapi.com/v1/images/search",
            "random_fox": "https://randomfox.ca/floof/",
            "random_duck": "https://random-d.uk/api/random",
            "random_joke": "https://official-joke-api.appspot.com/random_joke",
            "random_quote": "https://zenquotes.io/api/random",
            "random_activity": "https://www.boredapi.com/api/activity",
        },
        "description": "Random data generators",
    },
    # IP & Geolocation
    "ip_geo": {
        "base_url": "",
        "endpoints": {
            "ipify": "https://api.ipify.org?format=json",
            "ipinfo": "https://ipinfo.io/json",
            "ip_api": "http://ip-api.com/json/",
        },
        "description": "IP address and geolocation APIs",
    },
    # Public Data APIs
    "public_data": {
        "base_url": "",
        "endpoints": {
            "countries": "https://restcountries.com/v3.1/all?fields=name,capital,population",
            "country_usa": "https://restcountries.com/v3.1/name/usa",
            "universities": "http://universities.hipolabs.com/search?country=United+States",
            "github_users": "https://api.github.com/users",
            "github_repos": "https://api.github.com/repositories",
        },
        "description": "Public data APIs",
    },
}


@dataclass
class RequestResult:
    """Result of an API request."""
    api_name: str
    endpoint_name: str
    url: str
    success: bool
    status_code: int | None = None
    response_preview: str = ""
    error: str | None = None


def make_url(api_config: dict, endpoint_path: str) -> str:
    """Build full URL from API config and endpoint path."""
    base = api_config.get("base_url", "")
    if endpoint_path.startswith("http"):
        return endpoint_path
    return f"{base}{endpoint_path}"


def preview_response(resp_data: Any, max_len: int = 200) -> str:
    """Create a preview of the response data."""
    if isinstance(resp_data, dict):
        text = json.dumps(resp_data, indent=2)
    elif isinstance(resp_data, list):
        text = json.dumps(resp_data[:2], indent=2) + f"\n... ({len(resp_data)} items)"
    else:
        text = str(resp_data)

    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


# =============================================================================
# Sync Client
# =============================================================================

def run_sync_requests(profile: str = "chrome_120", verbose: bool = True) -> list[RequestResult]:
    """Run requests using sync client."""
    results: list[RequestResult] = []

    print(f"\n{'='*70}")
    print(f"  GAKIDO DUMMY API REQUESTS (Sync)")
    print(f"  Profile: {profile}")
    print(f"{'='*70}")

    with Client(impersonate=profile, timeout=15.0) as client:
        for api_name, api_config in DUMMY_APIS.items():
            print(f"\n--- {api_name}: {api_config['description']} ---")

            for endpoint_name, endpoint_path in api_config["endpoints"].items():
                url = make_url(api_config, endpoint_path)

                try:
                    resp = client.get(url)

                    try:
                        data = resp.json()
                        preview = preview_response(data)
                    except Exception:
                        preview = resp.text[:200]

                    result = RequestResult(
                        api_name=api_name,
                        endpoint_name=endpoint_name,
                        url=url,
                        success=resp.status_code in (200, 201),
                        status_code=resp.status_code,
                        response_preview=preview,
                    )

                    if verbose:
                        status = "✅" if result.success else "❌"
                        print(f"  {status} {endpoint_name:20s} HTTP {resp.status_code}")

                except Exception as e:
                    result = RequestResult(
                        api_name=api_name,
                        endpoint_name=endpoint_name,
                        url=url,
                        success=False,
                        error=str(e),
                    )
                    if verbose:
                        print(f"  ❌ {endpoint_name:20s} ERROR: {str(e)[:50]}")

                results.append(result)

    return results


# =============================================================================
# Async Client
# =============================================================================

async def run_async_requests(profile: str = "chrome_120", verbose: bool = True) -> list[RequestResult]:
    """Run requests using async client."""
    results: list[RequestResult] = []

    print(f"\n{'='*70}")
    print(f"  GAKIDO DUMMY API REQUESTS (Async)")
    print(f"  Profile: {profile}")
    print(f"{'='*70}")

    async with AsyncClient(impersonate=profile, timeout=15.0) as client:
        for api_name, api_config in DUMMY_APIS.items():
            print(f"\n--- {api_name}: {api_config['description']} ---")

            for endpoint_name, endpoint_path in api_config["endpoints"].items():
                url = make_url(api_config, endpoint_path)

                try:
                    resp = await client.get(url)

                    try:
                        data = resp.json()
                        preview = preview_response(data)
                    except Exception:
                        preview = resp.text[:200]

                    result = RequestResult(
                        api_name=api_name,
                        endpoint_name=endpoint_name,
                        url=url,
                        success=resp.status_code in (200, 201),
                        status_code=resp.status_code,
                        response_preview=preview,
                    )

                    if verbose:
                        status = "✅" if result.success else "❌"
                        print(f"  {status} {endpoint_name:20s} HTTP {resp.status_code}")

                except Exception as e:
                    result = RequestResult(
                        api_name=api_name,
                        endpoint_name=endpoint_name,
                        url=url,
                        success=False,
                        error=str(e),
                    )
                    if verbose:
                        print(f"  ❌ {endpoint_name:20s} ERROR: {str(e)[:50]}")

                results.append(result)

    return results


# =============================================================================
# POST/PUT/DELETE Examples
# =============================================================================

def run_crud_examples(profile: str = "chrome_120") -> None:
    """Demonstrate CRUD operations with dummy APIs."""
    print(f"\n{'='*70}")
    print(f"  CRUD OPERATIONS EXAMPLES")
    print(f"{'='*70}")

    with Client(impersonate=profile, timeout=15.0) as client:
        # POST - Create
        print("\n--- POST (Create) ---")
        post_data = {
            "title": "Test Post",
            "body": "This is a test post created with gakido",
            "userId": 1,
        }
        resp = client.post(
            "https://jsonplaceholder.typicode.com/posts",
            data=json.dumps(post_data).encode(),
            headers={"Content-Type": "application/json"},
        )
        print(f"  POST /posts: HTTP {resp.status_code}")
        print(f"  Response: {resp.json()}")

        # PUT - Update
        print("\n--- PUT (Update) ---")
        put_data = {
            "id": 1,
            "title": "Updated Title",
            "body": "Updated body content",
            "userId": 1,
        }
        resp = client.put(
            "https://jsonplaceholder.typicode.com/posts/1",
            data=json.dumps(put_data).encode(),
            headers={"Content-Type": "application/json"},
        )
        print(f"  PUT /posts/1: HTTP {resp.status_code}")
        print(f"  Response: {resp.json()}")

        # PATCH - Partial Update
        print("\n--- PATCH (Partial Update) ---")
        patch_data = {"title": "Patched Title Only"}
        resp = client.patch(
            "https://jsonplaceholder.typicode.com/posts/1",
            data=json.dumps(patch_data).encode(),
            headers={"Content-Type": "application/json"},
        )
        print(f"  PATCH /posts/1: HTTP {resp.status_code}")
        print(f"  Response: {resp.json()}")

        # DELETE
        print("\n--- DELETE ---")
        resp = client.delete("https://jsonplaceholder.typicode.com/posts/1")
        print(f"  DELETE /posts/1: HTTP {resp.status_code}")

        # POST with form data
        print("\n--- POST (Form Data) ---")
        resp = client.post(
            "https://httpbin.org/post",
            data={"name": "gakido", "version": "0.1.0"},
        )
        print(f"  POST /post (form): HTTP {resp.status_code}")
        form_data = resp.json().get("form", {})
        print(f"  Form data received: {form_data}")


# =============================================================================
# Specific API Examples
# =============================================================================

def run_specific_examples(profile: str = "chrome_120") -> None:
    """Run specific interesting API examples."""
    print(f"\n{'='*70}")
    print(f"  SPECIFIC API EXAMPLES")
    print(f"{'='*70}")

    with Client(impersonate=profile, timeout=15.0) as client:
        # Random User
        print("\n--- Random User ---")
        resp = client.get("https://randomuser.me/api/")
        user = resp.json()["results"][0]
        print(f"  Name: {user['name']['first']} {user['name']['last']}")
        print(f"  Email: {user['email']}")
        print(f"  Country: {user['location']['country']}")

        # Random Joke
        print("\n--- Random Joke ---")
        resp = client.get("https://official-joke-api.appspot.com/random_joke")
        joke = resp.json()
        print(f"  Setup: {joke['setup']}")
        print(f"  Punchline: {joke['punchline']}")

        # IP Info
        print("\n--- Your IP Info ---")
        resp = client.get("https://ipinfo.io/json")
        ip_info = resp.json()
        print(f"  IP: {ip_info.get('ip', 'N/A')}")
        print(f"  City: {ip_info.get('city', 'N/A')}")
        print(f"  Country: {ip_info.get('country', 'N/A')}")

        # Random Quote
        print("\n--- Random Quote ---")
        try:
            resp = client.get("https://zenquotes.io/api/random")
            if resp.status_code == 200:
                quotes = resp.json()
                if quotes and len(quotes) > 0:
                    quote = quotes[0]
                    print(f"  \"{quote.get('q', 'N/A')}\"")
                    print(f"  - {quote.get('a', 'Unknown')}")
            else:
                print(f"  (Quote API returned {resp.status_code})")
        except Exception as e:
            print(f"  (Quote API error: {str(e)[:50]})")

        # DummyJSON Product
        print("\n--- Random Product ---")
        resp = client.get("https://dummyjson.com/products/1")
        product = resp.json()
        print(f"  Product: {product['title']}")
        print(f"  Price: ${product['price']}")
        print(f"  Rating: {product['rating']}/5")


# =============================================================================
# Summary
# =============================================================================

def print_summary(results: list[RequestResult]) -> None:
    """Print summary of results."""
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed

    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  Total requests: {total}")
    print(f"  Successful: {passed} ({passed/total*100:.1f}%)")
    print(f"  Failed: {failed}")

    if failed > 0:
        print("\n  Failed requests:")
        for r in results:
            if not r.success:
                error = r.error or f"HTTP {r.status_code}"
                print(f"    - {r.api_name}/{r.endpoint_name}: {error[:50]}")


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test gakido with free dummy API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available APIs:
  - jsonplaceholder: Fake REST API (posts, users, todos, etc.)
  - httpbin: HTTP request/response testing
  - reqres: Fake user data
  - dummyjson: Products, users, quotes, recipes
  - random_data: Random users, jokes, animals
  - ip_geo: IP address and geolocation
  - public_data: Countries, universities, GitHub

Examples:
    uv run python examples/dummy_api_requests.py
    uv run python examples/dummy_api_requests.py --async
    uv run python examples/dummy_api_requests.py --profile firefox_147
    uv run python examples/dummy_api_requests.py --crud
    uv run python examples/dummy_api_requests.py --examples
        """,
    )
    parser.add_argument(
        "--profile", "-p",
        default="chrome_120",
        help="Browser profile to use (default: chrome_120)",
    )
    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use async client",
    )
    parser.add_argument(
        "--crud",
        action="store_true",
        help="Run CRUD operation examples (POST, PUT, PATCH, DELETE)",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Run specific interesting API examples",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    if args.crud:
        run_crud_examples(args.profile)
    elif args.examples:
        run_specific_examples(args.profile)
    elif args.use_async:
        results = asyncio.run(run_async_requests(args.profile, verbose=not args.quiet))
        print_summary(results)
    else:
        results = run_sync_requests(args.profile, verbose=not args.quiet)
        print_summary(results)


if __name__ == "__main__":
    main()
