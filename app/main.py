from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import applications, contacts
from app.db import get_session
from app.web import routes as web


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

    app.include_router(applications.router)
    app.include_router(contacts.router)
    app.include_router(web.router)
    app.mount("/static", StaticFiles(directory=web.STATIC_DIR), name="static")
    return app


app = create_app()
