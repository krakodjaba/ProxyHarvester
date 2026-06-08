from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Iterable

from .models import ProxyNode


async def _read_some(reader: asyncio.StreamReader, n: int, timeout_s: float) -> bytes:
    return await asyncio.wait_for(reader.read(n), timeout=timeout_s)


async def _validate_http_connect(
    node: ProxyNode,
    probe_host: str,
    probe_port: int,
    connect_timeout_s: float,
) -> int | None:
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.host, node.port), timeout=connect_timeout_s
        )
        try:
            req = (
                f"CONNECT {probe_host}:{probe_port} HTTP/1.1\\r\\n"
                f"Host: {probe_host}:{probe_port}\\r\\n"
                "Proxy-Connection: keep-alive\\r\\n"
                "User-Agent: Anibus-Scanner/py-proxytool/0.1\\r\\n"
                "\\r\\n"
            ).encode("ascii", errors="ignore")
            writer.write(req)
            await asyncio.wait_for(writer.drain(), timeout=connect_timeout_s)
            resp = await _read_some(reader, 64, timeout_s=connect_timeout_s)
            if not resp:
                return None
            head = resp.decode("ascii", errors="ignore")
            if head.startswith("HTTP/1.1 200") or head.startswith("HTTP/1.0 200"):
                return int((time.perf_counter() - start) * 1000)
            return None
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
    except Exception:
        return None


async def _validate_http_get(
    node: ProxyNode,
    url_host: str,
    url_port: int,
    url_path: str,
    connect_timeout_s: float,
) -> int | None:
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.host, node.port), timeout=connect_timeout_s
        )
        try:
            req = (
                f"GET http://{url_host}:{url_port}{url_path} HTTP/1.1\r\n"
                f"Host: {url_host}\r\n"
                "Connection: close\r\n"
                "User-Agent: Anibus-Scanner/py-proxytool/0.1\r\n"
                "\r\n"
            ).encode("ascii", errors="ignore")
            writer.write(req)
            await asyncio.wait_for(writer.drain(), timeout=connect_timeout_s)
            resp = await _read_some(reader, 64, timeout_s=connect_timeout_s)
            if not resp:
                return None
            head = resp.decode("ascii", errors="ignore")
            first = head.split("\r\n", 1)[0]
            parts = first.split(" ", 2)
            if len(parts) >= 2 and parts[0].startswith("HTTP/"):
                try:
                    code = int(parts[1])
                except ValueError:
                    return None
                if 200 <= code < 400:
                    return int((time.perf_counter() - start) * 1000)
            return None
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
    except Exception:
        return None


async def _validate_socks5_connect(
    node: ProxyNode,
    probe_host: str,
    probe_port: int,
    connect_timeout_s: float,
) -> int | None:
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.host, node.port), timeout=connect_timeout_s
        )
        try:
            # Greeting: VER=5, NMETHODS=1, METHOD=0 (no-auth)
            writer.write(b"\x05\x01\x00")
            await asyncio.wait_for(writer.drain(), timeout=connect_timeout_s)
            sel = await _read_some(reader, 2, timeout_s=connect_timeout_s)
            if len(sel) != 2 or sel[0] != 0x05 or sel[1] != 0x00:
                return None

            # CONNECT request: VER=5, CMD=1, RSV=0, ATYP=1 (IPv4)
            host_parts = probe_host.split(".")
            if len(host_parts) != 4:
                return None
            try:
                addr = bytes(int(x) & 0xFF for x in host_parts)
            except ValueError:
                return None
            port = int(probe_port) & 0xFFFF
            req = b"\x05\x01\x00\x01" + addr + port.to_bytes(2, "big")
            writer.write(req)
            await asyncio.wait_for(writer.drain(), timeout=connect_timeout_s)

            # Reply: VER, REP, RSV, ATYP, BND.ADDR..., BND.PORT
            head = await _read_some(reader, 4, timeout_s=connect_timeout_s)
            if len(head) != 4 or head[0] != 0x05:
                return None
            rep = head[1]
            if rep != 0x00:
                return None

            atyp = head[3]
            if atyp == 0x01:  # IPv4
                await _read_some(reader, 4 + 2, timeout_s=connect_timeout_s)
            elif atyp == 0x03:  # DOMAIN
                ln = await _read_some(reader, 1, timeout_s=connect_timeout_s)
                await _read_some(reader, int(ln[0]) + 2, timeout_s=connect_timeout_s)
            elif atyp == 0x04:  # IPv6
                await _read_some(reader, 16 + 2, timeout_s=connect_timeout_s)
            else:
                return None

            return int((time.perf_counter() - start) * 1000)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
    except Exception:
        return None


async def check_one(
    node: ProxyNode,
    *,
    probe_host: str = "8.8.8.8",
    probe_port: int = 80,
    http_fallback_host: str = "example.com",
    http_fallback_port: int = 80,
    http_fallback_path: str = "/",
    connect_timeout_s: float = 4.0,
    max_latency_s: float = 8.0,
) -> ProxyNode | None:
    if node.type == "http":
        latency = await _validate_http_connect(
            node, probe_host=probe_host, probe_port=probe_port, connect_timeout_s=connect_timeout_s
        )
        if latency is None:
            latency = await _validate_http_get(
                node,
                url_host=http_fallback_host,
                url_port=http_fallback_port,
                url_path=http_fallback_path,
                connect_timeout_s=connect_timeout_s,
            )
    else:
        latency = await _validate_socks5_connect(
            node, probe_host=probe_host, probe_port=probe_port, connect_timeout_s=connect_timeout_s
        )
    if latency is None:
        return None
    if latency > int(max_latency_s * 1000):
        return None
    return node.with_latency(latency).enrich_country()


async def check_all(
    nodes: Iterable[ProxyNode],
    *,
    concurrency: int = 200,
    limit: int | None = None,
    probe_host: str = "8.8.8.8",
    probe_port: int = 80,
    http_fallback_host: str = "example.com",
    http_fallback_port: int = 80,
    http_fallback_path: str = "/",
    connect_timeout_s: float = 4.0,
    max_latency_s: float = 8.0,
    progress: bool = True,
) -> list[ProxyNode]:
    items = list(nodes)
    if limit is not None:
        items = items[: max(0, int(limit))]

    sem = asyncio.Semaphore(max(1, int(concurrency)))
    live: list[ProxyNode] = []
    checked = 0
    total = len(items)

    async def worker(n: ProxyNode) -> None:
        nonlocal checked
        async with sem:
            res = await check_one(
                n,
                probe_host=probe_host,
                probe_port=probe_port,
                http_fallback_host=http_fallback_host,
                http_fallback_port=http_fallback_port,
                http_fallback_path=http_fallback_path,
                connect_timeout_s=connect_timeout_s,
                max_latency_s=max_latency_s,
            )
        if res is not None:
            live.append(res)
        checked += 1
        if progress and (checked == total or checked % 50 == 0):
            print(f"[check] {checked}/{total} checked, live={len(live)}", flush=True)

    await asyncio.gather(*(worker(n) for n in items), return_exceptions=True)
    live.sort(key=lambda x: x.latency_ms)
    return live


def check_all_sync(nodes: Iterable[ProxyNode], **kwargs) -> list[ProxyNode]:
    return asyncio.run(check_all(nodes, **kwargs))
