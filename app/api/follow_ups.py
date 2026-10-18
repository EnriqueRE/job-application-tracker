from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clock import get_today
from app.db import get_session
from app.schemas import FollowUpOut
from app.services.follow_up import list_follow_ups

router = APIRouter(prefix="/api/follow-ups", tags=["follow-ups"])


@router.get("", response_model=list[FollowUpOut])
def follow_ups(
    session: Annotated[Session, Depends(get_session)],
    today: Annotated[date, Depends(get_today)],
) -> list[FollowUpOut]:
    """Open applications quiet for longer than their status's threshold, oldest first."""
    return [
        FollowUpOut(
            id=f.application.id,
            company=f.application.company.name,
            title=f.application.title,
            status=f.application.status,
            applied_on=f.application.applied_on,
            last_activity_on=f.last_activity_on,
            days_since_activity=f.days_since_activity,
            threshold_days=f.threshold_days,
            days_overdue=f.days_overdue,
        )
        for f in list_follow_ups(session, today=today)
    ]
