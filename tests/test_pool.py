"""Tests for gakido.pool module."""

import pytest
from unittest.mock import Mock, patch
from gakido.pool import ConnectionPool


class TestConnectionPool:
    """Tests for ConnectionPool class."""

    def test_init_defaults(self):
        """Test pool initialization with defaults."""
        pool = ConnectionPool(profile={})
        assert pool.timeout == 10.0
        assert pool.verify is True
        assert pool.max_per_host == 4

    def test_init_custom_values(self):
        """Test pool initialization with custom values."""
        pool = ConnectionPool(
            profile={"tls": {}},
            timeout=30.0,
            verify=False,
            max_per_host=8,
        )
        assert pool.timeout == 30.0
        assert pool.verify is False
        assert pool.max_per_host == 8

    def test_acquire_creates_new_connection(self):
        """Test acquire creates new connection when pool empty."""
        pool = ConnectionPool(profile={})
        conn = pool.acquire("https", "example.com", 443)

        assert conn.host == "example.com"
        assert conn.port == 443
        assert conn.scheme == "https"

    def test_release_and_reuse(self):
        """Test released connection can be reused."""
        pool = ConnectionPool(profile={})
        conn1 = pool.acquire("https", "example.com", 443)
        conn1.closed = False  # Simulate open connection

        pool.release(conn1)
        conn2 = pool.acquire("https", "example.com", 443)

        assert conn1 is conn2

    def test_release_closed_connection_ignored(self):
        """Test releasing closed connection doesn't add to pool."""
        pool = ConnectionPool(profile={})
        conn = pool.acquire("https", "example.com", 443)
        conn.closed = True

        pool.release(conn)

        # Should create new connection
        conn2 = pool.acquire("https", "example.com", 443)
        assert conn is not conn2

    def test_max_per_host_limit(self):
        """Test max_per_host limit is respected."""
        pool = ConnectionPool(profile={}, max_per_host=2)

        # Create and release max connections
        conns = []
        for _ in range(3):
            conn = pool.acquire("https", "example.com", 443)
            conn.closed = False
            conns.append(conn)

        # Release all
        for conn in conns:
            pool.release(conn)

        # Only max_per_host should be kept
        key = ("https", "example.com", 443, None)
        assert len(pool._pools[key]) == 2

    def test_different_hosts_separate_pools(self):
        """Test different hosts use separate pools."""
        pool = ConnectionPool(profile={})

        conn1 = pool.acquire("https", "example.com", 443)
        conn2 = pool.acquire("https", "other.com", 443)

        assert conn1.host == "example.com"
        assert conn2.host == "other.com"

    def test_different_ports_separate_pools(self):
        """Test different ports use separate pools."""
        pool = ConnectionPool(profile={})

        conn1 = pool.acquire("https", "example.com", 443)
        conn2 = pool.acquire("https", "example.com", 8443)

        assert conn1.port == 443
        assert conn2.port == 8443

    def test_different_schemes_separate_pools(self):
        """Test different schemes use separate pools."""
        pool = ConnectionPool(profile={})

        conn1 = pool.acquire("http", "example.com", 80)
        conn2 = pool.acquire("https", "example.com", 443)

        assert conn1.scheme == "http"
        assert conn2.scheme == "https"

    def test_close_closes_all_connections(self):
        """Test close() closes all pooled connections."""
        pool = ConnectionPool(profile={})

        # Acquire and release some connections
        conn1 = pool.acquire("https", "example.com", 443)
        conn1.closed = False
        pool.release(conn1)

        conn2 = pool.acquire("https", "other.com", 443)
        conn2.closed = False
        pool.release(conn2)

        # Close pool
        with patch.object(conn1, 'close') as mock_close1, \
             patch.object(conn2, 'close') as mock_close2:
            pool.close()
            mock_close1.assert_called_once()
            mock_close2.assert_called_once()

        assert len(pool._pools) == 0

    def test_acquire_skips_closed_connections(self):
        """Test acquire skips closed connections in pool."""
        pool = ConnectionPool(profile={})

        # Create and release connection, then mark it closed
        conn1 = pool.acquire("https", "example.com", 443)
        conn1.closed = False
        pool.release(conn1)
        conn1.closed = True  # Mark as closed after release

        # Should create new connection
        conn2 = pool.acquire("https", "example.com", 443)
        assert conn1 is not conn2

    def test_profile_passed_to_connection(self):
        """Test profile is passed to created connections."""
        profile = {"tls": {"alpn": ["h2"]}}
        pool = ConnectionPool(profile=profile)

        conn = pool.acquire("https", "example.com", 443)
        assert conn.profile == profile

    def test_timeout_passed_to_connection(self):
        """Test timeout is passed to created connections."""
        pool = ConnectionPool(profile={}, timeout=30.0)
        conn = pool.acquire("https", "example.com", 443)
        assert conn.timeout == 30.0

    def test_verify_passed_to_connection(self):
        """Test verify is passed to created connections."""
        pool = ConnectionPool(profile={}, verify=False)
        conn = pool.acquire("https", "example.com", 443)
        assert conn.verify is False


