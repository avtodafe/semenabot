#!/usr/bin/env python3
"""Диагностика roseltorg.ru — тестируем AJAX-эндпоинт /procedures/search_ajax."""
import json
import requests
import warnings
warnings.filterwarnings("ignore")

from bs4 import BeautifulSoup

PROXY = "http://yq3MUmtH:BqzN3LAa@195.208.89.54:64310"
PROXIES = {"http": PROXY, "https": PROXY}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://www.roseltorg.ru/procedures/search",
    "X-Requested-With": "XMLHttpRequest",
}


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.proxies.update(PROXIES)
    return s


# 1. IP check
print("=== IP через прокси ===")
s = make_session()
try:
    r = s.get("http://httpbin.org/ip", timeout=(8, 8))
    print(f"IP: {r.json()['origin']}")
except Exception as e:
    print(f"ERR: {e}")

KW = "семена"

# 2. Тестируем AJAX-эндпоинт
print("\n=== /procedures/search_ajax ===")
params = {
    "sale": "1",
    "query_field": KW,
    "status[]": ["0", "1", "2"],
}
url = "https://www.roseltorg.ru/procedures/search_ajax"

try:
    r = s.get(url, params=params, timeout=(10, 30), verify=False)
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type', '?')!r}")
    print(f"Length: {len(r.text)}")
    print(f"URL: {r.url}")

    ct = r.headers.get("content-type", "")
    if "json" in ct:
        d = r.json()
        print("JSON type:", type(d).__name__)
        if isinstance(d, dict):
            print("Keys:", list(d.keys()))
            print(json.dumps(d, ensure_ascii=False, indent=2)[:2000])
        elif isinstance(d, list):
            print(f"List len: {len(d)}")
            if d:
                print("First item:", json.dumps(d[0], ensure_ascii=False, indent=2)[:1000])
    else:
        # HTML response — parse it
        soup = BeautifulSoup(r.text, "lxml")
        print("\n--- HTML структура ---")

        # Ищем карточки процедур
        selectors_to_try = [
            ".procedure-item",
            ".procedures__item",
            "[class*='procedure-item']",
            "[class*='procedures__item']",
            ".lot-item",
            ".search-result",
            ".search-item",
            ".tender-item",
            "li[data-id]",
            "div[data-id]",
            "article",
            "tr[data-href]",
        ]
        for sel in selectors_to_try:
            items = soup.select(sel)
            if items:
                print(f"  Found {len(items)} items with selector {sel!r}")
                print("  First item:")
                print("  ", items[0].get_text(" ", strip=True)[:300])
                print("  First item attrs:", items[0].attrs)
                # Ищем ссылки внутри
                links = items[0].find_all("a", href=True)
                for a in links[:5]:
                    print(f"    link: {a['href']!r} — {a.get_text(strip=True)[:80]!r}")
                break
        else:
            print("  Не нашли карточек стандартными селекторами")
            # Dump all classes
            classes = set()
            for tag in soup.find_all(True):
                for c in (tag.get("class") or []):
                    classes.add(c)
            relevant = [c for c in sorted(classes) if any(k in c for k in
                        ("proc", "tender", "lot", "item", "result", "search", "card", "row"))]
            print("  Relevant classes:", relevant[:30])
            print("\n  Raw HTML[:3000]:")
            print(r.text[:3000])
except Exception as e:
    import traceback
    print(f"ERR: {e}")
    traceback.print_exc()

# 3. Без фильтра sale — все закупки
print("\n=== /procedures/search_ajax без sale (все типы) ===")
try:
    params2 = {"query_field": KW}
    r2 = s.get(url, params=params2, timeout=(10, 30), verify=False)
    print(f"Status: {r2.status_code}  len={len(r2.text)}")
    if r2.text != r.text:
        print("Ответ отличается от предыдущего")
        soup2 = BeautifulSoup(r2.text, "lxml")
        items2 = soup2.select("[class*='procedure']") or soup2.select("article")
        print(f"Items found: {len(items2)}")
except Exception as e:
    print(f"ERR: {e}")

# 4. Проверяем одну конкретную процедуру (коммерческая)
print("\n=== Одна конкретная процедура ===")
try:
    r3 = s.get("https://www.roseltorg.ru/procedure/B1902251253579",
               timeout=(10, 20), verify=False)
    print(f"Status: {r3.status_code}  len={len(r3.text)}")
    soup3 = BeautifulSoup(r3.text, "lxml")
    # Ищем заголовок, номер, цену, дату
    for sel in [".procedure-header", ".procedure__title", "h1", ".lot-title"]:
        el = soup3.select_one(sel)
        if el:
            print(f"  {sel}: {el.get_text(strip=True)[:200]!r}")
    print("  Classes on page (relevant):")
    classes = {c for t in soup3.find_all(True) for c in (t.get("class") or [])}
    relevant = sorted(c for c in classes if any(k in c for k in
                      ("proc", "tender", "lot", "title", "price", "date", "num", "info")))
    print("  ", relevant[:30])
except Exception as e:
    print(f"ERR: {e}")
