from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.clock import get_today
from app.db import get_session
from app.models import Application, Channel, Contact, Status
from app.schemas import (
    ApplicationCreate,
    ApplicationFields,
    ApplicationUpdate,
    ContactIn,
    ContactUpdate,
    FollowUpSettings,
    InteractionIn,
    LinkIn,
    StatusChangeIn,
)
from app.services import applications as service
from app.services import contacts, interactions, links
from app.services import settings as settings_service
from app.services.follow_up import application_last_activity, list_follow_ups
from app.services.status import InvalidChangeDate, record_status_change

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=WEB_DIR / "templates")

router = APIRouter(include_in_schema=False)

SessionDep = Annotated[Session, Depends(get_session)]
TodayDep = Annotated[date, Depends(get_today)]


async def form_fields(request: Request) -> dict[str, str]:
    # Read the form ourselves so a bad field re-renders the page instead of a raw 422.
    form = await request.form()
    return {key: value for key, value in form.items() if isinstance(value, str)}


FormDep = Annotated[dict[str, str], Depends(form_fields)]


def parse_form[M: BaseModel](model: type[M], fields: dict[str, str]) -> M | dict[str, str]:
    """Validate a form, returning the model or field name -> error message."""
    # Browsers send "" for empty inputs; that means None for nullable fields like job_url.
    cleaned: dict[str, str | None] = {
        key: None if value.strip() == "" and _defaults_to_none(model, key) else value
        for key, value in fields.items()
    }
    try:
        return model.model_validate(cleaned)
    except ValidationError as exc:
        errors: dict[str, str] = {}
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "form"
            errors.setdefault(field, error["msg"].removeprefix("Value error, "))
        return errors


def _defaults_to_none(model: type[BaseModel], name: str) -> bool:
    info = model.model_fields.get(name)
    return info is not None and not info.is_required() and info.default is None


def is_htmx(request: Request) -> bool:
    # A history restore (back button after hx-push-url) needs the whole page.
    headers = request.headers
    return headers.get("HX-Request") == "true" and "HX-History-Restore-Request" not in headers


def redirect(request: Request, url: str) -> Response:
    if is_htmx(request):
        return Response(headers={"HX-Redirect": url})
    return RedirectResponse(url, status.HTTP_303_SEE_OTHER)


