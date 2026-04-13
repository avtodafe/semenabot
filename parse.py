#!/usr/bin/env python3
"""
parse.py — скрипт парсинга (запускается в 08:00 через cron или scheduler.py).

Cron:
    0 8 * * * /usr/bin/python3 /home/user/semenabot/parse.py
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("parse.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> int:
    from dedup import deduplicate
    from models import init_db, save_tenders
    from parser_gos import fetch_all_tenders as fetch_gos
    from parser_sber import fetch_all_tenders as fetch_sber

    logger.info("=== Parse run started ===")
    init_db()

    gos = fetch_gos()
    sber = fetch_sber()
    all_tenders = gos + sber
    logger.info(
        "Fetched total %d (GOS: %d | SBER: %d)", len(all_tenders), len(gos), len(sber)
    )

    unique = deduplicate(all_tenders)
    saved = save_tenders(unique)
    logger.info("=== Parse complete: %d new tenders saved ===", saved)
    return saved


if __name__ == "__main__":
    main()
