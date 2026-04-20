#!/usr/bin/env python3
"""Диагностика прокси + roseltorg.ru."""
import requests

HTTP_PROXY  = "http://yq3MUmtH:BqzN3LAa@154.211.9.62:61870"
SOCKS_PROXY = "socks5://yq3MUmtH:BqzN3LAa@154.211.9.62:61871"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# 1. Проверяем IP без прокси
print("=== Без прокси ===")
try:
    r = requests.get("http://httpbin.org/ip", timeout=(5, 5))
    print(f"IP: {r.json()['origin']}")
except Exception as e:
    print(f"ERR: {e}")

# 2. Проверяем IP через HTTP прокси
print("\n=== HTTP прокси ===")
try:
    r = requests.get("http://httpbin.org/ip", proxies={"http": HTTP_PROXY, "https": HTTP_PROXY}, timeout=(8, 8))
    print(f"IP: {r.json()['origin']}")
except Exception as e:
    print(f"ERR: {e}")

# 3. Проверяем IP через SOCKS5 прокси
print("\n=== SOCKS5 прокси ===")
try:
    r = requests.get("http://httpbin.org/ip", proxies={"http": SOCKS_PROXY, "https": SOCKS_PROXY}, timeout=(8, 8))
    print(f"IP: {r.json()['origin']}")
except Exception as e:
    print(f"ERR: {e}")

# 4. Пробуем roseltorg через HTTP прокси с verify=False
print("\n=== roseltorg через HTTP прокси ===")
try:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.proxies.update({"http": HTTP_PROXY, "https": HTTP_PROXY})
    r = s.get("https://www.roseltorg.ru/", timeout=(8, 10), verify=False)
    print(f"[{r.status_code}] OK — {r.text[:100].replace(chr(10),' ')}")
except Exception as e:
    print(f"ERR: {e}")
