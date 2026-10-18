from datetime import date
from pathlib import Path

import pytest

from app.models import Status
from app.services.export import (
    ExportEntry,
    ExportGroup,
    classify_rejection,
    group_of,
    render_export,
)

GOLDEN = Path(__file__).parent / "golden" / "export.md"
EXPORTED_ON = date(2026, 10, 17)

EARLY = ExportEntry(
    company="Acme Corp",
    title="Senior Platform Engineer",
    applied_on=date(2026, 9, 12),
    job_url="https://acme.example/jobs/1",
    job_description="Run Kubernetes.\n\nWrite Terraform.\n",
    path=[(Status.APPLIED, date(2026, 9, 12)), (Status.REJECTED, date(2026, 9, 14))],
)
LATE = ExportEntry(
    company="Globex",
    title="SRE",
    applied_on=date(2026, 9, 1),
    job_url=None,
    job_description="",
    path=[
        (Status.APPLIED, date(2026, 9, 1)),
        (Status.SCREENING, date(2026, 9, 5)),
        (Status.INTERVIEWING, date(2026, 9, 10)),
        (Status.REJECTED, date(2026, 9, 20)),
    ],
)
NO_RESPONSE = ExportEntry(
    company="Initech",
    title="Backend Developer",
    applied_on=date(2026, 8, 20),
    job_url="https://initech.example/careers/42",
    job_description="Maintain TPS report service.",
    path=[(Status.APPLIED, date(2026, 8, 20)), (Status.NO_RESPONSE, date(2026, 9, 30))],
)


@pytest.mark.parametrize(
    "history",
    [
        [Status.APPLIED, Status.REJECTED],
        [Status.REJECTED],
        [Status.APPLIED, Status.WITHDRAWN, Status.REJECTED],
    ],
)
def test_rejection_without_screening_interview_or_offer_is_early(
    history: list[Status],
) -> None:
    assert classify_rejection(history) == ExportGroup.REJECTED_EARLY


@pytest.mark.parametrize("reached", [Status.SCREENING, Status.INTERVIEWING, Status.OFFER])
def test_rejection_after_screening_interview_or_offer_is_late(reached: Status) -> None:
    history = [Status.APPLIED, reached, Status.REJECTED]

    assert classify_rejection(history) == ExportGroup.REJECTED_LATE


def test_group_of_puts_each_closed_status_in_its_group() -> None:
    assert group_of(EARLY) == ExportGroup.REJECTED_EARLY
    assert group_of(LATE) == ExportGroup.REJECTED_LATE
    assert group_of(NO_RESPONSE) == ExportGroup.NO_RESPONSE


def test_other_statuses_are_not_exported() -> None:
    offer = ExportEntry(
        company="A",
        title="B",
        applied_on=date(2026, 9, 1),
        job_url=None,
        job_description="",
        path=[(Status.APPLIED, date(2026, 9, 1)), (Status.OFFER, date(2026, 9, 9))],
    )

    assert group_of(offer) is None


def test_render_matches_the_golden_file() -> None:
    rendered = render_export([NO_RESPONSE, LATE, EARLY], exported_on=EXPORTED_ON)

    assert rendered == GOLDEN.read_text()


def test_empty_groups_are_left_out() -> None:
    rendered = render_export([EARLY], exported_on=EXPORTED_ON)

    assert "## Rejected without an interview" in rendered
    assert "## Rejected after screening or interviews" not in rendered
    assert "## No response" not in rendered


def test_groups_filter_narrows_the_export() -> None:
    rendered = render_export(
        [EARLY, LATE, NO_RESPONSE],
        exported_on=EXPORTED_ON,
        groups={ExportGroup.REJECTED_EARLY},
    )

    assert "Acme Corp" in rendered
    assert "Globex" not in rendered
    assert "Initech" not in rendered


def test_nothing_to_export_still_has_a_heading_and_says_so() -> None:
    rendered = render_export([], exported_on=EXPORTED_ON)

    assert rendered.startswith("# Applications for resume review (exported 2026-10-17)\n")
    assert "No matching applications." in rendered


def test_entries_within_a_group_are_oldest_applied_first() -> None:
    newer = ExportEntry(
        company="Zeta",
        title="SRE",
        applied_on=date(2026, 10, 1),
        job_url=None,
        job_description="",
        path=[(Status.APPLIED, date(2026, 10, 1)), (Status.REJECTED, date(2026, 10, 2))],
    )

    rendered = render_export([newer, EARLY], exported_on=EXPORTED_ON)

    assert rendered.index("Acme Corp") < rendered.index("Zeta")
