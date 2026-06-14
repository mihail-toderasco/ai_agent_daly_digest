import re

from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func, JSON as JSONType
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import Base


ARXIV_ID_PATTERN = re.compile(
    r"^\d{4}\.\d{4,5}v\d+$"
)


class ArxivEntry(Base):
    __tablename__ = "arxiv_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    arxiv_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    categories: Mapped[str] = mapped_column(Text)
    published: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    link: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONType)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    @validates("arxiv_id")
    def validate_arxiv_id(
        self,
        key: str,
        value: str,
    ) -> str:
        if not ARXIV_ID_PATTERN.fullmatch(value):
            raise ValueError(
                f"Invalid arxiv_id: {value}"
            )

        return value
