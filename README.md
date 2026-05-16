# Python Proxy Tool (harvester/checker/verify)

Самодостаточный аналог Java-модуля `it.r2u.anibus.service.network.proxy`, но на Python 3.11+.

Функции:
- `harvest` — сбор raw прокси из публичных источников.
- `check` — быстрая проверка "живой ли прокси" через TCP + CONNECT/SOCKS5 CONNECT + измерение latency.
- `verify` — проверка реальным HTTP-запросом через прокси (дополнительный фильтр).

## Быстрый старт

1) Собрать и проверить:

```powershell
python -m proxytool run --out out_proxies.jsonl
```

2) Только собрать:

```powershell
python -m proxytool harvest --out raw.jsonl
```

3) Проверить ранее собранный файл:

```powershell
python -m proxytool check --in raw.jsonl --out live.jsonl
```

4) Верифицировать (реальный HTTP GET через прокси):

```powershell
python -m proxytool verify --in live.jsonl --out verified.jsonl
```

## Формат файлов

`*.jsonl`, по одной записи на строку:

```json
{"host":"1.2.3.4","port":8080,"type":"http","country":"XX","latency_ms":123}
```

## Полезные опции
- `--concurrency 200` — параллелизм проверок.
- `--connect-timeout 4.0` — таймаут TCP/handshake.
- `--max-latency 8.0` — максимальная latency (сек).
- `--types http socks5` — ограничить типы.
- `--limit N` — ограничить количество проверяемых прокси (для smoke-теста).
- `--http-fallback-host/--http-fallback-port/--http-fallback-path` — fallback для HTTP-прокси в `check`, если `CONNECT` заблокирован (по умолчанию `example.com:80/`).

## Замечания
- Для `check` используется "тройной handshake" по аналогии с Java:
  - HTTP: TCP connect → `CONNECT <probe_host>:<probe_port>` → ответ 200.
  - SOCKS5: TCP connect → RFC1928 handshake → CONNECT к probe endpoint.
- Для `verify` делается HTTP GET к `http://example.com/` (по умолчанию).
