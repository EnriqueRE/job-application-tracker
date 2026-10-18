from datetime import date, timedelta

import pytest

from app.models import Status
from app.services.follow_up import last_activity_on, needs_follow_up

TODAY = date(2026, 10, 17)
DEFAULTS = {Status.APPLIED: 7, Status.SCREENING: 5, Status.INTERVIEWING: 3}


@pytest.mark.parametrize(("status", "days"), list(DEFAULTS.items()))
def test_exactly_at_the_threshold_does_not_need_follow_up(status: Status, days: int) -> None:
    last = TODAY - timedelta(days=days)

    assert not needs_follow_up(status, last_activity=last, today=TODAY, thresholds=DEFAULTS)


@pytest.mark.parametrize(("status", "days"), list(DEFAULTS.items()))
def test_one_day_past_the_threshold_needs_follow_up(status: Status, days: int) -> None:
    last = TODAY - timedelta(days=days + 1)

    assert needs_follow_up(status, last_activity=last, today=TODAY, thresholds=DEFAULTS)


@pytest.mark.parametrize(
    "status",
    [Status.OFFER, Status.ACCEPTED, Status.REJECTED, Status.WITHDRAWN, Status.NO_RESPONSE],
)
def test_closed_statuses_never_need_follow_up(status: Status) -> None:
    long_ago = TODAY - timedelta(days=400)

    assert not needs_follow_up(status, last_activity=long_ago, today=TODAY, thresholds=DEFAULTS)


def test_thresholds_are_per_status() -> None:
    six_days_ago = TODAY - timedelta(days=6)

    assert not needs_follow_up(
        Status.APPLIED, last_activity=six_days_ago, today=TODAY, thresholds=DEFAULTS
    )
    assert needs_follow_up(
        Status.SCREENING, last_activity=six_days_ago, today=TODAY, thresholds=DEFAULTS
    )


def test_an_edited_threshold_is_used() -> None:
    ten_days_ago = TODAY - timedelta(days=10)
    thresholds = {**DEFAULTS, Status.APPLIED: 14}

    assert not needs_follow_up(
        Status.APPLIED, last_activity=ten_days_ago, today=TODAY, thresholds=thresholds
    )


def test_an_open_status_without_a_threshold_is_not_listed() -> None:
    assert not needs_follow_up(
        Status.APPLIED, last_activity=date(2020, 1, 1), today=TODAY, thresholds={}
    )


def test_last_activity_with_no_interactions_or_changes_is_the_applied_date() -> None:
    applied = date(2026, 9, 12)

    assert last_activity_on(applied_on=applied, status_changes=[applied], interactions=[]) == (
        applied
    )


def test_a_back_dated_status_change_counts_from_its_change_date() -> None:
    result = last_activity_on(
        applied_on=date(2026, 9, 12),
        status_changes=[date(2026, 9, 12), date(2026, 9, 20)],
        interactions=[],
    )

    assert result == date(2026, 9, 20)


def test_a_recent_interaction_moves_last_activity() -> None:
    result = last_activity_on(
        applied_on=date(2026, 9, 12),
        status_changes=[date(2026, 9, 12), date(2026, 9, 20)],
        interactions=[date(2026, 9, 15), date(2026, 10, 2)],
    )

    assert result == date(2026, 10, 2)
