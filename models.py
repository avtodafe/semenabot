from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)


class Base(DeclarativeBase):
    pass


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_num = Column(String(100), unique=True, index=True)
    title = Column(String(1000))
    customer = Column(String(500))
    inn = Column(String(20))
    price = Column(Float)
    deadline = Column(String(30))
    publish_date = Column(String(30))
    url = Column(String(1000))
    source = Column(String(20))          # "gos" | "sber"
    sent = Column(Boolean, default=False)
    dedup_hash = Column(String(64), index=True)
    duplicate_source = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SeenHash(Base):
    __tablename__ = "seen_hashes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hash_value = Column(String(64), unique=True, index=True)
    primary_source = Column(String(20))
    duplicate_source = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables and clean up hashes older than 30 days."""
    Base.metadata.create_all(engine)
    cutoff = datetime.utcnow() - timedelta(days=30)
    with Session(engine) as session:
        session.execute(
            text("DELETE FROM seen_hashes WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        session.commit()


def save_tenders(tenders: list[dict]) -> int:
    """Persist new tenders to DB. Returns count of newly saved records."""
    saved = 0
    with Session(engine) as session:
        for t in tenders:
            if session.query(Tender).filter_by(reg_num=t["reg_num"]).first():
                continue
            fields = {k: v for k, v in t.items() if k != "id" and hasattr(Tender, k)}
            session.add(Tender(**fields))
            saved += 1
        session.commit()
    return saved


def get_unsent_tenders() -> list[dict]:
    """Return all unsent tenders ordered by price descending."""
    with Session(engine) as session:
        rows = (
            session.query(Tender)
            .filter_by(sent=False)
            .order_by(Tender.price.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "title": r.title,
                "customer": r.customer,
                "price": r.price,
                "deadline": r.deadline,
                "url": r.url,
                "source": r.source,
            }
            for r in rows
        ]


def mark_as_sent(ids: list[int]) -> None:
    with Session(engine) as session:
        session.query(Tender).filter(Tender.id.in_(ids)).update(
            {"sent": True}, synchronize_session=False
        )
        session.commit()
