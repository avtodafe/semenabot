#!/usr/bin/env python3
"""Диагностика roseltorg.ru — поиск правильных URL и структуры HTML."""
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


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.proxies.update(PROXIES)
    return s


def probe(s, url, label=""):
    try:
        r = s.get(url, timeout=(10, 20), verify=False, allow_redirects=True)
        soup = BeautifulSoup(r.text, "lxml")
        title = soup.title.string.strip() if soup.title else "?"
        # count tender-like items
        cards = (
            soup.select(".procedure-card") or
            soup.select(".tender-item") or
            soup.select(".lot-item") or
            soup.select("[class*='procedure']") or
            soup.select("[class*='tender']") or
            soup.select("[class*='lot']") or
            soup.select("article") or
            soup.select(".card")
        )
        print(f"[{r.status_code}] {label or url}")
        print(f"  title: {title!r}")
        print(f"  len={len(r.text)}  cards={len(cards)}")
        print(f"  final_url: {r.url}")
        if r.status_code == 200 and cards:
            print("  --- first card text ---")
            print("  " + cards[0].get_text(" ", strip=True)[:200])
        return r, soup
    except Exception as e:
        print(f"[ERR] {label or url}: {e}")
        return None, None


# 1. IP check
print("=== IP через прокси ===")
try:
    s = make_session()
    r = s.get("http://httpbin.org/ip", timeout=(8, 8))
    print(f"IP: {r.json()['origin']}")
except Exception as e:
    print(f"ERR: {e}")

# 2. Known search URLs with query param variants
print("\n=== Тестируем поисковые URL ===")
KW = "семена"
s = make_session()
candidates = [
    f"https://www.roseltorg.ru/procedures/search?query={KW}",
    f"https://www.roseltorg.ru/procedures/search?q={KW}",
    f"https://www.roseltorg.ru/procedures/search?text={KW}",
    f"https://www.roseltorg.ru/procedures/search?keyword={KW}",
    f"https://www.roseltorg.ru/procedures/search",
    f"https://www.roseltorg.ru/search/com?query={KW}",
    f"https://www.roseltorg.ru/search/com?q={KW}",
    f"https://www.roseltorg.ru/search/com",
    f"https://www.roseltorg.ru/search/44fz?query={KW}",
    f"https://www.roseltorg.ru/business",
    f"https://www.roseltorg.ru/torgi",
]
for url in candidates:
    probe(s, url)
    print()

# 3. Главная страница — ищем форму поиска
print("\n=== Форма поиска на главной ===")
r, soup = probe(s, "https://www.roseltorg.ru/")
if soup:
    print("\n--- Все формы ---")
    for form in soup.find_all("form"):
        print(f"  action={form.get('action')!r} method={form.get('method')!r}")
        for inp in form.find_all(["input", "select", "textarea"]):
            print(f"    {inp.name} name={inp.get('name')!r} type={inp.get('type')!r} placeholder={inp.get('placeholder','')!r}")

    print("\n--- Ссылки в навигации ---")
    for a in soup.select("nav a, .nav a, header a, .header a")[:30]:
        href = a.get("href", "")
        txt = a.get_text(strip=True)[:60]
        if href:
            print(f"  {href!r:55s} {txt!r}")
