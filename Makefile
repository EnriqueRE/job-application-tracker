COMPOSE := docker compose

.PHONY: up down logs ps test lint

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
	$(COMPOSE) run --rm --build app pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy app tests
