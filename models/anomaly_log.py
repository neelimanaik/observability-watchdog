from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class AnomalyLog(Base):
    """One record per source per detection cycle — tracks error rate vs threshold."""

    __tablename__ = "anomaly_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(128), index=True)
    window_count: Mapped[int] = mapped_column(Integer)        # total events in window
    error_count: Mapped[int] = mapped_column(Integer)         # error+critical events
    threshold: Mapped[float] = mapped_column(Float)           # spike threshold applied
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
