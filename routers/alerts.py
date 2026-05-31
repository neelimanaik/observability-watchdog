from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from database import get_db
from models.alert import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: int
    rule: str
    source: str
    message: str
    severity: str
    acknowledged: bool
    llm_analysis: str | None
    root_cause_category: str | None
    suppression_count: int
    created_at: str

    model_config = {"from_attributes": True}


def _to_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id,
        rule=a.rule,
        source=a.source,
        message=a.message,
        severity=a.severity,
        acknowledged=a.acknowledged,
        llm_analysis=a.llm_analysis,
        root_cause_category=a.root_cause_category,
        suppression_count=a.suppression_count,
        created_at=a.created_at.isoformat(),
    )


@router.get("/", response_model=list[AlertOut])
def list_alerts(
    acknowledged: bool | None = None,
    db: Session = Depends(get_db),
):
    q = select(Alert).order_by(func.datetime(Alert.created_at).desc())
    if acknowledged is not None:
        q = q.where(Alert.acknowledged == acknowledged)
    rows = db.execute(q).scalars().all()
    return [_to_out(r) for r in rows]


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    return _to_out(alert)
