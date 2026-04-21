#!/usr/bin/env python3
"""
One-off: удаляем несохранённые тендеры, парсим только roseltorg,
применяем новые фильтры, отправляем в Telegram.
"""
import atexit
import base64
import json
import logging
import os
import subprocess
import sys
from datetime import datetime

_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parse.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(_LOG, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def _upload_log() -> None:
    token = os.environ.get("GH_PAT", "")
    if not token:
        return
    try:
        logging.shutdown()
        with open(_LOG, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        api = "https://api.github.com/repos/avtodafe/semenabot/contents/roseltorg_run_output.txt"
        branch = "claude/seed-parser-bot-qO5Mo"
        r = subprocess.run(
            ["curl", "-s", "-H", f"Authorization: token {token}", f"{api}?ref={branch}"],
            capture_output=True, text=True, timeout=15,
        )
        try:
            sha = json.loads(r.stdout).get("sha", "")
        except Exception:
            sha = ""
        body: dict = {
            "message": f"auto: roseltorg run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": content,
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        r2 = subprocess.run(
            ["curl", "-s", "-X", "PUT",
             "-H", f"Authorization: token {token}",
             "-H", "Content-Type: application/json",
             api, "-d", json.dumps(body)],
            capture_output=True, text=True, timeout=20,
        )
        resp = json.loads(r2.stdout)
        cs = resp.get("commit", {}).get("sha", "")
        print("Log upload:", cs[:12] if cs else resp.get("message", "ERR"), flush=True)
    except Exception as e:
        print("Log upload failed:", e, flush=True)


atexit.register(_upload_log)

import requests
from sqlalchemy.orm import Session

from models import SeenHash, Tender, engine, init_db, get_unsent_tenders, mark_as_sent, save_tenders
from parser_sites import SEARCH_TERMS, _fetch_roseltorg
from filters import filter_tenders
from dedup import deduplicate
from bot import send_daily_report

init_db()

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
s = requests.Session()  # dummy — _fetch_roseltorg создаёт свою сессию с прокси
all_raw = []
for kw in SEARCH_TERMS:
    results = _fetch_roseltorg(s, kw)
    if results:
        all_raw.extend(results)
        logger.info("  '%s' → %d результатов", kw, len(results))
    else:
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
