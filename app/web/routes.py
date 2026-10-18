from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.clock import get_today
from app.db import get_session
from app.models import Application, Status
from app.schemas import ApplicationCreate, ApplicationFields, ApplicationUpdate, StatusChangeIn
from app.services import applications as service
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
    return request.headers.get("HX-Request") == "true"


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


@router.get("/", response_class=HTMLResponse)
def list_page(request: Request, session: SessionDep) -> HTMLResponse:
    applications = service.list_applications(session)
    return templates.TemplateResponse(request, "list.html", {"applications": applications})


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


def detail_context(application: Application, today: date, **extra: Any) -> dict[str, Any]:
    return {"application": application, "today": today, "statuses": list(Status), **extra}


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
    if error is None and not is_htmx(request):
        return redirect(request, f"/applications/{application_id}")
    template = "_status.html" if is_htmx(request) else "detail.html"
    return templates.TemplateResponse(
        request,
        template,
        detail_context(application, today, status_error=error, attempted=fields),
        status_code=status.HTTP_200_OK if error is None else status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


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
