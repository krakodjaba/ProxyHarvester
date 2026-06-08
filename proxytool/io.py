from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator

from .models import ProxyNode


def read_jsonl(path: str | Path) -> Iterator[ProxyNode]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            yield ProxyNode(
                host=str(obj["host"]),
                port=int(obj["port"]),
                type=str(obj["type"]).lower(),  # type: ignore[arg-type]
                country=obj.get("country", "XX"),
                latency_ms=int(obj.get("latency_ms", -1)),
            )


def write_jsonl(path: str | Path, nodes: Iterable[ProxyNode]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for n in nodes:
            f.write(
                json.dumps(
                    {
                        "host": n.host,
                        "port": n.port,
                        "type": str(n.type),
                        "country": n.country,
                        "latency_ms": n.latency_ms,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

