from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Application, Company
from app.schemas import ApplicationCreate, ApplicationUpdate
from app.services.status import InvalidChangeDate, change_status

DUPLICATE_INDEX = "uq_applications_company_title_applied_on"


class DuplicateApplication(Exception):
    def __init__(self, existing_id: int) -> None:
        super().__init__("An application with this company, title and date already exists.")
        self.existing_id = existing_id


def get_or_create_company(session: Session, name: str) -> Company:
    company = session.scalar(select(Company).where(func.lower(Company.name) == name.lower()))
    if company is None:
        company = Company(name=name)
        session.add(company)
    return company


def find_duplicate(
    session: Session, *, company_id: int, title: str, applied_on: date
) -> int | None:
    return session.scalar(
        select(Application.id).where(
            Application.company_id == company_id,
            func.lower(func.trim(Application.title)) == title.strip().lower(),
            Application.applied_on == applied_on,
        )
    )


def list_applications(session: Session) -> list[Application]:
    query = select(Application).order_by(Application.applied_on.desc(), Application.id.desc())
    return list(session.scalars(query))


def get_application(session: Session, application_id: int) -> Application | None:
    return session.get(Application, application_id)


def create_application(session: Session, data: ApplicationCreate, *, today: date) -> Application:
    company = get_or_create_company(session, data.company)
    application = Application(
        company=company,
        **data.model_dump(exclude={"company", "status"}),
    )
    change_status(application, data.status, changed_on=data.applied_on, today=today)
    session.add(application)
    _commit_or_raise_duplicate(session, application)
    return application


def update_application(
    session: Session, application: Application, data: ApplicationUpdate, *, today: date
) -> Application:
    changes = data.model_dump(exclude_unset=True)
    if "company" in changes:
        application.company = get_or_create_company(session, changes.pop("company"))
    if "applied_on" in changes:
        check_applied_on(application, changes["applied_on"], today=today)
    for name, value in changes.items():
        setattr(application, name, value)
    _commit_or_raise_duplicate(session, application)
    return application


def check_applied_on(application: Application, applied_on: date, *, today: date) -> None:
    # History rows are never rewritten, so the applied date can't move past a later change.
    if applied_on > today:
        raise InvalidChangeDate("The applied date can't be in the future.")
    later_changes = application.history[1:]
    if later_changes and applied_on > later_changes[0].changed_on:
        raise InvalidChangeDate(
            "The applied date can't be after the first status change "
            f"({later_changes[0].changed_on.isoformat()})."
        )


def delete_application(session: Session, application: Application) -> None:
    session.delete(application)
    session.commit()


def _commit_or_raise_duplicate(session: Session, application: Application) -> None:
    # The unique index is the source of truth; the lookup afterwards only finds the ID to show.
    with session.no_autoflush:  # loading the company must not flush (and fail) early
        key = (application.company, application.title, application.applied_on)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != DUPLICATE_INDEX:
            raise
        company, title, applied_on = key
        existing_id = find_duplicate(
            session, company_id=company.id, title=title, applied_on=applied_on
        )
        assert existing_id is not None
        raise DuplicateApplication(existing_id) from exc
