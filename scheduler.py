#!/usr/bin/env python3
"""
scheduler.py — альтернатива системному cron (для Windows / Mac / VPS без cron).

Запуск: python scheduler.py
  08:00 МСК — parse.py (парсинг площадок)
  10:00 МСК — send.py  (отправка в Telegram)
"""
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

TZ = "Europe/Moscow"


def run_parse() -> None:
    from parse import main
    main()


def run_send() -> None:
    from send import main
    main()


scheduler = BlockingScheduler(timezone=TZ)
scheduler.add_job(run_parse, CronTrigger(hour=8, minute=0, timezone=TZ), id="parse")
scheduler.add_job(run_send, CronTrigger(hour=10, minute=0, timezone=TZ), id="send")

if __name__ == "__main__":
    logger.info("Scheduler running (Europe/Moscow):")
    logger.info("  08:00 — parse.py")
    logger.info("  10:00 — send.py")
    logger.info("Press Ctrl+C to stop")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
