from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import json

from .harvester import harvest
from .checker import check_all
from .io import read_jsonl, write_jsonl
from .models import ProxyNode
from .verifier import verify_all

def export_raw_links_from_verified_jsonl(
    src: str = "output/verified.jsonl",
    dst: str = "output/raw.txt",
) -> None:
    Path("output").mkdir(exist_ok=True)

    with open(src, "r", encoding="utf-8") as f_in, open(dst, "w", encoding="utf-8") as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)

            host = obj.get("host")
            port = obj.get("port")
            proto = (obj.get("type") or "http").lower()

            if not host or not port:
                continue

            # нормализация протокола
            if "socks" in proto:
                scheme = "socks5"
            else:
                scheme = "http"

            f_out.write(f"{scheme}://{host}:{port}\n")
            
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="proxytool", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_h = sub.add_parser("harvest", help="Harvest raw proxies from public sources")
    p_h.add_argument("--out", required=True, help="Output jsonl path")
    p_h.add_argument("--timeout", type=float, default=8.0, help="Source fetch timeout (s)")

    p_c = sub.add_parser("check", help="Check proxies via TCP+CONNECT/SOCKS5 CONNECT, measure latency")
    p_c.add_argument("--in", dest="inp", required=True, help="Input jsonl path")
    p_c.add_argument("--out", required=True, help="Output jsonl path")
    p_c.add_argument("--concurrency", type=int, default=200)
    p_c.add_argument("--limit", type=int, default=None)
    p_c.add_argument("--connect-timeout", type=float, default=4.0)
    p_c.add_argument("--max-latency", type=float, default=8.0)
    p_c.add_argument("--probe-host", type=str, default="8.8.8.8")
    p_c.add_argument("--probe-port", type=int, default=80)
    p_c.add_argument("--types", nargs="+", choices=["http", "socks5"], default=["http", "socks5"])
    p_c.add_argument("--http-fallback-host", type=str, default="example.com")
    p_c.add_argument("--http-fallback-port", type=int, default=80)
    p_c.add_argument("--http-fallback-path", type=str, default="/")

    p_v = sub.add_parser("verify", help="Verify proxies by doing real HTTP GET through them")
    p_v.add_argument("--in", dest="inp", required=True, help="Input jsonl path")
    p_v.add_argument("--out", required=True, help="Output jsonl path")
    p_v.add_argument("--concurrency", type=int, default=200)
    p_v.add_argument("--limit", type=int, default=None)
    p_v.add_argument("--timeout", type=float, default=6.0)
    p_v.add_argument("--types", nargs="+", choices=["http", "socks5"], default=["http", "socks5"])
    p_v.add_argument("--url-host", type=str, default="example.com")
    p_v.add_argument("--url-port", type=int, default=80)
    p_v.add_argument("--url-path", type=str, default="/")

    p_r = sub.add_parser("run", help="Harvest -> check -> verify (optional)")
    p_r.add_argument("--out", required=True, help="Output jsonl path (verified if --verify, else live)")
    p_r.add_argument("--raw-out", default=None, help="Optional raw jsonl path to persist harvested list")
    p_r.add_argument("--live-out", default=None, help="Optional live jsonl path to persist checked list")
    p_r.add_argument("--timeout", type=float, default=8.0, help="Source fetch timeout (s)")
    p_r.add_argument("--concurrency", type=int, default=200)
    p_r.add_argument("--limit", type=int, default=None)
    p_r.add_argument("--connect-timeout", type=float, default=4.0)
    p_r.add_argument("--max-latency", type=float, default=8.0)
    p_r.add_argument("--probe-host", type=str, default="8.8.8.8")
    p_r.add_argument("--probe-port", type=int, default=80)
    p_r.add_argument("--types", nargs="+", choices=["http", "socks5"], default=["http", "socks5"])
    p_r.add_argument("--http-fallback-host", type=str, default="example.com")
    p_r.add_argument("--http-fallback-port", type=int, default=80)
    p_r.add_argument("--http-fallback-path", type=str, default="/")
    p_r.add_argument("--verify", action="store_true", help="Run verify stage with HTTP GET")
    p_r.add_argument("--verify-timeout", type=float, default=6.0)
    p_r.add_argument("--url-host", type=str, default="example.com")
    p_r.add_argument("--url-port", type=int, default=80)
    p_r.add_argument("--url-path", type=str, default="/")

    return p.parse_args(argv)


