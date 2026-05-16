from __future__ import annotations

import asyncio
import urllib.request
from typing import Iterable

from .models import ProxyNode, ProxyType
from .sources import HTTP_SOURCES, SOCKS5_SOURCES, IP_PORT_RE


def _http_get(url: str, timeout_s: float) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Anibus-Scanner/py-proxytool/0.1",
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            if getattr(r, "status", 200) != 200:
                return None
            data = r.read()
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return None


async def _fetch_list(url: str, ptype: ProxyType, timeout_s: float) -> set[ProxyNode]:
    body = await asyncio.to_thread(_http_get, url, timeout_s)
    if not body:
        return set()
    out: set[ProxyNode] = set()
    for m in IP_PORT_RE.finditer(body):
        host = m.group(1)
        try:
            port = int(m.group(2))
        except ValueError:
            continue
        if port < 1 or port > 65535:
            continue
        out.add(ProxyNode(host=host, port=port, type=ptype, country="XX", latency_ms=-1))
    return out


async def harvest(timeout_s: float = 8.0) -> set[ProxyNode]:
    tasks: list[asyncio.Task[set[ProxyNode]]] = []
    for url in HTTP_SOURCES:
        tasks.append(asyncio.create_task(_fetch_list(url, "http", timeout_s)))
    for url in SOCKS5_SOURCES:
        tasks.append(asyncio.create_task(_fetch_list(url, "socks5", timeout_s)))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[tuple[str, int, ProxyType], ProxyNode] = {}
    for r in results:
        if isinstance(r, Exception):
            continue
        for n in r:
            out[n.key()] = n
    return set(out.values())


def harvest_sync(timeout_s: float = 8.0) -> set[ProxyNode]:
    return asyncio.run(harvest(timeout_s=timeout_s))

