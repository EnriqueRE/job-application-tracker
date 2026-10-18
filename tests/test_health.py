from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import get_session


def test_healthz_reports_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_reports_unavailable_when_database_is_unreachable(app: FastAPI) -> None:
    unreachable = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere",
        connect_args={"connect_timeout": 1},
    )

    def unreachable_session() -> Iterator[Session]:
        with Session(unreachable) as session:
            yield session

    app.dependency_overrides[get_session] = unreachable_session

    response = TestClient(app).get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"status": "database unavailable"}
