"""Tests for gakido.proxy module."""

import pytest
from gakido.proxy import ProxyRotator


class TestProxyRotator:
    """Tests for ProxyRotator class."""

    def test_init_with_list(self):
        """Test initialization with list of proxies."""
        proxies = ["http://proxy1:8080", "http://proxy2:8080"]
        rotator = ProxyRotator(proxies)
        assert rotator.proxies == proxies

    def test_init_with_tuple(self):
        """Test initialization with tuple of proxies."""
        proxies = ("http://proxy1:8080", "http://proxy2:8080")
        rotator = ProxyRotator(proxies)
        assert rotator.proxies == list(proxies)

    def test_init_with_generator(self):
        """Test initialization with generator."""
        def gen():
            yield "http://proxy1:8080"
            yield "http://proxy2:8080"

        rotator = ProxyRotator(gen())
        assert len(rotator.proxies) == 2

    def test_init_empty_list(self):
        """Test initialization with empty list."""
        rotator = ProxyRotator([])
        assert rotator.proxies == []

    def test_next_returns_proxy(self):
        """Test next() returns a proxy from the list."""
        proxies = ["http://proxy1:8080", "http://proxy2:8080"]
        rotator = ProxyRotator(proxies)

        result = rotator.next()
        assert result in proxies

    def test_next_empty_returns_none(self):
        """Test next() returns None when no proxies."""
        rotator = ProxyRotator([])
        assert rotator.next() is None

    def test_next_single_proxy(self):
        """Test next() with single proxy always returns it."""
        rotator = ProxyRotator(["http://proxy:8080"])

        for _ in range(10):
            assert rotator.next() == "http://proxy:8080"

    def test_next_random_selection(self):
        """Test next() randomly selects from proxies."""
        proxies = [f"http://proxy{i}:8080" for i in range(10)]
        rotator = ProxyRotator(proxies)

        # With many proxies and many calls, we should see variety
        results = {rotator.next() for _ in range(100)}
        # Should have selected multiple different proxies
        assert len(results) > 1

    def test_proxies_list_is_copy(self):
        """Test internal list is a copy of input."""
        original = ["http://proxy:8080"]
        rotator = ProxyRotator(original)

        # Modifying original shouldn't affect rotator
        original.append("http://proxy2:8080")
        assert len(rotator.proxies) == 1
