#!/bin/sh
# Container default command: bring the schema up to date, then serve.
# `docker compose run app <cmd>` replaces this, so one-off commands never migrate.
set -eu
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
