#!/usr/bin/env python3
"""Диагностика roseltorg.ru — поиск правильных URL и API."""
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def make_session(extra_headers=None):
    s = requests.Session()
    s.headers.update(HEADERS)
    if extra_headers:
        s.headers.update(extra_headers)
    s.proxies.update(PROXIES)
    return s


def probe_html(s, url):
    try:
        r = s.get(url, timeout=(10, 25), verify=False, allow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.string.strip() if soup.title else "?"
        cards = (
            soup.select("[class*='procedure']") or
            soup.select("[class*='tender']") or
            soup.select("[class*='lot']") or
            soup.select("article") or
            soup.select(".card")
        )
        print(f"[{r.status_code}] {url}")
        print(f"  title={title!r}  len={len(r.text)}  cards={len(cards)}")
        if cards:
            print("  first card:", cards[0].get_text(" ", strip=True)[:200])
        return r, soup
    except Exception as e:
        print(f"[ERR] {url}: {e}")
        return None, None


def probe_api(s, url):
    try:
        r = s.get(url, timeout=(10, 25), verify=False, allow_redirects=True)
        print(f"[{r.status_code}] {url}  content-type={r.headers.get('content-type','?')!r}")
        ct = r.headers.get("content-type", "")
        if "json" in ct:
            try:
                d = r.json()
                print("  JSON keys:", list(d.keys()) if isinstance(d, dict) else f"list len={len(d)}")
                if isinstance(d, dict):
                    print("  ", json.dumps(d, ensure_ascii=False)[:300])
                elif isinstance(d, list) and d:
                    print("  first:", json.dumps(d[0], ensure_ascii=False)[:300])
            except Exception as e:
                print(f"  JSON parse err: {e}")
        else:
            print("  body[:200]:", r.text[:200].replace("\n", " "))
        return r
    except Exception as e:
        print(f"[ERR] {url}: {e}")
        return None


# 1. IP check
print("=== IP через прокси ===")
try:
    s = make_session()
    r = s.get("http://httpbin.org/ip", timeout=(8, 8))
    print(f"IP: {r.json()['origin']}")
except Exception as e:
    print(f"ERR: {e}")

KW = "семена"

# 2. HTML search pages
print("\n=== HTML search pages ===")
s = make_session()
for url in [
    f"https://www.roseltorg.ru/procedures/search",
    f"https://www.roseltorg.ru/procedures/search?query={KW}",
    f"https://www.roseltorg.ru/procedures/search?q={KW}",
    f"https://www.roseltorg.ru/search/com?query={KW}",
    f"https://www.roseltorg.ru/search/com?q={KW}",
    f"https://www.roseltorg.ru/search/44fz?query={KW}",
    f"https://corp.roseltorg.ru/",
    f"https://business.roseltorg.ru/",
]:
    probe_html(s, url)
    print()

# 3. business.roseltorg.ru API
print("=== business.roseltorg.ru API ===")
s_api = make_session({"Accept": "application/json"})
for url in [
    f"https://business.roseltorg.ru/api/v1/procedures?q={KW}",
    f"https://business.roseltorg.ru/api/v1/procedures?query={KW}",
    f"https://business.roseltorg.ru/api/v1/procedures?text={KW}",
    f"https://business.roseltorg.ru/api/v1/procedures?keyword={KW}",
    f"https://business.roseltorg.ru/api/v1/procedures?search={KW}",
    f"https://business.roseltorg.ru/api/v1/procedures",
    f"https://business.roseltorg.ru/api/v1/documents?q={KW}",
    f"https://business.roseltorg.ru/api/v1/lots?q={KW}",
    f"https://business.roseltorg.ru/api/v1/search?q={KW}",
    f"https://business.roseltorg.ru/api/v1/",
]:
    probe_api(s_api, url)
    print()

# 4. Check main roseltorg.ru/procedures/search form structure
print("=== Form structure: /procedures/search ===")
r, soup = probe_html(s, "https://www.roseltorg.ru/procedures/search")
if soup:
    print("\n--- Формы ---")
    for form in soup.find_all("form"):
        print(f"  action={form.get('action')!r} method={form.get('method')!r}")
        for inp in form.find_all(["input", "select", "textarea"]):
            name = inp.get("name", "")
            if name:
                print(f"    {inp.name} name={name!r} type={inp.get('type')!r} value={inp.get('value','')!r}")
    print("\n--- Все классы (уникальные, первые 50) ---")
    classes = set()
    for tag in soup.find_all(True):
        for c in (tag.get("class") or []):
            classes.add(c)
    for c in sorted(classes)[:50]:
        print(f"  .{c}")
# trigger
