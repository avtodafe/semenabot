#!/usr/bin/env python3
"""Диагностика roseltorg.ru через прокси."""
import requests

PROXY = "http://yq3MUmtH:BqzN3LAa@154.211.9.62:61870"
PROXIES = {"http": PROXY, "https": PROXY}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

urls = [
    ("Главная",     "https://www.roseltorg.ru/"),
    ("Поиск",       "https://www.roseltorg.ru/search/?query=семена&minPrice=100000"),
    ("JSON API?",   "https://www.roseltorg.ru/api/search?query=семена"),
]

s = requests.Session()
s.headers.update(HEADERS)
s.proxies.update(PROXIES)

for name, url in urls:
    try:
        r = s.get(url, timeout=(8, 10), allow_redirects=True)
        ct = r.headers.get("Content-Type", "")[:60]
        cf = "⚠️ Cloudflare" if "cloudflare" in r.text.lower() else ""
        print(f"\n[{r.status_code}] {name} {cf}")
        print(f"  Content-Type: {ct}")
        print(f"  Body: {r.text[:300].replace(chr(10), ' ')}")
    except Exception as e:
        print(f"\n[ERR] {name}: {e}")
