from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal
from .geo import get_country

ProxyType = Literal["http", "socks5"]


@dataclass(frozen=True, slots=True)
class ProxyNode:
    host: str
    port: int
    type: ProxyType
    country: str = "XX"
    latency_ms: int = -1

    def with_latency(self, latency_ms: int) -> "ProxyNode":
        return replace(self, latency_ms=latency_ms)

    def enrich_country(self) -> "ProxyNode":
        return replace(self, country=get_country(self.host))

    def key(self) -> tuple[str, int, ProxyType]:
        return (self.host, self.port, self.type)

