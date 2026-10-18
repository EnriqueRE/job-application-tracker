import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import Session

from app.db import get_session
from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("TEST_DATABASE_URL is not set; run database tests with `make test`.", 2)
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.exit(f"Refusing to run tests against non-test database {database!r}.", 2)

    alembic_cfg = Config(str(ROOT / "alembic.ini"))
    alembic_cfg.attributes["database_url"] = url
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Session whose work is rolled back after each test, even if the code under test commits."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
