from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Iterable

from .models import ProxyNode


async def _read_until(reader: asyncio.StreamReader, token: bytes, timeout_s: float, max_bytes: int) -> bytes:
    buf = bytearray()
    deadline = time.perf_counter() + timeout_s
    while token not in buf and len(buf) < max_bytes:
        left = deadline - time.perf_counter()
        if left <= 0:
            break
        chunk = await asyncio.wait_for(reader.read(4096), timeout=left)
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


async def _verify_http_proxy(
    node: ProxyNode,
    url_host: str,
    url_port: int,
    url_path: str,
    timeout_s: float,
) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.host, node.port), timeout=timeout_s
        )
        try:
            # Absolute-form request is standard for HTTP proxies
            req = (
                f"GET http://{url_host}:{url_port}{url_path} HTTP/1.1\r\n"
                f"Host: {url_host}\r\n"
                "Connection: close\r\n"
                "User-Agent: Anibus-Scanner/py-proxytool/0.1\r\n"
                "\r\n"
            ).encode("ascii", errors="ignore")
            writer.write(req)
            await asyncio.wait_for(writer.drain(), timeout=timeout_s)
            head = await _read_until(reader, b"\r\n\r\n", timeout_s=timeout_s, max_bytes=8192)
            if not head:
                return False
            txt = head.decode("ascii", errors="ignore")
            return txt.startswith("HTTP/1.1 200") or txt.startswith("HTTP/1.0 200")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
    except Exception:
        return False


async def _socks5_connect(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    port: int,
    timeout_s: float,
) -> bool:
    # Greeting
    writer.write(b"\x05\x01\x00")
    await asyncio.wait_for(writer.drain(), timeout=timeout_s)
    sel = await asyncio.wait_for(reader.readexactly(2), timeout=timeout_s)
    if sel[0] != 0x05 or sel[1] != 0x00:
        return False

    # Connect: use DOMAIN to support example.com
    host_bytes = host.encode("idna", errors="ignore")
    if not host_bytes or len(host_bytes) > 255:
        return False
    req = (
        b"\x05\x01\x00\x03"
        + bytes([len(host_bytes)])
        + host_bytes
        + (int(port) & 0xFFFF).to_bytes(2, "big")
    )
    writer.write(req)
    await asyncio.wait_for(writer.drain(), timeout=timeout_s)

    head = await asyncio.wait_for(reader.readexactly(4), timeout=timeout_s)
    if head[0] != 0x05 or head[1] != 0x00:
        return False
    atyp = head[3]
    if atyp == 0x01:
        await asyncio.wait_for(reader.readexactly(4 + 2), timeout=timeout_s)
    elif atyp == 0x03:
        ln = await asyncio.wait_for(reader.readexactly(1), timeout=timeout_s)
        await asyncio.wait_for(reader.readexactly(int(ln[0]) + 2), timeout=timeout_s)
    elif atyp == 0x04:
        await asyncio.wait_for(reader.readexactly(16 + 2), timeout=timeout_s)
    else:
        return False
    return True


async def _verify_socks5_proxy(
    node: ProxyNode,
    url_host: str,
    url_port: int,
    url_path: str,
    timeout_s: float,
) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.host, node.port), timeout=timeout_s
        )
        try:
            ok = await _socks5_connect(reader, writer, host=url_host, port=url_port, timeout_s=timeout_s)
            if not ok:
                return False
            req = (
                f"GET {url_path} HTTP/1.1\r\n"
                f"Host: {url_host}\r\n"
                "Connection: close\r\n"
                "User-Agent: Anibus-Scanner/py-proxytool/0.1\r\n"
                "\r\n"
            ).encode("ascii", errors="ignore")
            writer.write(req)
            await asyncio.wait_for(writer.drain(), timeout=timeout_s)
            head = await _read_until(reader, b"\r\n\r\n", timeout_s=timeout_s, max_bytes=8192)
            if not head:
                return False
            txt = head.decode("ascii", errors="ignore")
            return txt.startswith("HTTP/1.1 200") or txt.startswith("HTTP/1.0 200")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
    except Exception:
        return False


async def verify_one(
    node: ProxyNode,
    *,
    url_host: str = "example.com",
    url_port: int = 80,
    url_path: str = "/",
    timeout_s: float = 6.0,
) -> bool:
    if node.type == "http":
        return await _verify_http_proxy(
            node, url_host=url_host, url_port=url_port, url_path=url_path, timeout_s=timeout_s
        )
    return await _verify_socks5_proxy(
        node, url_host=url_host, url_port=url_port, url_path=url_path, timeout_s=timeout_s
    )


async def verify_all(
    nodes: Iterable[ProxyNode],
    *,
    concurrency: int = 200,
    limit: int | None = None,
    url_host: str = "example.com",
    url_port: int = 80,
    url_path: str = "/",
    timeout_s: float = 6.0,
    progress: bool = True,
) -> list[ProxyNode]:
    items = list(nodes)
    if limit is not None:
        items = items[: max(0, int(limit))]

    sem = asyncio.Semaphore(max(1, int(concurrency)))
    ok_nodes: list[ProxyNode] = []
    checked = 0
    total = len(items)

    async def worker(n: ProxyNode) -> None:
        nonlocal checked
        async with sem:
            ok = await verify_one(
                n, url_host=url_host, url_port=url_port, url_path=url_path, timeout_s=timeout_s
            )
        if ok:
            ok_nodes.append(n)
        checked += 1
        if progress and (checked == total or checked % 50 == 0):
            print(f"[verify] {checked}/{total} checked, ok={len(ok_nodes)}", flush=True)

    await asyncio.gather(*(worker(n) for n in items), return_exceptions=True)
    ok_nodes.sort(key=lambda x: (x.latency_ms, x.country))
    return ok_nodes


def verify_all_sync(nodes: Iterable[ProxyNode], **kwargs) -> list[ProxyNode]:
    return asyncio.run(verify_all(nodes, **kwargs))
