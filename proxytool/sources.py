from __future__ import annotations

import re

IP_PORT_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})")

HTTP_SOURCES: list[str] = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http"
    "&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
]

SOCKS5_SOURCES: list[str] = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5"
    "&timeout=10000&country=all",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]
