from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from database import get_db
from models.event import Event
from services.ingestion import EventIn, EventOut, ingest_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/", response_model=EventOut, status_code=201)
def create_event(payload: EventIn, db: Session = Depends(get_db)):
    ev = ingest_event(db, payload)
    return EventOut.from_orm_event(ev)


@router.get("/", response_model=list[EventOut])
def list_events(
    source: str | None = Query(None),
    level: str | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(Event).order_by(desc(Event.timestamp)).offset(offset).limit(limit)
    if source:
        q = q.where(Event.source == source)
    if level:
        q = q.where(Event.level == level)
    rows = db.execute(q).scalars().all()
    return [EventOut.from_orm_event(r) for r in rows]


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventOut.from_orm_event(ev)
