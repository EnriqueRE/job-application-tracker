from datetime import date

from app.models import Application, Status, StatusChange


class InvalidChangeDate(ValueError):
    pass


def change_status(
    application: Application, to_status: Status, *, changed_on: date, today: date
) -> StatusChange | None:
    """The only writer of ``Application.status``; every change is recorded in history.

    Returns None when the status is unchanged, since re-setting it is not an event.
    """
    if changed_on > today:
        raise InvalidChangeDate("The change date can't be in the future.")
    latest = application.history[-1] if application.history else None
    if latest is not None and to_status == application.status:
        return None
    change = StatusChange(
        from_status=latest.to_status if latest else None,
        to_status=to_status,
        changed_on=changed_on,
    )
    application.status = to_status
    application.history.append(change)
    return change
