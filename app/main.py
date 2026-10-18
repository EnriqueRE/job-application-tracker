from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import applications, contacts, export, follow_ups, settings
from app.db import get_session
from app.web import routes as web


def create_app() -> FastAPI:
    # The default docs pages load Swagger UI and ReDoc from a CDN; serve Swagger UI locally.
    app = FastAPI(title="Job Application Tracker", docs_url=None, redoc_url=None)

    @app.get("/docs", include_in_schema=False)
    def docs() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - API docs",
            swagger_js_url="/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger/swagger-ui.css",
            swagger_favicon_url="data:,",
            swagger_ui_parameters={"validatorUrl": None},
        )

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
    app.include_router(settings.router)
    app.include_router(follow_ups.router)
    app.include_router(export.router)
    app.include_router(web.router)
    app.mount("/static", StaticFiles(directory=web.STATIC_DIR), name="static")
    return app


app = create_app()
