#!/usr/bin/env python3
"""
send.py — скрипт отправки в Telegram (запускается в 10:00 через cron или scheduler.py).

Cron:
    0 10 * * * /usr/bin/python3 /home/user/semenabot/send.py
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("send.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    from bot import send_daily_report
    from models import get_unsent_tenders, init_db, mark_as_sent

    logger.info("=== Send run started ===")
    init_db()

    tenders = get_unsent_tenders()
    if not tenders:
        logger.info("No new tenders today — nothing to send")
        return

    send_daily_report(tenders)
    mark_as_sent([t["id"] for t in tenders])
    logger.info("=== Send complete: %d tenders sent ===", len(tenders))


if __name__ == "__main__":
    main()
