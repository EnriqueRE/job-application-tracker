from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.clock import get_today
from app.db import get_session
from app.models import Application
from app.schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationUpdate,
    DuplicateOut,
    StatusChangeIn,
)
from app.services import applications as service
from app.services.status import InvalidChangeDate, record_status_change

router = APIRouter(prefix="/api/applications", tags=["applications"])

SessionDep = Annotated[Session, Depends(get_session)]
TodayDep = Annotated[date, Depends(get_today)]


def duplicate_response(exc: service.DuplicateApplication) -> JSONResponse:
    body = DuplicateOut(detail=str(exc), existing_id=exc.existing_id)
    return JSONResponse(body.model_dump(), status_code=status.HTTP_409_CONFLICT)


@router.get("", response_model=list[ApplicationOut])
def list_applications(session: SessionDep) -> list[ApplicationOut]:
    return [ApplicationOut.model_validate(a) for a in service.list_applications(session)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationOut,
    responses={409: {"model": DuplicateOut}},
)
def create_application(
    data: ApplicationCreate, session: SessionDep, today: TodayDep
) -> ApplicationOut | JSONResponse:
    try:
        application = service.create_application(session, data, today=today)
    except service.DuplicateApplication as exc:
        return duplicate_response(exc)
    except InvalidChangeDate as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return ApplicationOut.model_validate(application)


def get_or_404(session: Session, application_id: int) -> Application:
    application = service.get_application(session, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, session: SessionDep) -> ApplicationOut:
    return ApplicationOut.model_validate(get_or_404(session, application_id))


@router.patch(
    "/{application_id}", response_model=ApplicationOut, responses={409: {"model": DuplicateOut}}
)
def update_application(
    application_id: int, data: ApplicationUpdate, session: SessionDep, today: TodayDep
) -> ApplicationOut | JSONResponse:
    application = get_or_404(session, application_id)
    try:
        service.update_application(session, application, data, today=today)
    except service.DuplicateApplication as exc:
        return duplicate_response(exc)
    except InvalidChangeDate as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return ApplicationOut.model_validate(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, session: SessionDep) -> Response:
    service.delete_application(session, get_or_404(session, application_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{application_id}/status", response_model=ApplicationOut)
def change_status(
    application_id: int, data: StatusChangeIn, session: SessionDep, today: TodayDep
) -> ApplicationOut:
    application = get_or_404(session, application_id)
    try:
        record_status_change(
            session, application, data.status, changed_on=data.changed_on, today=today
        )
    except InvalidChangeDate as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return ApplicationOut.model_validate(application)
