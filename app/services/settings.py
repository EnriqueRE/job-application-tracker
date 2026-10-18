from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FollowUpThreshold, Status
from app.schemas import FollowUpSettings


def get_thresholds(session: Session) -> dict[Status, int]:
    # Read on every request on purpose: an edit applies immediately, with no cache to clear.
    rows = session.scalars(select(FollowUpThreshold))
    return {row.status: row.days for row in rows}


def get_follow_up_settings(session: Session) -> FollowUpSettings:
    return FollowUpSettings.model_validate(
        {status.value: days for status, days in get_thresholds(session).items()}
    )


def update_follow_up_settings(session: Session, data: FollowUpSettings) -> FollowUpSettings:
    rows = {row.status: row for row in session.scalars(select(FollowUpThreshold))}
    for name, days in data.model_dump().items():
        status = Status(name)
        row = rows.get(status)
        if row is None:
            session.add(FollowUpThreshold(status=status, days=days))
        else:
            row.days = days
    session.commit()
    return get_follow_up_settings(session)