def get_or_404(session: Session, application_id: int) -> Application:
    application = service.get_application(session, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


def render_form(
    request: Request,
    *,
    values: dict[str, Any],
    action: str,
    heading: str,
    errors: dict[str, str] | None = None,
    duplicate_id: int | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    context = {
        "values": values,
        "errors": errors or {},
        "action": action,
        "heading": heading,
        "duplicate_id": duplicate_id,
    }
    return templates.TemplateResponse(request, "form.html", context, status_code=status_code)


def detail_context(application: Application, today: date, **extra: Any) -> dict[str, Any]:
    return {
        "application": application,
        "today": today,
        "statuses": list(Status),
        "channels": list(Channel),
        **extra,
    }


def section(
    request: Request,
    template: str,
    application: Application,
    today: date,
    *,
    error: str | None = None,
    **extra: Any,
) -> Response:
    """Render one detail-page section for htmx, or go back to the page for a plain form post."""
    if not is_htmx(request):
        if error is None:
            return redirect(request, f"/applications/{application.id}")
        template = "detail.html"
    return templates.TemplateResponse(
        request,
        template,
        detail_context(application, today, **extra, **{f"{template_key(template)}_error": error}),
        status_code=status.HTTP_200_OK if error is None else status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def template_key(template: str) -> str:
    return template.removeprefix("_").removesuffix(".html")


@router.get("/", response_class=HTMLResponse)
def list_page(
    request: Request,
    session: SessionDep,
    statuses: Annotated[list[Status], Query(alias="status")] = [],  # noqa: B006
    q: str = "",
) -> HTMLResponse:
    applications = service.list_applications(session, statuses=statuses, q=q)
    context = {
        "applications": applications,
        "statuses": list(Status),
        "selected": set(statuses),
        "q": q,
        "filtered": bool(statuses or q.strip()),
        "last_activity": application_last_activity,
    }
    template = "_rows.html" if is_htmx(request) else "list.html"
    return templates.TemplateResponse(request, template, context)


@router.get("/applications/new", response_class=HTMLResponse)
def new_application_page(request: Request, today: TodayDep) -> HTMLResponse:
    return render_form(
        request,
        values={"applied_on": today.isoformat()},
        action="/applications",
        heading="New application",
    )


@router.post("/applications", response_class=HTMLResponse)
def create_application(
    request: Request, fields: FormDep, session: SessionDep, today: TodayDep
) -> Response:
    def again(**kwargs: Any) -> HTMLResponse:
        return render_form(
            request, values=fields, action="/applications", heading="New application", **kwargs
        )

    data = parse_form(ApplicationCreate, fields)
    if isinstance(data, dict):
        return again(errors=data, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        application = service.create_application(session, data, today=today)
    except InvalidChangeDate as exc:
        return again(
            errors={"applied_on": str(exc)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )
    except service.DuplicateApplication as exc:
        return again(duplicate_id=exc.existing_id, status_code=status.HTTP_409_CONFLICT)
    return redirect(request, f"/applications/{application.id}")


@router.get("/applications/{application_id}", response_class=HTMLResponse)
def detail_page(
    request: Request, application_id: int, session: SessionDep, today: TodayDep
) -> HTMLResponse:
    application = get_or_404(session, application_id)
    return templates.TemplateResponse(request, "detail.html", detail_context(application, today))


@router.post("/applications/{application_id}/status", response_class=HTMLResponse)
def change_status(
    request: Request,
    application_id: int,
    fields: FormDep,
    session: SessionDep,
    today: TodayDep,
) -> Response:
    application = get_or_404(session, application_id)
    data = parse_form(StatusChangeIn, fields)
    error: str | None = None
    if isinstance(data, dict):
        error = next(iter(data.values()))
    else:
        try:
            record_status_change(
                session, application, data.status, changed_on=data.changed_on, today=today
            )
        except InvalidChangeDate as exc:
            error = str(exc)
    return section(request, "_status.html", application, today, error=error, attempted=fields)


def form_values(application: Application) -> dict[str, Any]:
    return {
        "company": application.company.name,
        "title": application.title,
        "job_url": application.job_url,
        "job_description": application.job_description,
        "location": application.location,
        "source": application.source,
        "applied_on": application.applied_on.isoformat(),
        "notes": application.notes,
    }


@router.get("/applications/{application_id}/edit", response_class=HTMLResponse)
def edit_application_page(
    request: Request, application_id: int, session: SessionDep
) -> HTMLResponse:
    application = get_or_404(session, application_id)
    return render_form(
        request,
        values=form_values(application),
        action=f"/applications/{application.id}",
        heading=f"Edit {application.title}",
    )


@router.post("/applications/{application_id}", response_class=HTMLResponse)
def update_application(
    request: Request,
    application_id: int,
    fields: FormDep,
    session: SessionDep,
    today: TodayDep,
) -> Response:
    application = get_or_404(session, application_id)
    heading = f"Edit {application.title}"

    def again(**kwargs: Any) -> HTMLResponse:
        return render_form(
            request,
            values=fields,
            action=f"/applications/{application_id}",
            heading=heading,
            **kwargs,
        )

    data = parse_form(ApplicationFields, fields)
    if isinstance(data, dict):
        return again(errors=data, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        service.update_application(
            session, application, ApplicationUpdate(**data.model_dump()), today=today
        )
    except InvalidChangeDate as exc:
        return again(
            errors={"applied_on": str(exc)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )
    except service.DuplicateApplication as exc:
        return again(duplicate_id=exc.existing_id, status_code=status.HTTP_409_CONFLICT)
    return redirect(request, f"/applications/{application_id}")


@router.post("/applications/{application_id}/delete")
def delete_application(request: Request, application_id: int, session: SessionDep) -> Response:
    service.delete_application(session, get_or_404(session, application_id))
    return redirect(request, "/")


@router.post("/applications/{application_id}/links", response_class=HTMLResponse)
def add_link(
    request: Request, application_id: int, fields: FormDep, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    data = parse_form(LinkIn, fields)
    if isinstance(data, dict):
        return section(
            request,
            "_links.html",
            application,
            today,
            error=errors_text(data),
            link_values=fields,
        )
    links.add_link(session, application, data)
    return section(request, "_links.html", application, today)


@router.post("/applications/{application_id}/links/{link_id}/delete", response_class=HTMLResponse)
def remove_link(
    request: Request, application_id: int, link_id: int, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    link = links.get_link(session, application, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    links.remove_link(session, application, link)
    return section(request, "_links.html", application, today)


def contact_or_404(session: Session, application: Application, contact_id: int) -> Contact:
    contact = contacts.get_contact(session, contact_id)
    if contact is None or contact.company_id != application.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


def contacts_changed(response: Response) -> Response:
    # The interactions form lists contacts too; this event makes it refresh itself.
    response.headers["HX-Trigger"] = "contacts-changed"
    return response


def errors_text(errors: dict[str, str]) -> str:
    return " ".join(f"{field}: {message}" for field, message in errors.items())


@router.get("/applications/{application_id}/contacts", response_class=HTMLResponse)
def contacts_section(
    request: Request, application_id: int, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    return section(request, "_contacts.html", application, today)


@router.post("/applications/{application_id}/contacts", response_class=HTMLResponse)
def add_contact(
    request: Request, application_id: int, fields: FormDep, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    data = parse_form(ContactIn, fields)
    if isinstance(data, dict):
        return section(
            request,
            "_contacts.html",
            application,
            today,
            error=errors_text(data),
            contact_values=fields,
        )
    contacts.create_contact(session, application.company, data)
    return contacts_changed(section(request, "_contacts.html", application, today))


@router.get(
    "/applications/{application_id}/contacts/{contact_id}/edit", response_class=HTMLResponse
)
def edit_contact_form(
    request: Request, application_id: int, contact_id: int, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    contact = contact_or_404(session, application, contact_id)
    return templates.TemplateResponse(
        request,
        "_contacts.html" if is_htmx(request) else "detail.html",
        detail_context(application, today, editing_contact_id=contact.id),
    )


@router.post("/applications/{application_id}/contacts/{contact_id}", response_class=HTMLResponse)
def update_contact(
    request: Request,
    application_id: int,
    contact_id: int,
    fields: FormDep,
    session: SessionDep,
    today: TodayDep,
) -> Response:
    application = get_or_404(session, application_id)
    contact = contact_or_404(session, application, contact_id)
    data = parse_form(ContactIn, fields)
    if isinstance(data, dict):
        return section(
            request,
            "_contacts.html",
            application,
            today,
            error=errors_text(data),
            editing_contact_id=contact.id,
            edit_values=fields,
        )
    contacts.update_contact(session, contact, ContactUpdate(**data.model_dump()))
    return contacts_changed(section(request, "_contacts.html", application, today))


@router.post(
    "/applications/{application_id}/contacts/{contact_id}/delete", response_class=HTMLResponse
)
def delete_contact(
    request: Request, application_id: int, contact_id: int, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    contacts.delete_contact(session, contact_or_404(session, application, contact_id))
    return contacts_changed(section(request, "_contacts.html", application, today))


@router.get("/applications/{application_id}/interactions", response_class=HTMLResponse)
def interactions_section(
    request: Request, application_id: int, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    return section(request, "_interactions.html", application, today)


@router.post("/applications/{application_id}/interactions", response_class=HTMLResponse)
def log_interaction(
    request: Request, application_id: int, fields: FormDep, session: SessionDep, today: TodayDep
) -> Response:
    application = get_or_404(session, application_id)
    data = parse_form(InteractionIn, fields)
    if isinstance(data, dict):
        return section(
            request,
            "_interactions.html",
            application,
            today,
            error=errors_text(data),
            interaction_values=fields,
        )
    try:
        interactions.log_interaction(session, application, data, today=today)
    except interactions.InvalidInteraction as exc:
        return section(
            request,
            "_interactions.html",
            application,
            today,
            error=str(exc),
            interaction_values=fields,
        )
    return section(request, "_interactions.html", application, today)


@router.post(
    "/applications/{application_id}/interactions/{interaction_id}/delete",
    response_class=HTMLResponse,
)
def delete_interaction(
    request: Request,
    application_id: int,
    interaction_id: int,
    session: SessionDep,
    today: TodayDep,
) -> Response:
    application = get_or_404(session, application_id)
    interaction = interactions.get_interaction(session, application, interaction_id)
    if interaction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interaction not found")
    interactions.delete_interaction(session, application, interaction)
    return section(request, "_interactions.html", application, today)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: SessionDep, saved: bool = False) -> HTMLResponse:
    values = settings_service.get_follow_up_settings(session).model_dump()
    return templates.TemplateResponse(
        request, "settings.html", {"values": values, "errors": {}, "saved": saved}
    )


@router.post("/settings", response_class=HTMLResponse)
def save_settings(request: Request, fields: FormDep, session: SessionDep) -> Response:
    data = parse_form(FollowUpSettings, fields)
    if isinstance(data, dict):
        return templates.TemplateResponse(
            request,
            "settings.html",
            {"values": fields, "errors": data, "saved": False},
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    settings_service.update_follow_up_settings(session, data)
    return redirect(request, "/settings?saved=true")


@router.get("/follow-ups", response_class=HTMLResponse)
def follow_ups_page(request: Request, session: SessionDep, today: TodayDep) -> HTMLResponse:
    follow_ups = list_follow_ups(session, today=today)
    return templates.TemplateResponse(
        request, "follow_ups.html", {"follow_ups": follow_ups, "today": today}
    )
