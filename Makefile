COMPOSE := docker compose

.PHONY: up down logs ps test lint backup restore

.env:
	cp .env.example .env

up: .env
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f app

ps:
	$(COMPOSE) ps

test: .env
	$(COMPOSE) run --rm --build app pytest -q --cov=app/services --cov-report=term --cov-fail-under=85

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy app tests

# Plain-SQL dump with DROP statements, so restoring replaces whatever is there.
backup:
	@mkdir -p backups
	@file=backups/tracker-$$(date +%Y%m%d-%H%M%S).sql; \
	$(COMPOSE) exec -T db sh -c 'pg_dump --clean --if-exists -U "$$POSTGRES_USER" "$$POSTGRES_DB"' > $$file \
		&& echo "Wrote $$file" || { rm -f $$file; exit 1; }

# Usage: make restore FILE=backups/tracker-YYYYMMDD-HHMMSS.sql
restore:
	@test -f "$(FILE)" || { echo "usage: make restore FILE=backups/<dump>.sql"; exit 1; }
	$(COMPOSE) stop app
	$(COMPOSE) exec -T db sh -c 'psql -q -o /dev/null -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < "$(FILE)"
	$(COMPOSE) up -d --wait app
