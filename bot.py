"""
bot.py — Telegram-рассылка через python-telegram-bot 20.x (async).

Публичный интерфейс:
    send_daily_report(tenders: list[dict]) -> None
"""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import date

from telegram import Bot
from telegram.constants import ParseMode

from config import BOT_TOKEN, CHANNEL_ID

logger = logging.getLogger(__name__)

SEPARATOR = "━" * 19
TG_MAX_LEN = 4096


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _fmt_price(price: float) -> str:
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f} млн ₽"
    return f"{price:,.0f} ₽".replace(",", "\u202f")  # thin non-breaking space


_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def _fmt_tender(idx: int, t: dict) -> str:
    num = _NUMS[idx - 1] if idx <= len(_NUMS) else f"{idx}."
    source_host = "zakupki.gov.ru" if t.get("source") == "gos" else "sberbank-ast.ru"
    url = html.escape(t.get("url") or source_host)
    deadline = html.escape(t.get("deadline") or "—")
    customer = html.escape(t.get("customer") or "—")
    title = html.escape(t.get("title") or "Без названия")

    return (
        f"{num} {title}\n"
        f"🏛 Заказчик: {customer}\n"
        f"💰 Начальная цена: {_fmt_price(t.get('price', 0))}\n"
        f"📅 Дедлайн: {deadline}\n"
        f"🔗 {url}"
    )


def _build_full_message(tenders: list[dict]) -> str:
    today = date.today().strftime("%d.%m.%Y")
    total = sum(t.get("price", 0) for t in tenders)

    header = (
        f"📋 <b>Тендеры на семена — {today}</b>\n"
        f"Найдено: {len(tenders)} новых тендеров\n"
    )
    footer = (
        f"Итого за сегодня: {len(tenders)} тендеров | {_fmt_price(total)}"
    )

    blocks = [_fmt_tender(i, t) for i, t in enumerate(tenders, 1)]
    body = f"\n{SEPARATOR}\n" + f"\n\n".join(blocks) + f"\n{SEPARATOR}\n"

    return header + body + footer


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

async def _send_chunks(bot: Bot, tenders: list[dict]) -> None:
    """Send tenders, splitting into multiple messages if needed."""
    today = date.today().strftime("%d.%m.%Y")
    total = sum(t.get("price", 0) for t in tenders)

    full = _build_full_message(tenders)
    if len(full) <= TG_MAX_LEN:
        await bot.send_message(
            chat_id=CHANNEL_ID, text=full, parse_mode=ParseMode.HTML
        )
        return

    # Header message
    header = (
        f"📋 <b>Тендеры на семена — {today}</b>\n"
        f"Найдено: {len(tenders)} новых тендеров\n"
    )
    await bot.send_message(
        chat_id=CHANNEL_ID, text=header, parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(1)

    # Tender chunks
    chunk_lines: list[str] = [SEPARATOR]
    for i, tender in enumerate(tenders, 1):
        block = _fmt_tender(i, tender)
        candidate = "\n".join(chunk_lines) + f"\n\n{block}"
        if len(candidate) > TG_MAX_LEN - 30:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text="\n".join(chunk_lines) + f"\n{SEPARATOR}",
                parse_mode=ParseMode.HTML,
            )
            await asyncio.sleep(1)
            chunk_lines = [SEPARATOR, block]
        else:
            chunk_lines.append(block)

    # Last chunk + footer
    footer = f"Итого за сегодня: {len(tenders)} тендеров | {_fmt_price(total)}"
    last = "\n".join(chunk_lines) + f"\n{SEPARATOR}\n{footer}"
    await bot.send_message(
        chat_id=CHANNEL_ID, text=last, parse_mode=ParseMode.HTML
    )


async def _run(tenders: list[dict]) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        await _send_chunks(bot, tenders)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def send_daily_report(tenders: list[dict]) -> None:
    """Synchronous wrapper — safe to call from cron scripts."""
    if not tenders:
        logger.info("Nothing to send")
        return
    logger.info("Sending %d tenders to %s", len(tenders), CHANNEL_ID)
    asyncio.run(_run(tenders))
    logger.info("Telegram send complete")
