"""Global post-fetch relevance filter applied to all parsers in parse.py."""
from __future__ import annotations

import logging

from config import EXCLUDE_KEYWORDS, REQUIRE_KEYWORDS

logger = logging.getLogger(__name__)


def is_relevant(title: str) -> bool:
    tl = title.lower()
    if not any(kw in tl for kw in REQUIRE_KEYWORDS):
        return False
    if any(kw in tl for kw in EXCLUDE_KEYWORDS):
        return False
    return True


def filter_tenders(tenders: list[dict]) -> list[dict]:
    kept, dropped = [], []
    for t in tenders:
        if is_relevant(t.get("title", "")):
            kept.append(t)
        else:
            dropped.append(t.get("title", "")[:60])
    if dropped:
        logger.info("Filtered out %d irrelevant tenders: %s", len(dropped), dropped[:10])
    return kept
