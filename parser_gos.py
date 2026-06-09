"""
parser_gos.py — парсер zakupki.gov.ru

Эндпоинт: https://zakupki.gov.ru/epz/order/extendedsearch/results.html
Метод: GET + HTML → BeautifulSoup
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from config import EXCLUDE_KEYWORDS, KEYWORD_GROUPS, MIN_PRICE

logger = logging.getLogger(__name__)

BASE_URL = "https://zakupki.gov.ru/epz/order/extendedsearch/results.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://zakupki.gov.ru",
}

REQUEST_PAUSE = 1.5   # seconds between keyword requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_params(keyword: str, page: int = 1) -> dict:
    yesterday = (date.today() - timedelta(days=1)).strftime("%d.%m.%Y")
    return {
        "searchString": keyword,
        "morphology": "on",
        "fz44": "on",
        "fz223": "on",
        "priceFrom": str(MIN_PRICE),
        "publishDateFrom": yesterday,
        "sortBy": "UPDATE_DATE",
        "pageNumber": str(page),
        "recordsPerPage": "_50",
        "showLotsInfoHidden": "false",
        "search-filter": "Дата размещения",
    }


def _parse_price(text: str) -> float:
    cleaned = re.sub(r"[^\d,.]", "", text.replace("\xa0", "")).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _is_excluded(title: str) -> bool:
    tl = title.lower()
    return any(kw.lower() in tl for kw in EXCLUDE_KEYWORDS)


def _fetch_page(keyword: str, page: int = 1) -> BeautifulSoup | None:
    params = _build_params(keyword, page)
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        logger.error("GOS fetch error '%s' page %d: %s", keyword, page, exc)
        return None


def _parse_entries(soup: BeautifulSoup) -> list[dict]:
    entries: list[dict] = []

    # zakupki.gov.ru result blocks
    blocks = soup.select(".search-registry-entry-block")
    if not blocks:
        logger.debug("GOS: no blocks found (page may be empty or layout changed)")
        return entries

    for block in blocks:
        try:
            # Title / subject — find the row labelled "Объект закупки";
            # otherwise the OKPD2 categories block (semicolon-separated list)
            # is often returned first by select_one(".registry-entry__body-value").
            title = ""
            for body_block in block.select(".registry-entry__body-block"):
                label_el = body_block.select_one(".registry-entry__body-title")
                if label_el:
                    label = label_el.get_text(strip=True).lower()
                    if "объект" in label or "наименован" in label:
                        val_el = body_block.select_one(".registry-entry__body-value")
                        if val_el:
                            title = val_el.get_text(separator=" ", strip=True)
                            break
            if not title:
                title_el = block.select_one(".registry-entry__body-value")
                title = title_el.get_text(separator=" ", strip=True) if title_el else ""
            if not title or _is_excluded(title):
                continue

            # Registration number + direct link
            num_el = block.select_one(".registry-entry__header-mid__number a")
            reg_num = num_el.get_text(strip=True) if num_el else ""
            href = ""
            if num_el and num_el.has_attr("href"):
                href = num_el["href"]
                if href and not href.startswith("http"):
                    href = "https://zakupki.gov.ru" + href

            # Customer name
            customer_el = block.select_one(".registry-entry__body-href a")
            customer = customer_el.get_text(strip=True) if customer_el else ""

            # INN — usually next to customer name
            inn = ""
            inn_block = block.select_one(".registry-entry__body-href")
            if inn_block:
                raw = inn_block.get_text(" ", strip=True)
                m = re.search(r"ИНН[:\s]+(\d{10,12})", raw)
                inn = m.group(1) if m else ""

            # Price
            price_el = block.select_one(".price-block__value")
            price = _parse_price(price_el.get_text(strip=True)) if price_el else 0.0
            if price > 0 and price < MIN_PRICE:
                continue

            # Dates — find block labelled "Окончание подачи заявок"
            publish_date = ""
            deadline = ""
            for data_block in block.select(".data-block"):
                title_el = data_block.select_one(".data-block__title")
                val_el = data_block.select_one(".data-block__value")
                if not title_el or not val_el:
                    continue
                label = title_el.get_text(strip=True).lower()
                val = val_el.get_text(strip=True)
                if "размещен" in label:
                    publish_date = val
                elif "подач" in label or "окончани" in label:
                    deadline = val
            # Fallback: take first two .data-block__value if labels not found
            if not publish_date and not deadline:
                date_els = block.select(".data-block__value")
                publish_date = date_els[0].get_text(strip=True) if len(date_els) > 0 else ""
                deadline = date_els[1].get_text(strip=True) if len(date_els) > 1 else ""

            entries.append(
                {
                    "reg_num": reg_num or f"GOS-{hashlib.md5((title + str(price)).encode()).hexdigest()[:16]}",
                    "title": title,
                    "customer": customer,
                    "inn": inn,
                    "price": price,
                    "deadline": deadline,
                    "publish_date": publish_date,
                    "url": href,
                    "source": "gos",
                }
            )
        except Exception as exc:
            logger.warning("GOS entry parse error: %s", exc)

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_all_tenders() -> list[dict]:
    """Return unique tenders from zakupki.gov.ru for all keyword groups."""
    seen: set[str] = set()
    result: list[dict] = []

    all_keywords = [kw for group in KEYWORD_GROUPS.values() for kw in group]

    for keyword in all_keywords:
        logger.info("GOS: searching '%s'", keyword)
        soup = _fetch_page(keyword)
        if soup:
            for entry in _parse_entries(soup):
                rn = entry["reg_num"]
                if rn not in seen:
                    seen.add(rn)
                    result.append(entry)
        time.sleep(REQUEST_PAUSE)

    logger.info("GOS: %d unique tenders found", len(result))
    return result
