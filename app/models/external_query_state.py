from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class ExternalQueryState(Base):
    __tablename__ = "external_query_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    source: Mapped[str] = mapped_column(String(50), nullable=False)
    query: Mapped[str] = mapped_column(String(255), nullable=False)

    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    last_success_count: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
