import random
from collections.abc import Iterable


class ProxyRotator:
    def __init__(self, proxies: Iterable[str]) -> None:
        self.proxies = list(proxies)

    def next(self) -> str | None:
        if not self.proxies:
            return None
        return random.choice(self.proxies)
