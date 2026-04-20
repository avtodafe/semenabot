#!/usr/bin/env python3
"""Диагностика roseltorg.ru — что именно блокирует."""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

urls = [
    ("Главная",          "https://www.roseltorg.ru/"),
    ("Поиск HTML",       "https://www.roseltorg.ru/search/?query=семена&minPrice=100000"),
    ("Поиск JSON?",      "https://www.roseltorg.ru/api/search?query=семена"),
    ("Процедуры JSON?",  "https://www.roseltorg.ru/api/procedures?search=семена"),
    ("RSS?",             "https://www.roseltorg.ru/rss/"),
]

s = requests.Session()
s.headers.update(HEADERS)

for name, url in urls:
    try:
        r = s.get(url, timeout=15, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")[:50]
        body = r.text[:200].replace("\n", " ")
        cf = "Cloudflare" if "cloudflare" in r.text.lower() or "cf-ray" in str(r.headers).lower() else ""
        print(f"\n[{r.status_code}] {name}")
        print(f"  Content-Type: {ct}")
        if cf:
            print(f"  ⚠️  {cf} обнаружен")
        print(f"  Body: {body[:150]}")
    except Exception as e:
        print(f"\n[ERR] {name}: {e}")
