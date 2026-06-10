from __future__ import annotations

import re

IP_PORT_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})")

HTTP_SOURCES: list[str] = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/http.txt".
    "https://advanced.name/freeproxy/6a29dcccb0aa6?type=http?type=https?type=anon?type=elite"
]

SOCKS5_SOURCES: list[str] = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]
