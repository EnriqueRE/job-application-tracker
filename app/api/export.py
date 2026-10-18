from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.clock import get_today
from app.db import get_session
from app.services.export import ExportGroup, export_filename, export_markdown

router = APIRouter(prefix="/api", tags=["export"])


@router.get(
    "/export.md",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}}},
)
def export(
    session: Annotated[Session, Depends(get_session)],
    today: Annotated[date, Depends(get_today)],
    statuses: Annotated[
        list[ExportGroup],
        Query(description="Groups to include; all of them when omitted."),
    ] = [],  # noqa: B006
) -> Response:
    """Rejected and no-response applications with job descriptions, for resume review."""
    body = export_markdown(session, today=today, groups=statuses or tuple(ExportGroup))
    return Response(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{export_filename(today)}"'},
    )
