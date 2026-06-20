from datetime import date, datetime
from sqlalchemy import Integer, String, Text, Date, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .base import Base

class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    digest_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    query: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="completed",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_entry_ids: Mapped[list[int]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "digest_date", 
            "query", 
            name="uq_digest_date_query"
        ),
    )
