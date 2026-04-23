#!/usr/bin/env python3
"""
send.py — скрипт отправки в Telegram (запускается в 10:00 через cron или scheduler.py).

Cron:
    0 10 * * * /usr/bin/python3 /home/user/semenabot/send.py
"""
import logging
import os
import sys

_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "send.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(_LOG, encoding="utf-8")],
)

logger = logging.getLogger(__name__)


def _tg(text: str) -> None:
    try:
        import requests as _req
        from config import BOT_TOKEN, CHANNEL_ID
        _req.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHANNEL_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        logger.warning("_tg failed: %s", e)


def main() -> None:
    from bot import send_daily_report
    from models import get_unsent_tenders, init_db, mark_as_sent

    logger.info("=== Send run started ===")
    init_db()

    tenders = get_unsent_tenders()
    if not tenders:
        logger.info("No new tenders today — nothing to send")
        _tg("✅ Бот отработал — новых подходящих тендеров сегодня нет.")
        return

    try:
        send_daily_report(tenders)
    except Exception as exc:
        logger.error("send_daily_report failed: %s", exc)
        sys.exit(1)
    mark_as_sent([t["id"] for t in tenders])
    logger.info("=== Send complete: %d tenders sent ===", len(tenders))


if __name__ == "__main__":
    main()
