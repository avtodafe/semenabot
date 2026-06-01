"""
parser_sites.py — парсеры дополнительных торговых площадок.

Площадки: РТС-тендер, Росэлторг, B2B-Center, OTC.ru, Фабрикант,
ТЭК-Торг, ЭТП ГПБ, ЭТП ЕТС, ЭТП ММВБ, АГЗРТ, Lot-online, ЭТП ГОЗ,
Закупки360, Bicotender, Rostender, Контур.Закупки, Trade.su
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

import warnings

from config import EXCLUDE_KEYWORDS, MIN_PRICE, ROSELTORG_PROXY

logger = logging.getLogger(__name__)

# Укороченный набор поисковых терминов (8 вместо 24 — разумный баланс)
SEARCH_TERMS = [
    "семена овощных",
    "семена кормовых трав",
    "семена клевер",
    "семена люцерн",
    "семена тимофеевка",
    "газонные семена",
    "семена газонных",
    "посевной материал",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

REQUEST_PAUSE = 0.5


# ---------------------------------------------------------------------------
# Общие утилиты
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> float:
    cleaned = re.sub(r"[^\d,.]", "", text.replace("\xa0", "").replace(" ", ""))
    try:
        return float(cleaned.replace(",", "."))
    except ValueError:
        return 0.0


def _is_excluded(title: str) -> bool:
    tl = title.lower()
    return any(kw.lower() in tl for kw in EXCLUDE_KEYWORDS)


def _yesterday_ru() -> str:
    return (date.today() - timedelta(days=1)).strftime("%d.%m.%Y")


def _yesterday_iso() -> str:
    return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get(session: requests.Session, url: str, params: dict | None = None) -> BeautifulSoup | None:
    try:
        r = session.get(url, params=params, timeout=8)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        logger.warning("GET %s — %s", url, e)
        return None


def _tender(*, reg_num: str, title: str, customer: str = "", inn: str = "",
            price: float = 0.0, deadline: str = "", publish_date: str = "",
            url: str = "", source: str) -> dict | None:
    if not title or _is_excluded(title):
        return None
    if price > 0 and price < MIN_PRICE:   # известная цена ниже порога
        return None
    return {
        "reg_num": reg_num or f"{source}-{hashlib.md5((title + str(price)).encode()).hexdigest()[:16]}",
        "title": title.strip(),
        "customer": customer.strip(),
        "inn": inn.strip(),
        "price": price,
        "deadline": deadline.strip(),
        "publish_date": publish_date.strip(),
        "url": url,
        "source": source,
    }


def _id_from_url(href: str, prefix: str) -> str:
    m = re.search(r"[/?&]id=(\d+)|[/-](\d{5,})(?:[/?#]|$)", href)
    if m:
        return f"{prefix}-{m.group(1) or m.group(2)}"
    return ""


# ---------------------------------------------------------------------------
# РТС-тендер  rts-tender.ru
# ---------------------------------------------------------------------------
def _fetch_rts(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://www.rts-tender.ru/tender/search", {
        "text": kw, "priceFrom": MIN_PRICE, "dateFrom": _yesterday_ru(),
    })
    if not soup:
        return None
    out = []
    for row in soup.select(".search-result__item, .tender-row, tr.search-item"):
        a = row.select_one("a.search-result__name, a.tender-name, td.subject a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.rts-tender.ru" + href
        price_el = row.select_one(".search-result__price, .price, td.price")
        customer_el = row.select_one(".search-result__customer, .customer, td.customer")
        deadline_el = row.select_one(".search-result__date, .deadline, td.deadline")
        t = _tender(
            reg_num=_id_from_url(href, "RTS"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="rts",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Росэлторг  roseltorg.ru
# ---------------------------------------------------------------------------
def _make_roseltorg_session() -> requests.Session:
    """Session with Russian proxy — roseltorg.ru is TLS-blocked outside Russia."""
    s = requests.Session()
    s.headers.update({
        **HEADERS,
        "Referer": "https://www.roseltorg.ru/procedures/search",
        "X-Requested-With": "XMLHttpRequest",
    })
    if ROSELTORG_PROXY:
        s.proxies.update({"http": ROSELTORG_PROXY, "https": ROSELTORG_PROXY})
    return s


def _fetch_roseltorg(s: requests.Session, kw: str) -> list[dict] | None:
    rs = _make_roseltorg_session()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = rs.get(
                "https://www.roseltorg.ru/procedures/search_ajax",
                params={
                    "query_field": kw,
                    "status[]": ["0", "1", "2"],
                },
                timeout=(10, 30),
                verify=False,
            )
            r.raise_for_status()
    except Exception as e:
        logger.warning("roseltorg GET — %s", e)
        return None

    soup = BeautifulSoup(r.text, "lxml")
    out = []
    for item in soup.select(".search-results__item"):
        section_el = item.select_one(".search-results__section p")
        section = (section_el.get("title") or section_el.get_text(strip=True)) if section_el else ""
        # Skip FZ-44/FZ-223 — already covered by zakupki.gov.ru parser
        if "44-ФЗ" in section or "223-ФЗ" in section:
            continue

        title_a = item.select_one(".search-results__link--description")
        if not title_a:
            continue
        href = title_a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.roseltorg.ru" + href

        proc_num = item.get("data-feature-favorite-lots-procedure-number", "") or _id_from_url(href, "RELT")

        customer_a = item.select_one(".search-results__customer a")
        customer = customer_a.get_text(strip=True) if customer_a else ""

        price_el = (
            item.select_one(".search-results__currency") or
            item.select_one(".lot-item__nmc")
        )
        price = _parse_price(price_el.get_text(" ", strip=True)) if price_el else 0.0

        right = item.select_one(".search-results__data-col--right")
        deadline = right.get_text(" ", strip=True) if right else ""

        t = _tender(
            reg_num=f"RELT-{proc_num}" if proc_num else "",
            title=title_a.get_text(strip=True),
            customer=customer,
            price=price,
            deadline=deadline,
            url=href,
            source="roseltorg",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# B2B-Center  b2b-center.ru
# ---------------------------------------------------------------------------
def _fetch_b2b(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://www.b2b-center.ru/market/search/", {
        "q": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".lot-list__item, .search-result, .trade-item"):
        a = item.select_one("a.lot-list__title, a.trade-title, .item-title a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.b2b-center.ru" + href
        price_el = item.select_one(".lot-list__price, .price, .start-price")
        customer_el = item.select_one(".lot-list__org, .customer, .organizer")
        deadline_el = item.select_one(".lot-list__date, .deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "B2B"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="b2b",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# OTC.ru
# ---------------------------------------------------------------------------
def _fetch_otc(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://otc.ru/tenders", {
        "search": kw, "price_from": MIN_PRICE, "date_from": _yesterday_iso(),
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".tender-list__item, .tender-card, .search-result__item"):
        a = item.select_one("a.tender-name, a.tender-title, .tender-subject a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://otc.ru" + href
        price_el = item.select_one(".tender-price, .price, .start-price")
        customer_el = item.select_one(".tender-customer, .customer, .organizer-name")
        deadline_el = item.select_one(".tender-deadline, .deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "OTC"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="otc",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Фабрикант  fabrikant.ru
# ---------------------------------------------------------------------------
def _fetch_fabrikant(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://www.fabrikant.ru/trades/search/", {
        "q": kw, "price_from": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".trade-item, .search-item, .lot-row"):
        a = item.select_one("a.trade-name, a.lot-name, .item-title a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.fabrikant.ru" + href
        price_el = item.select_one(".trade-price, .start-price, .price")
        customer_el = item.select_one(".trade-org, .organizer, .customer")
        deadline_el = item.select_one(".trade-deadline, .end-date, .deadline")
        t = _tender(
            reg_num=_id_from_url(href, "FAB"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="fabrikant",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# ТЭК-Торг  tektorg.ru
# ---------------------------------------------------------------------------
def _fetch_tektorg(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://www.tektorg.ru/procedures", {
        "search": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".procedure-item, .tender-item, .lot-item"):
        a = item.select_one("a.procedure-name, a.tender-name, h3 a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.tektorg.ru" + href
        price_el = item.select_one(".procedure-price, .start-price, .price")
        customer_el = item.select_one(".procedure-org, .customer, .organizer")
        deadline_el = item.select_one(".procedure-deadline, .deadline, .date-end")
        t = _tender(
            reg_num=_id_from_url(href, "TEK"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="tektorg",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# ЭТП ГПБ  etpgpb.ru
# ---------------------------------------------------------------------------
def _fetch_etpgpb(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://etpgpb.ru/procedures/list", {
        "search": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".procedure-item, .tender-row, .search-item"):
        a = item.select_one("a.procedure-title, a.tender-name, .item-name a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://etpgpb.ru" + href
        price_el = item.select_one(".price, .start-price, .nmc")
        customer_el = item.select_one(".customer, .organizer, .org-name")
        deadline_el = item.select_one(".deadline, .date-end, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "GPB"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="etpgpb",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# ЭТП ЕТС  etp-ets.ru
# ---------------------------------------------------------------------------
def _fetch_etpets(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://www.etp-ets.ru/tenders", {
        "search": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".tender-item, .lot-item, .search-result"):
        a = item.select_one("a.tender-name, a.lot-name, .subject a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.etp-ets.ru" + href
        price_el = item.select_one(".price, .start-price")
        customer_el = item.select_one(".customer, .organizer")
        deadline_el = item.select_one(".deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "ETS"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="etpets",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# ЭТП ММВБ  etp-micex.ru
# ---------------------------------------------------------------------------
def _fetch_etpmicex(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://www.etp-micex.ru/tenders", {
        "q": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".tender-item, .lot-item"):
        a = item.select_one("a.tender-name, a.lot-name, h3 a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.etp-micex.ru" + href
        price_el = item.select_one(".price, .start-price")
        customer_el = item.select_one(".customer, .organizer")
        deadline_el = item.select_one(".deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "MCX"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="etpmicex",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# АГЗРТ  agzrt.ru
# ---------------------------------------------------------------------------
def _fetch_agzrt(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://agzrt.ru/tenders", {
        "q": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".tender-item, .lot-item, tr.tender"):
        a = item.select_one("a.tender-name, a.lot-name, td.name a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://agzrt.ru" + href
        price_el = item.select_one(".price, .start-price, td.price")
        customer_el = item.select_one(".customer, td.customer, .organizer")
        deadline_el = item.select_one(".deadline, td.deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "AGZRT"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="agzrt",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Lot-online  lot-online.ru
# ---------------------------------------------------------------------------
def _fetch_lotonline(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://lot-online.ru/auctions", {
        "search": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".auction-item, .lot-item, .tender-item"):
        a = item.select_one("a.auction-name, a.lot-name, a.tender-name, h3 a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://lot-online.ru" + href
        price_el = item.select_one(".price, .start-price, .initial-price")
        customer_el = item.select_one(".customer, .organizer, .seller")
        deadline_el = item.select_one(".deadline, .end-date, .date-end")
        t = _tender(
            reg_num=_id_from_url(href, "LOT"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="lotonline",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# ЭТП ГОЗ  etpgoz.ru
# ---------------------------------------------------------------------------
def _fetch_etpgoz(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://www.etpgoz.ru/tenders", {
        "search": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".tender-item, .lot-item"):
        a = item.select_one("a.tender-name, a.lot-name, h3 a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.etpgoz.ru" + href
        price_el = item.select_one(".price, .start-price")
        customer_el = item.select_one(".customer, .organizer")
        deadline_el = item.select_one(".deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "ETPGOZ"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="etpgoz",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Закупки360  zakupki360.ru  (агрегатор)
# ---------------------------------------------------------------------------
def _fetch_zakupki360(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://zakupki360.ru/purchases", {
        "q": kw, "priceFrom": MIN_PRICE, "dateFrom": _yesterday_iso(),
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".purchase-item, .tender-item, .search-item"):
        a = item.select_one("a.purchase-title, a.tender-name, .item-title a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://zakupki360.ru" + href
        price_el = item.select_one(".purchase-price, .price, .start-price")
        customer_el = item.select_one(".purchase-customer, .customer, .organizer")
        deadline_el = item.select_one(".purchase-deadline, .deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "Z360"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="zakupki360",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Bicotender  bicotender.ru  (агрегатор)
# ---------------------------------------------------------------------------
def _fetch_bicotender(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://bicotender.ru/search/", {
        "q": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".tender-item, .search-result, .lot-block"):
        a = item.select_one("a.tender-title, a.lot-title, .tender-name a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://bicotender.ru" + href
        price_el = item.select_one(".tender-price, .price, .start-price")
        customer_el = item.select_one(".tender-customer, .customer, .organizer")
        deadline_el = item.select_one(".tender-deadline, .deadline, .end-date")
        t = _tender(
            reg_num=_id_from_url(href, "BICO"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="bicotender",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Rostender.info  (агрегатор)
# ---------------------------------------------------------------------------
def _fetch_rostender(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://rostender.info/tender/search", {
        "q": kw, "price_from": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".tender-item, .search-result, .result-item"):
        a = item.select_one("a.tender-name, a.result-title, .subject a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://rostender.info" + href
        price_el = item.select_one(".price, .start-price, .tender-price")
        customer_el = item.select_one(".customer, .organizer, .tender-customer")
        deadline_el = item.select_one(".deadline, .end-date, .tender-deadline")
        t = _tender(
            reg_num=_id_from_url(href, "RST"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="rostender",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Контур.Закупки  zakupki.kontur.ru  (агрегатор)
# ---------------------------------------------------------------------------
def _fetch_kontur(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://zakupki.kontur.ru/search", {
        "q": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".search-result__item, .tender-row, .purchase-item"):
        a = item.select_one("a.search-result__title, a.purchase-name, .tender-subject a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://zakupki.kontur.ru" + href
        price_el = item.select_one(".price, .start-price, .search-result__price")
        customer_el = item.select_one(".customer, .organizer, .search-result__customer")
        deadline_el = item.select_one(".deadline, .end-date, .search-result__date")
        t = _tender(
            reg_num=_id_from_url(href, "KNT"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="kontur",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Trade.su
# ---------------------------------------------------------------------------
def _fetch_trade(s: requests.Session, kw: str) -> list[dict] | None:
    soup = _get(s, "https://trade.su/search", {
        "q": kw, "priceFrom": MIN_PRICE,
    })
    if not soup:
        return None
    out = []
    for item in soup.select(".trade-item, .lot-item, .search-result"):
        a = item.select_one("a.trade-name, a.lot-name, .item-title a")
        if not a:
            continue
        href = a.get("href", "")
        if href and not href.startswith("http"):
            href = "https://trade.su" + href
        price_el = item.select_one(".price, .start-price, .trade-price")
        customer_el = item.select_one(".customer, .organizer, .trade-org")
        deadline_el = item.select_one(".deadline, .end-date, .trade-deadline")
        t = _tender(
            reg_num=_id_from_url(href, "TRADE"),
            title=a.get_text(strip=True),
            customer=customer_el.get_text(strip=True) if customer_el else "",
            price=_parse_price(price_el.get_text(strip=True)) if price_el else 0.0,
            deadline=deadline_el.get_text(strip=True) if deadline_el else "",
            url=href, source="trade",
        )
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Реестр площадок
# ---------------------------------------------------------------------------

# Only Roseltorg is enabled — it has a working custom fetcher.
# The other 16 sites used guessed CSS selectors that never matched,
# downloading full HTML pages (200-500 KB each) for every keyword
# and returning zero results — causing ~750 MB/month of wasted traffic.
SITE_FETCHERS: list[tuple[str, callable]] = [
    ("Росэлторг",        _fetch_roseltorg),
]


def fetch_all_tenders() -> list[dict]:
    """Запустить парсинг всех дополнительных площадок."""
    seen: set[str] = set()
    result: list[dict] = []

    with _make_session() as session:
        for site_name, fetcher in SITE_FETCHERS:
            site_count = 0
            site_failed = False
            for i, kw in enumerate(SEARCH_TERMS):
                logger.info("%s: '%s'", site_name, kw)
                try:
                    entries = fetcher(session, kw)
                    # Если первый запрос вернул None (сайт недоступен) — пропускаем сайт
                    if entries is None and i == 0:
                        logger.warning("%s: недоступен, пропускаем", site_name)
                        site_failed = True
                        break
                    for entry in (entries or []):
                        rn = entry["reg_num"]
                        if rn not in seen:
                            seen.add(rn)
                            result.append(entry)
                            site_count += 1
                except Exception as e:
                    logger.error("%s error '%s': %s", site_name, kw, e)
                    if i == 0:
                        logger.warning("%s: первый запрос упал, пропускаем сайт", site_name)
                        site_failed = True
                        break
                time.sleep(REQUEST_PAUSE)
            if not site_failed:
                logger.info("%s: итого %d тендеров", site_name, site_count)

    logger.info("Все доп. площадки: %d уникальных тендеров", len(result))
    return result
