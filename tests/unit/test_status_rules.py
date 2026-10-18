from datetime import date

import pytest

from app.services.status import InvalidChangeDate, validate_change_date

TODAY = date(2026, 10, 17)
APPLIED = date(2026, 9, 12)
LATEST = date(2026, 9, 20)


def test_a_date_between_the_latest_change_and_today_is_allowed() -> None:
    validate_change_date(
        date(2026, 10, 1), today=TODAY, applied_on=APPLIED, latest_change_on=LATEST
    )


def test_today_is_allowed() -> None:
    validate_change_date(TODAY, today=TODAY, applied_on=APPLIED, latest_change_on=LATEST)


def test_a_future_date_is_rejected() -> None:
    with pytest.raises(InvalidChangeDate, match="future"):
        validate_change_date(
            date(2026, 10, 18), today=TODAY, applied_on=APPLIED, latest_change_on=LATEST
        )


def test_the_applied_date_itself_is_allowed() -> None:
    validate_change_date(APPLIED, today=TODAY, applied_on=APPLIED, latest_change_on=APPLIED)


def test_a_date_before_the_applied_date_is_rejected() -> None:
    with pytest.raises(InvalidChangeDate, match="applied"):
        validate_change_date(
            date(2026, 9, 11), today=TODAY, applied_on=APPLIED, latest_change_on=None
        )


def test_the_latest_change_date_itself_is_allowed() -> None:
    validate_change_date(LATEST, today=TODAY, applied_on=APPLIED, latest_change_on=LATEST)


def test_a_date_before_the_latest_change_is_rejected() -> None:
    with pytest.raises(InvalidChangeDate, match="latest status change"):
        validate_change_date(
            date(2026, 9, 19), today=TODAY, applied_on=APPLIED, latest_change_on=LATEST
        )


def test_with_no_earlier_change_only_applied_date_and_today_bound_it() -> None:
    validate_change_date(APPLIED, today=TODAY, applied_on=APPLIED, latest_change_on=None)
