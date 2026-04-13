"""
parser_sber.py — парсер Сбербанк-АСТ

Эндпоинт: https://www.sberbank-ast.ru/purchaseList.aspx
Метод: GET + HTML → BeautifulSoup
Пауза между запросами 2–3 сек, чтобы не получить бан.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from config import EXCLUDE_KEYWORDS, KEYWORD_GROUPS, MIN_PRICE

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sberbank-ast.ru/purchaseList.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://www.sberbank-ast.ru",
}

REQUEST_PAUSE = 2.5   # seconds between requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> float:
    cleaned = re.sub(r"[^\d,.]", "", text.replace("\xa0", "").replace(" ", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _is_excluded(title: str) -> bool:
    tl = title.lower()
    return any(kw.lower() in tl for kw in EXCLUDE_KEYWORDS)


def _fetch_page(session: requests.Session, keyword: str, page: int = 1) -> BeautifulSoup | None:
    yesterday = (date.today() - timedelta(days=1)).strftime("%d.%m.%Y")
    params = {
        "searchtext": keyword,
        "startPrice": str(MIN_PRICE),
        "publishDateFrom": yesterday,
        "page": str(page),
    }
    try:
        resp = session.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        logger.error("SBER fetch error '%s' page %d: %s", keyword, page, exc)
        return None


def _parse_entries(soup: BeautifulSoup) -> list[dict]:
    entries: list[dict] = []

    # Try several known selector patterns (sberbank-ast.ru may change layout)
    rows = (
        soup.select("table.tableBlock tr.purchaseRow")
        or soup.select("tr[data-id]")
        or soup.select(".purchases-list__item")
        or soup.select(".lot-item")
    )

    if not rows:
        logger.debug("SBER: no rows found (page empty or layout changed)")
        return entries

    for row in rows:
        try:
            # Title + link
            title_el = (
                row.select_one(".purchaseName a")
                or row.select_one("td.subject a")
                or row.select_one("a[href*='purchaseCard']")
                or row.select_one(".lot-item__name a")
            )
            title = title_el.get_text(separator=" ", strip=True) if title_el else ""
            if not title or _is_excluded(title):
                continue

            href = ""
            if title_el and title_el.has_attr("href"):
                href = title_el["href"]
                if href and not href.startswith("http"):
                    href = "https://www.sberbank-ast.ru" + href

            # Price
            price_el = (
                row.select_one(".price")
                or row.select_one("td.price")
                or row.select_one(".startPrice")
            )
            price = _parse_price(price_el.get_text(strip=True)) if price_el else 0.0
            if price < MIN_PRICE:
                continue

            # Customer
            customer_el = (
                row.select_one(".customer a")
                or row.select_one("td.customer")
                or row.select_one(".organizationName")
            )
            customer = customer_el.get_text(strip=True) if customer_el else ""

            # INN
            inn = ""
            inn_el = row.select_one(".inn") or row.select_one("[data-inn]")
            if inn_el:
                raw = inn_el.get("data-inn") or inn_el.get_text(strip=True)
                m = re.search(r"\d{10,12}", raw)
                inn = m.group(0) if m else ""

            # Deadline
            deadline_el = (
                row.select_one(".deadline")
                or row.select_one("td.deadline")
                or row.select_one(".applicationDeadlineDate")
            )
            deadline = deadline_el.get_text(strip=True) if deadline_el else ""

            # Reg number / ID
            reg_num = ""
            id_el = row.select_one("[data-purchase-id]") or row.select_one(".purchaseId")
            if id_el:
                reg_num = id_el.get("data-purchase-id") or id_el.get_text(strip=True)
            if not reg_num and href:
                m = re.search(r"[?&]id=(\d+)", href)
                reg_num = f"SBER-{m.group(1)}" if m else ""
            if not reg_num:
                reg_num = f"SBER-{abs(hash(title + str(price)))}"

            entries.append(
                {
                    "reg_num": reg_num,
                    "title": title,
                    "customer": customer,
                    "inn": inn,
                    "price": price,
                    "deadline": deadline,
                    "publish_date": "",
                    "url": href,
                    "source": "sber",
                }
            )
        except Exception as exc:
            logger.warning("SBER entry parse error: %s", exc)

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_all_tenders() -> list[dict]:
    """Return unique tenders from sberbank-ast.ru for all keyword groups."""
    seen: set[str] = set()
    result: list[dict] = []

    all_keywords = [kw for group in KEYWORD_GROUPS.values() for kw in group]

    with requests.Session() as session:
        for keyword in all_keywords:
            logger.info("SBER: searching '%s'", keyword)
            soup = _fetch_page(session, keyword)
            if soup:
                for entry in _parse_entries(soup):
                    rn = entry["reg_num"]
                    if rn not in seen:
                        seen.add(rn)
                        result.append(entry)
            time.sleep(REQUEST_PAUSE)

    logger.info("SBER: %d unique tenders found", len(result))
    return result
