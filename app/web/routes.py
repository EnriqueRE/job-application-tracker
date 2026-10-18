from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_session
from app.services import applications as service

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=WEB_DIR / "templates")

router = APIRouter(include_in_schema=False)

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/", response_class=HTMLResponse)
def list_page(request: Request, session: SessionDep) -> HTMLResponse:
    applications = service.list_applications(session)
    return templates.TemplateResponse(request, "list.html", {"applications": applications})
