from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session


def create_app() -> FastAPI:
    app = FastAPI(title="Job Application Tracker")

    @app.get("/healthz")
    def healthz(
        response: Response, session: Annotated[Session, Depends(get_session)]
    ) -> dict[str, str]:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "database unavailable"}
        return {"status": "ok"}

    return app


app = create_app()