async def _cmd_harvest(ns: argparse.Namespace) -> int:
    nodes = await harvest(timeout_s=float(ns.timeout))
    write_jsonl(ns.out, nodes)
    print(f"[harvest] wrote {len(nodes)} candidates to {ns.out}")
    return 0


async def _cmd_check(ns: argparse.Namespace) -> int:
    nodes = list(read_jsonl(ns.inp))
    allowed = set(ns.types)
    nodes = [n for n in nodes if n.type in allowed]
    live = await check_all(
        nodes,
        concurrency=int(ns.concurrency),
        limit=ns.limit,
        probe_host=str(ns.probe_host),
        probe_port=int(ns.probe_port),
        http_fallback_host=str(ns.http_fallback_host),
        http_fallback_port=int(ns.http_fallback_port),
        http_fallback_path=str(ns.http_fallback_path),
        connect_timeout_s=float(ns.connect_timeout),
        max_latency_s=float(ns.max_latency),
        progress=True,
    )
    write_jsonl(ns.out, live)
    print(f"[check] wrote {len(live)} live proxies to {ns.out}")
    return 0


async def _cmd_verify(ns: argparse.Namespace) -> int:
    nodes = list(read_jsonl(ns.inp))
    allowed = set(ns.types)
    nodes = [n for n in nodes if n.type in allowed]
    ok = await verify_all(
        nodes,
        concurrency=int(ns.concurrency),
        limit=ns.limit,
        url_host=str(ns.url_host),
        url_port=int(ns.url_port),
        url_path=str(ns.url_path),
        timeout_s=float(ns.timeout),
        progress=True,
    )
    write_jsonl(ns.out, ok)
    print(f"[verify] wrote {len(ok)} verified proxies to {ns.out}")
    export_raw_links_from_verified_jsonl(ns.out, "output/raw.txt")
    return 0


async def _cmd_run(ns: argparse.Namespace) -> int:
    raw = await harvest(timeout_s=float(ns.timeout))
    allowed = set(ns.types)
    raw = {n for n in raw if n.type in allowed}
    if ns.raw_out:
        write_jsonl(ns.raw_out, raw)
        print(f"[run] wrote raw={len(raw)} to {ns.raw_out}")
        export_raw_links_from_verified_jsonl(ns.out, "output/raw.txt")
    else:
        print(f"[run] harvested raw={len(raw)}")

    live = await check_all(
        raw,
        concurrency=int(ns.concurrency),
        limit=ns.limit,
        probe_host=str(ns.probe_host),
        probe_port=int(ns.probe_port),
        http_fallback_host=str(ns.http_fallback_host),
        http_fallback_port=int(ns.http_fallback_port),
        http_fallback_path=str(ns.http_fallback_path),
        connect_timeout_s=float(ns.connect_timeout),
        max_latency_s=float(ns.max_latency),
        progress=True,
    )
    if ns.live_out:
        write_jsonl(ns.out, verified)
        print(f"[run] wrote verified={len(verified)} to {ns.out}")
        export_raw_links_from_verified_jsonl(ns.out, "output/raw.txt")
        
        export_raw_links_from_verified_jsonl(ns.out, "output/raw.txt")
    else:
        print(f"[run] checked live={len(live)}")

    if ns.verify:
        verified = await verify_all(
            live,
            concurrency=int(ns.concurrency),
            limit=ns.limit,
            url_host=str(ns.url_host),
            url_port=int(ns.url_port),
            url_path=str(ns.url_path),
            timeout_s=float(ns.verify_timeout),
            progress=True,
        )
        write_jsonl(ns.out, verified)
        print(f"[run] wrote verified={len(verified)} to {ns.out}")
        export_raw_links_from_verified_jsonl(ns.out, "output/raw.txt")
    else:
        write_jsonl(ns.out, live)
        print(f"[run] wrote live={len(live)} to {ns.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    if ns.cmd == "harvest":
        return asyncio.run(_cmd_harvest(ns))
    if ns.cmd == "check":
        return asyncio.run(_cmd_check(ns))
    if ns.cmd == "verify":
        return asyncio.run(_cmd_verify(ns))
    if ns.cmd == "run":
        return asyncio.run(_cmd_run(ns))
    raise SystemExit(2)
