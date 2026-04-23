#!/usr/bin/env python3
"""
One-off: удаляем несохранённые тендеры, парсим только roseltorg,
применяем новые фильтры, отправляем в Telegram.
"""
import logging
import os
import sys

_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parse.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(_LOG, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

import requests
from sqlalchemy.orm import Session

from config import BOT_TOKEN, CHANNEL_ID
from models import SeenHash, Tender, engine, init_db, get_unsent_tenders, mark_as_sent, save_tenders
from parser_sites import SEARCH_TERMS, _fetch_roseltorg
from filters import filter_tenders
from dedup import deduplicate
from bot import send_daily_report

init_db()


def _tg(text: str) -> None:
    """Send plain text to Telegram channel (diagnostic helper)."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHANNEL_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        logger.warning("_tg failed: %s", e)


# 1. Удаляем все неотправленные тендеры и их хеши (мусор от старого парсинга)
with Session(engine) as session:
    unsent = session.query(Tender).filter_by(sent=False).all()
    hashes = [t.dedup_hash for t in unsent if t.dedup_hash]
    count = session.query(Tender).filter_by(sent=False).delete(synchronize_session=False)
    if hashes:
        session.query(SeenHash).filter(SeenHash.hash_value.in_(hashes)).delete(
            synchronize_session=False
        )
    session.commit()
    logger.info("Очищено %d несохранённых тендеров и %d хешей", count, len(hashes))

# 2. Парсим только roseltorg
logger.info("Запуск парсинга roseltorg...")
s = requests.Session()
all_raw: list[dict] = []
kw_results: list[str] = []
for kw in SEARCH_TERMS:
    results = _fetch_roseltorg(s, kw)
    if results:
        all_raw.extend(results)
        kw_results.append(f"  '{kw}' → {len(results)}")
        logger.info("  '%s' → %d результатов", kw, len(results))
    else:
        kw_results.append(f"  '{kw}' → 0")
        logger.warning("  '%s' → нет результатов или ошибка", kw)

logger.info("Всего получено: %d", len(all_raw))

# 3. Фильтрация и дедупликация
filtered = filter_tenders(all_raw)
logger.info("После фильтра: %d", len(filtered))
unique = deduplicate(filtered)
saved = save_tenders(unique)
logger.info("Сохранено новых: %d", saved)

# 4. Отправка в Telegram
tenders = get_unsent_tenders()

# Diagnostic status
_tg(
    "🔍 Roseltorg диагностика:\n"
    f"Получено: {len(all_raw)}, фильтр: {len(filtered)}, новых: {saved}, к отправке: {len(tenders)}\n"
    + "\n".join(kw_results[:12])
)

if not tenders:
    logger.info("Нечего отправлять — тендеров нет")
    sys.exit(0)

logger.info("Отправляем %d тендеров...", len(tenders))
try:
    send_daily_report(tenders)
except Exception as e:
    logger.error("Ошибка отправки: %s", e)
    sys.exit(1)

mark_as_sent([t["id"] for t in tenders])
logger.info("Готово — отправлено %d тендеров", len(tenders))
