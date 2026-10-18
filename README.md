# Job Application Tracker

A local tracker for an active job search. For every application it keeps the full job
description, applied date, status history, links, notes, company contacts and a dated log of
every conversation, so the interview-prep page has everything on one screen.

It answers three questions quickly:

1. **Before an interview:** what is this role, where does it stand, and who have I talked to?
2. **Follow-up:** which open applications have gone quiet long enough that I should check in?
3. **Resume tuning:** give me every rejected or no-response application with its job description,
   as markdown to paste into an LLM, with quick rejections kept apart from later ones.

Everything runs on your machine under Docker Compose. The app never calls an external service.

## Quickstart

Requirements: Docker with the Compose v2 plugin, and `make`.

```sh
git clone https://github.com/EnriqueRE/job-application-tracker.git
cd job-application-tracker
make up          # creates .env from .env.example, builds, migrates, starts
```

Then open <http://localhost:8000>. The JSON API is documented at <http://localhost:8000/docs>.

`make up` copies `.env.example` to `.env` on first run. Change `POSTGRES_PASSWORD` in `.env` before
you store real data. The app is published on `127.0.0.1` only.

| Command | What it does |
|---|---|
| `make up` / `make down` | Start or stop the stack. Data lives in the `pgdata` volume and survives `down`. |
| `make logs` | Follow the app's logs. |
| `make test` | Run the test suite in the dev image against a separate `tracker_test` database, with ≥ 85% coverage required on `app/services`. |
| `make lint` | `ruff check`, `ruff format --check` and `mypy --strict` (needs [`uv`](https://docs.astral.sh/uv/)). |
| `make backup` | Write a timestamped plain-SQL dump to `backups/` (git-ignored). |
| `make restore FILE=backups/<dump>.sql` | Stop the app, replace the database with the dump, start the app again. |

## Features

- **Applications:** company, role title, job URL, full pasted job description, location, source,
  applied date, status and notes. Company + title (ignoring case and surrounding whitespace) +
  applied date must be unique; a duplicate is refused with a link to the existing one.
- **Status history:** every change is recorded with the date it happened (defaults to today, can be
  back-dated, never in the future or out of order). The detail page changes status in place.
- **Contacts and interactions:** contacts belong to a company, so one recruiter covers several roles.
  Interactions (date, channel, optional contact, note) are listed newest first.
- **Follow-ups:** open applications (`applied`, `screening`, `interviewing`) with no activity for
  longer than their status's threshold, oldest first. Thresholds are edited on the settings page
  (defaults 7 / 5 / 3 days) and apply immediately.
- **Export:** `GET /api/export.md` downloads early rejections, late rejections (the history reached
  screening, interviewing or offer) and no-response applications with full job descriptions.

## Architecture

```
 browser ──HTML/htmx──► app/web    ─┐
                                    ├─► app/services ──SQLAlchemy──► PostgreSQL 16
 scripts ──JSON───────► app/api    ─┘    (domain rules)               (named volume)
```

- **FastAPI** serves two thin router sets over one service layer: `app/api` (JSON under `/api`) and
  `app/web` (Jinja2 templates with htmx 2, vendored in `app/web/static`, with no CDN).
- **Services own every rule.** `services.status.change_status()` is the only writer of an
  application's status and always appends a history row. Rules such as `validate_change_date`,
  `needs_follow_up`, `classify_rejection` and `render_export` are pure functions that take
  `today` explicitly, so their unit tests need no database.
- **The database enforces the invariants:** a functional unique index on
  `(company_id, lower(trim(title)), applied_on)`, CHECK constraints on statuses, channels and
  threshold ranges, and cascading deletes from an application to its history, links and interactions.
- **Sync SQLAlchemy 2** with typed models. A single user gains nothing from async, and sync keeps
  sessions, tests and Alembic simple.
- **Alembic migrations run at container start** (`docker/start.sh`), so `docker compose up` on a
  clean machine is enough. Migrations with expression indexes are written by hand, and
  `alembic check` is kept clean.
- **Tests** run against real Postgres, never SQLite. Each test runs in a transaction that is rolled
  back, and the harness refuses any database whose name doesn't end in `_test`.

```
app/
  api/         JSON routers
  services/    domain logic
  web/         HTML routers, templates, static assets
  models.py    SQLAlchemy models
  schemas.py   Pydantic request and response models
migrations/    Alembic
tests/unit/    pure rules (status dates, follow-up, export golden file)
tests/integration/  API and web through the TestClient against Postgres
```

## Roadmap

The project is built in stages. Each one gets its own spec when it starts.

| Stage | Adds | State |
|---|---|---|
| 1 | API, Postgres, htmx UI, status history, follow-ups, settings, markdown export, Docker Compose | Built; checkpoint (a week of real use) pending |
| 2 | CI/CD: lint, test, image build and push | Planned |
| 3 | Kubernetes manifests or a Helm chart | Planned |
| 4 | Terraform for a cloud deployment | Planned |

The stage 1 spec is in [SPEC.md](SPEC.md) and the task plan in [tasks/plan.md](tasks/plan.md).
