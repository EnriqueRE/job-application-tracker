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
from app.models import Application
from app.schemas import ApplicationCreate
from app.services import applications as service
from app.services.status import InvalidChangeDate

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
    # Browsers send empty strings for untouched inputs; treat them as "not given".
    cleaned = {key: value for key, value in fields.items() if value.strip() != ""}
    try:
        return model.model_validate(cleaned)
    except ValidationError as exc:
        errors: dict[str, str] = {}
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "form"
            errors.setdefault(field, error["msg"].removeprefix("Value error, "))
        return errors


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
    return RedirectResponse(f"/applications/{application.id}", status.HTTP_303_SEE_OTHER)


@router.get("/applications/{application_id}", response_class=HTMLResponse)
def detail_page(request: Request, application_id: int, session: SessionDep) -> HTMLResponse:
    application = get_or_404(session, application_id)
    return templates.TemplateResponse(request, "detail.html", {"application": application})
