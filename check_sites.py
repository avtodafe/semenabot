#!/usr/bin/env python3
"""Проверка доступности всех площадок с текущего IP."""
import requests

SITES = [
    ("zakupki.gov.ru",  "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=семена&fz44=on"),
    ("rts-tender.ru",   "https://www.rts-tender.ru/tender/search?text=семена"),
    ("roseltorg.ru",    "https://www.roseltorg.ru/search/?query=семена"),
    ("b2b-center.ru",   "https://www.b2b-center.ru/market/search/?q=семена"),
    ("otc.ru",          "https://otc.ru/tenders?search=семена"),
    ("fabrikant.ru",    "https://www.fabrikant.ru/trades/search/?q=семена"),
    ("tektorg.ru",      "https://www.tektorg.ru/procedures?search=семена"),
    ("etpgpb.ru",       "https://etpgpb.ru/procedures/list?search=семена"),
    ("etp-ets.ru",      "https://www.etp-ets.ru/tenders?search=семена"),
    ("etp-micex.ru",    "https://www.etp-micex.ru/tenders?q=семена"),
    ("agzrt.ru",        "https://agzrt.ru/tenders?q=семена"),
    ("lot-online.ru",   "https://lot-online.ru/auctions?search=семена"),
    ("etpgoz.ru",       "https://www.etpgoz.ru/tenders?search=семена"),
    ("zakupki360.ru",   "https://zakupki360.ru/purchases?q=семена"),
    ("bicotender.ru",   "https://bicotender.ru/search/?q=семена"),
    ("rostender.info",  "https://rostender.info/tender/search?q=семена"),
    ("kontur.ru",       "https://zakupki.kontur.ru/search?q=семена"),
    ("trade.su",        "https://trade.su/search?q=семена"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

ok, blocked = [], []

for name, url in SITES:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        status = r.status_code
        if status == 200:
            ok.append((name, status))
            print(f"✅ {name:<25} {status}")
        else:
            blocked.append((name, status))
            print(f"❌ {name:<25} {status}")
    except requests.Timeout:
        blocked.append((name, "timeout"))
        print(f"⏱  {name:<25} timeout")
    except Exception as e:
        blocked.append((name, str(e)[:40]))
        print(f"💥 {name:<25} {str(e)[:40]}")

print(f"\nИтого: {len(ok)} доступны, {len(blocked)} заблокированы")
