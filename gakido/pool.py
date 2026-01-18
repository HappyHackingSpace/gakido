from __future__ import annotations

from collections import defaultdict

from .connection import Connection


class ConnectionPool:
    """
    Naive connection pool keyed by (scheme, host, port).
    """

    def __init__(
        self,
        profile: dict,
        timeout: float = 10.0,
        verify: bool = True,
        max_per_host: int = 4,
    ) -> None:
        self.profile = profile
        self.timeout = timeout
        self.verify = verify
        self.max_per_host = max_per_host
        self._pools: dict[tuple[str, str, int], list[Connection]] = defaultdict(list)

    def acquire(self, scheme: str, host: str, port: int) -> Connection:
        key = (scheme, host, port)
        while self._pools[key]:
            conn = self._pools[key].pop()
            if not conn.closed:
                return conn
        return Connection(host, port, scheme, self.profile, self.timeout, self.verify)

    def release(self, conn: Connection) -> None:
        if conn.closed:
            return
        key = (conn.scheme, conn.host, conn.port)
        bucket = self._pools[key]
        if len(bucket) >= self.max_per_host:
            conn.close()
            return
        bucket.append(conn)

    def close(self) -> None:
        for conns in self._pools.values():
            for conn in conns:
                conn.close()
        self._pools.clear()
