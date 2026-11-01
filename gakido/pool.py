from __future__ import annotations

import time
from collections import defaultdict

from .connection import Connection


class ConnectionPool:
    """
    Naive connection pool keyed by (scheme, host, port, proxy_url).

    Args:
        profile: Browser profile passed to created connections
        timeout: Request timeout in seconds
        verify: Whether to verify SSL certificates
        max_per_host: Maximum idle connections kept per pool key
        health_check: Verify pooled connections are still usable before
            handing them out; stale connections are closed and replaced
            (default: False)
        idle_timeout: Close pooled connections that have been idle for more
            than this many seconds; None disables the check (default: None)
    """

    def __init__(
        self,
        profile: dict,
        timeout: float = 10.0,
        verify: bool = True,
        max_per_host: int = 4,
        health_check: bool = False,
        idle_timeout: float | None = None,
    ) -> None:
        if idle_timeout is not None and idle_timeout <= 0:
            raise ValueError("idle_timeout must be > 0 or None")
        self.profile = profile
        self.timeout = timeout
        self.verify = verify
        self.max_per_host = max_per_host
        self.health_check = health_check
        self.idle_timeout = idle_timeout
        self._pools: dict[tuple[str, str, int, str | None], list[Connection]] = (
            defaultdict(list)
        )

    def _is_reusable(self, conn: Connection) -> bool:
        """Decide whether a pooled connection can be handed out again."""
        if conn.closed:
            return False
        if (
            self.idle_timeout is not None
            and time.time() - conn.last_used > self.idle_timeout
        ):
            return False
        if self.health_check and not conn.is_healthy():
            return False
        return True

    def acquire(
        self, scheme: str, host: str, port: int, proxy_url: str | None = None
    ) -> Connection:
        key = (scheme, host, port, proxy_url)
        while self._pools[key]:
            conn = self._pools[key].pop()
            if self._is_reusable(conn):
                return conn
            conn.close()
        return Connection(
            host,
            port,
            scheme,
            self.profile,
            self.timeout,
            self.verify,
            proxy_url=proxy_url,
        )

    def release(self, conn: Connection) -> None:
        if conn.closed:
            return
        key = (conn.scheme, conn.host, conn.port, conn.proxy_url)
        bucket = self._pools[key]
        if len(bucket) >= self.max_per_host:
            conn.close()
            return
        conn.last_used = time.time()
        bucket.append(conn)

    def close(self) -> None:
        for conns in self._pools.values():
            for conn in conns:
                conn.close()
        self._pools.clear()
