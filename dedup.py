"""
Deduplication module.

Algorithm:
  hash = SHA-256(ИНН_or_customer[:30] | price_rounded_to_1000 | title[:60])

If hash is already in seen_hashes (DB) — skip tender, update duplicate_source.
TTL for hashes: 30 days (cleaned up in models.init_db).
"""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy.orm import Session

from models import SeenHash, engine

logger = logging.getLogger(__name__)


def _compute_hash(tender: dict) -> str:
    inn = (tender.get("inn") or "").strip()
    if not inn:
        inn = (tender.get("customer") or "")[:30].strip()
    price_rounded = round((tender.get("price") or 0) / 1000) * 1000
    title_prefix = (tender.get("title") or "")[:60].strip()
    raw = f"{inn}|{price_rounded}|{title_prefix}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def deduplicate(tenders: list[dict]) -> list[dict]:
    """
    Remove cross-source duplicates from a mixed list of tenders.

    - Same tender on two platforms → keep first, note duplicate_source on it.
    - Returns enriched list (dedup_hash added to each tender dict).
    """
    seen_in_batch: dict[str, dict] = {}   # hash → tender already accepted
    result: list[dict] = []

    with Session(engine) as session:
        for tender in tenders:
            h = _compute_hash(tender)
            tender["dedup_hash"] = h

            # 1. Check within current batch
            if h in seen_in_batch:
                original = seen_in_batch[h]
                if not original.get("duplicate_source"):
                    original["duplicate_source"] = tender["source"]
                logger.info(
                    "Batch duplicate: [%s] '%s'",
                    tender["source"],
                    (tender.get("title") or "")[:50],
                )
                continue

            # 2. Check DB (previous runs)
            db_hash = session.query(SeenHash).filter_by(hash_value=h).first()
            if db_hash:
                if not db_hash.duplicate_source:
                    db_hash.duplicate_source = tender["source"]
                    session.commit()
                logger.info(
                    "DB duplicate: [%s] '%s'",
                    tender["source"],
                    (tender.get("title") or "")[:50],
                )
                continue

            # 3. New — accept and record
            seen_in_batch[h] = tender
            session.add(SeenHash(hash_value=h, primary_source=tender["source"]))
            result.append(tender)

        session.commit()

    logger.info("Dedup: %d raw → %d unique", len(tenders), len(result))
    return result
