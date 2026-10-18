from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import FollowUpSettings
from app.services import settings as service

router = APIRouter(prefix="/api/settings", tags=["settings"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/follow-up", response_model=FollowUpSettings)
def get_follow_up_settings(session: SessionDep) -> FollowUpSettings:
    return service.get_follow_up_settings(session)


@router.put("/follow-up", response_model=FollowUpSettings)
def update_follow_up_settings(data: FollowUpSettings, session: SessionDep) -> FollowUpSettings:
    return service.update_follow_up_settings(session, data)
