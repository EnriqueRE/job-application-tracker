from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import OPEN_STATUSES, Application, Status
from app.services.settings import get_thresholds


def last_activity_on(
    *, applied_on: date, status_changes: Iterable[date], interactions: Iterable[date]
) -> date:
    return max([applied_on, *status_changes, *interactions])


def needs_follow_up(
    status: Status, *, last_activity: date, today: date, thresholds: Mapping[Status, int]
) -> bool:
    """Open application with no activity for longer than its status's threshold."""
    if status not in OPEN_STATUSES or status not in thresholds:
        return False
    return (today - last_activity).days > thresholds[status]


def application_last_activity(application: Application) -> date:
    return last_activity_on(
        applied_on=application.applied_on,
        status_changes=(change.changed_on for change in application.history),
        interactions=(interaction.occurred_on for interaction in application.interactions),
    )


@dataclass(frozen=True)
class FollowUp:
    application: Application
    last_activity_on: date
    days_since_activity: int
    threshold_days: int

    @property
    def days_overdue(self) -> int:
        return self.days_since_activity - self.threshold_days


def list_follow_ups(session: Session, *, today: date) -> list[FollowUp]:
    thresholds = get_thresholds(session)
    query = (
        select(Application)
        .where(Application.status.in_(OPEN_STATUSES))
        .options(
            selectinload(Application.company),
            selectinload(Application.history),
            selectinload(Application.interactions),
        )
    )
    follow_ups = []
    for application in session.scalars(query):
        last = application_last_activity(application)
        if needs_follow_up(
            application.status, last_activity=last, today=today, thresholds=thresholds
        ):
            follow_ups.append(
                FollowUp(
                    application=application,
                    last_activity_on=last,
                    days_since_activity=(today - last).days,
                    threshold_days=thresholds[application.status],
                )
            )
    return sorted(follow_ups, key=lambda f: (f.last_activity_on, f.application.id))
