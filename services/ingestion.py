import json
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from models.event import Event


VALID_LEVELS = {"info", "warn", "error", "critical"}


class EventIn(BaseModel):
    source: str
    level: str
    message: str
    value: float | None = None
    tags: dict | None = None
    timestamp: datetime | None = None

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        v = v.lower()
        if v not in VALID_LEVELS:
            raise ValueError(f"level must be one of {VALID_LEVELS}")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source cannot be empty")
        return v.strip()[:128]


class EventOut(BaseModel):
    id: int
    source: str
    level: str
    message: str
    value: float | None
    tags: dict | None
    timestamp: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_event(cls, ev: Event) -> "EventOut":
        return cls(
            id=ev.id,
            source=ev.source,
            level=ev.level,
            message=ev.message,
            value=ev.value,
            tags=json.loads(ev.tags) if ev.tags else None,
            timestamp=ev.timestamp,
        )


def ingest_event(db: Session, payload: EventIn) -> Event:
    ev = Event(
        source=payload.source,
        level=payload.level,
        message=payload.message,
        value=payload.value,
        tags=json.dumps(payload.tags) if payload.tags else None,
        timestamp=payload.timestamp or datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev
