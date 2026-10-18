from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Application, Status

# Reaching any of these means the rejection came after a human looked at the application.
PAST_FIRST_FILTER = frozenset({Status.SCREENING, Status.INTERVIEWING, Status.OFFER})


class ExportGroup(StrEnum):
    REJECTED_EARLY = "rejected_early"
    REJECTED_LATE = "rejected_late"
    NO_RESPONSE = "no_response"


HEADINGS = {
    ExportGroup.REJECTED_EARLY: "Rejected without an interview",
    ExportGroup.REJECTED_LATE: "Rejected after screening or interviews",
    ExportGroup.NO_RESPONSE: "No response",
}


@dataclass(frozen=True)
class ExportEntry:
    company: str
    title: str
    applied_on: date
    job_url: str | None
    job_description: str
    path: Sequence[tuple[Status, date]]
    """Status history in order, ending at the current status."""

    @property
    def status(self) -> Status:
        return self.path[-1][0]


def classify_rejection(history: Iterable[Status]) -> ExportGroup:
    if PAST_FIRST_FILTER.intersection(history):
        return ExportGroup.REJECTED_LATE
    return ExportGroup.REJECTED_EARLY


def group_of(entry: ExportEntry) -> ExportGroup | None:
    if entry.status == Status.REJECTED:
        return classify_rejection(status for status, _ in entry.path)
    if entry.status == Status.NO_RESPONSE:
        return ExportGroup.NO_RESPONSE
    return None


def render_export(
    entries: Iterable[ExportEntry],
    *,
    exported_on: date,
    groups: Collection[ExportGroup] = tuple(ExportGroup),
) -> str:
    grouped: dict[ExportGroup, list[ExportEntry]] = {group: [] for group in ExportGroup}
    for entry in entries:
        group = group_of(entry)
        if group is not None and group in groups:
            grouped[group].append(entry)

    lines = [f"# Applications for resume review (exported {exported_on.isoformat()})", ""]
    if not any(grouped.values()):
        lines += ["No matching applications.", ""]
    for group, members in grouped.items():
        if not members:
            continue
        lines += [f"## {HEADINGS[group]}", ""]
        for entry in sorted(members, key=lambda e: (e.applied_on, e.company, e.title)):
            lines += _render_entry(entry)
    return "\n".join(lines)


def _render_entry(entry: ExportEntry) -> list[str]:
    path = " → ".join(f"{status.value} ({on.isoformat()})" for status, on in entry.path)
    lines = [
        f"### {entry.company} — {entry.title}",
        f"- Applied: {entry.applied_on.isoformat()}",
        f"- Status path: {path}",
    ]
    if entry.job_url:
        lines.append(f"- URL: {entry.job_url}")
    description = entry.job_description.lstrip("\n").rstrip() or "_No job description saved._"
    return [*lines, "", "#### Job description", description, "", "---", ""]


def collect_entries(session: Session) -> list[ExportEntry]:
    query = (
        select(Application)
        .where(Application.status.in_([Status.REJECTED, Status.NO_RESPONSE]))
        .options(selectinload(Application.company), selectinload(Application.history))
    )
    return [
        ExportEntry(
            company=application.company.name,
            title=application.title,
            applied_on=application.applied_on,
            job_url=application.job_url,
            job_description=application.job_description,
            path=[(change.to_status, change.changed_on) for change in application.history],
        )
        for application in session.scalars(query)
    ]


def export_markdown(
    session: Session, *, today: date, groups: Collection[ExportGroup] = tuple(ExportGroup)
) -> str:
    return render_export(collect_entries(session), exported_on=today, groups=groups)


def export_filename(today: date) -> str:
    return f"applications-for-review-{today.isoformat()}.md"