class TestConnectionPoolHealthCheck:
    """Tests for pool connection health checking."""

    def test_health_check_disabled_by_default(self):
        """Test health_check defaults to False and is_healthy is not called."""
        pool = ConnectionPool(profile={})
        assert pool.health_check is False

        conn = pool.acquire("https", "example.com", 443)
        conn.closed = False
        pool.release(conn)

        with patch.object(conn, 'is_healthy') as mock_healthy:
            reused = pool.acquire("https", "example.com", 443)
            mock_healthy.assert_not_called()
        assert reused is conn

    def test_healthy_connection_reused(self):
        """Test a healthy pooled connection is handed out again."""
        pool = ConnectionPool(profile={}, health_check=True)
        conn = pool.acquire("https", "example.com", 443)
        conn.closed = False
        pool.release(conn)

        with patch.object(conn, 'is_healthy', return_value=True):
            reused = pool.acquire("https", "example.com", 443)
        assert reused is conn

    def test_unhealthy_connection_closed_and_replaced(self):
        """Test an unhealthy pooled connection is closed and replaced."""
        pool = ConnectionPool(profile={}, health_check=True)
        conn = pool.acquire("https", "example.com", 443)
        conn.closed = False
        pool.release(conn)

        with patch.object(conn, 'is_healthy', return_value=False), \
             patch.object(conn, 'close') as mock_close:
            fresh = pool.acquire("https", "example.com", 443)
            mock_close.assert_called_once()
        assert fresh is not conn

    def test_unhealthy_connections_skipped_until_healthy(self):
        """Test unhealthy connections are drained until a healthy one is found."""
        pool = ConnectionPool(profile={}, health_check=True, max_per_host=4)

        bad = pool.acquire("https", "example.com", 443)
        good = pool.acquire("https", "example.com", 443)
        for conn in (good, bad):
            conn.closed = False
            pool.release(conn)

        # LIFO: `bad` (released last) is popped first and discarded.
        with patch.object(bad, 'is_healthy', return_value=False), \
             patch.object(good, 'is_healthy', return_value=True):
            reused = pool.acquire("https", "example.com", 443)
        assert reused is good


class TestConnectionPoolIdleTimeout:
    """Tests for pool idle timeout handling."""

    def test_idle_timeout_disabled_by_default(self):
        """Test idle_timeout defaults to None."""
        pool = ConnectionPool(profile={})
        assert pool.idle_timeout is None

    def test_invalid_idle_timeout_raises(self):
        """Test idle_timeout <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="idle_timeout"):
            ConnectionPool(profile={}, idle_timeout=0)
        with pytest.raises(ValueError, match="idle_timeout"):
            ConnectionPool(profile={}, idle_timeout=-1)

    def test_fresh_connection_reused_within_timeout(self):
        """Test a recently used connection is reused."""
        pool = ConnectionPool(profile={}, idle_timeout=60)
        conn = pool.acquire("https", "example.com", 443)
        conn.closed = False
        pool.release(conn)

        reused = pool.acquire("https", "example.com", 443)
        assert reused is conn

    def test_expired_connection_closed_and_replaced(self):
        """Test a connection idle past the timeout is closed and replaced."""
        pool = ConnectionPool(profile={}, idle_timeout=60)
        conn = pool.acquire("https", "example.com", 443)
        conn.closed = False
        pool.release(conn)
        conn.last_used -= 120  # Simulate 2 minutes of idleness

        with patch.object(conn, 'close') as mock_close:
            fresh = pool.acquire("https", "example.com", 443)
            mock_close.assert_called_once()
        assert fresh is not conn

    def test_release_refreshes_last_used(self):
        """Test release() stamps the connection's last_used time."""
        import time

        pool = ConnectionPool(profile={})
        conn = pool.acquire("https", "example.com", 443)
        conn.closed = False
        conn.last_used = 0.0

        pool.release(conn)
        assert conn.last_used == pytest.approx(time.time(), abs=5)
