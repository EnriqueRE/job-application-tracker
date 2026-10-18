from datetime import date

from sqlalchemy.orm import Session

from app.models import Application, Status, StatusChange


class InvalidChangeDate(ValueError):
    pass


def validate_change_date(
    changed_on: date, *, today: date, applied_on: date, latest_change_on: date | None
) -> None:
    """Keep history ordered so it always ends at the current status."""
    if changed_on > today:
        raise InvalidChangeDate("The change date can't be in the future.")
    if changed_on < applied_on:
        raise InvalidChangeDate(
            f"The change date can't be before the applied date ({applied_on.isoformat()})."
        )
    if latest_change_on is not None and changed_on < latest_change_on:
        raise InvalidChangeDate(
            "The change date can't be before the latest status change "
            f"({latest_change_on.isoformat()})."
        )


def change_status(
    application: Application, to_status: Status, *, changed_on: date, today: date
) -> StatusChange | None:
    """The only writer of ``Application.status``; every change is recorded in history.

    Returns None when the status is unchanged, since re-setting it is not an event.
    """
    latest = application.history[-1] if application.history else None
    if latest is not None and to_status == application.status:
        return None
    validate_change_date(
        changed_on,
        today=today,
        applied_on=application.applied_on,
        latest_change_on=latest.changed_on if latest else None,
    )
    change = StatusChange(
        from_status=latest.to_status if latest else None,
        to_status=to_status,
        changed_on=changed_on,
    )
    application.status = to_status
    application.history.append(change)
    return change


def record_status_change(
    session: Session,
    application: Application,
    to_status: Status,
    *,
    changed_on: date | None,
    today: date,
) -> StatusChange | None:
    change = change_status(application, to_status, changed_on=changed_on or today, today=today)
    session.commit()
    return change
