#!/usr/bin/env python3
"""Диагностика прокси + roseltorg.ru — поиск правильных URL."""
import requests
import warnings
warnings.filterwarnings("ignore")

from bs4 import BeautifulSoup

PROXY = "http://yq3MUmtH:BqzN3LAa@195.208.89.54:64310"
PROXIES = {"http": PROXY, "https": PROXY}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.proxies.update(PROXIES)
    return s


# 1. Проверяем IP через прокси
print("=== IP через прокси ===")
try:
    s = make_session()
    r = s.get("http://httpbin.org/ip", timeout=(8, 8))
    print(f"IP: {r.json()['origin']}")
except Exception as e:
    print(f"ERR: {e}")

# 2. Главная страница roseltorg.ru
print("\n=== Главная roseltorg.ru ===")
try:
    s = make_session()
    r = s.get("https://www.roseltorg.ru/", timeout=(10, 20), verify=False)
    print(f"[{r.status_code}] len={len(r.text)}")
    soup = BeautifulSoup(r.text, "lxml")

    # Ищем все ссылки с ключевыми словами
    print("\n--- Ссылки с tender/search/auction/proced/lot/zakup ---")
    seen = set()
    for a in soup.find_all("a", href=True):
        h = a["href"]
        txt = a.get_text(strip=True)[:60]
        kws = ("tender", "search", "auction", "proced", "lot", "zakup",
               "purchase", "trade", "торг", "закуп", "аукцион", "процедур")
        if any(k in h.lower() or k in txt.lower() for k in kws) and h not in seen:
            seen.add(h)
            print(f"  {h!r:50s} {txt!r}")

    # Главное меню
    print("\n--- Nav / header links ---")
    for sel in ["nav a", ".nav a", ".menu a", "header a", ".header a", ".main-nav a"]:
        items = soup.select(sel)
        if items:
            print(f"[{sel}]")
            for a in items[:15]:
                print(f"  {a.get('href')!r:50s} {a.get_text(strip=True)!r}")

    # Формы поиска
    print("\n--- Формы ---")
    for form in soup.find_all("form"):
        print(f"  action={form.get('action')!r} method={form.get('method')!r}")
        for inp in form.find_all(["input", "select"]):
            print(f"    name={inp.get('name')!r} type={inp.get('type')!r} value={inp.get('value','')!r}")

except Exception as e:
    print(f"ERR: {e}")
    import traceback; traceback.print_exc()

# 3. Пробуем известные пути API / поиска
print("\n=== Пробуем пути поиска ===")
paths = [
    "/procedures",
    "/procedures/list",
    "/procedures/search",
    "/search",
    "/search/",
    "/search/?query=семена",
    "/search/?q=семена",
    "/search/?text=семена",
    "/tender/search",
    "/tenders",
    "/tenders/search",
    "/auctions",
    "/purchases",
    "/marketplace",
    "/market",
    "/trade",
    "/trades",
    "/zakupki",
    "/lots",
    "/catalog",
    "/catalog/search",
    "/node",
    "/content",
    "/api/search",
    "/api/v1/procedures",
    "/api/v1/lots",
    "/views/ajax",
    "/ru/search/node/семена",
    "/ru/search/node?keys=семена",
]
for path in paths:
    try:
        s = make_session()
        url = f"https://www.roseltorg.ru{path}"
        r = s.get(url, timeout=(5, 10), verify=False, allow_redirects=True)
        print(f"  [{r.status_code}] {path} (final: {r.url})")
        if r.status_code == 200 and len(r.text) > 500:
            # Ищем результаты
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.string if soup.title else "?"
            print(f"    title: {title!r}")
    except Exception as e:
        print(f"  [ERR] {path}: {str(e)[:60]}")

