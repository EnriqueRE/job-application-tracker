# Spec: Job Application Tracker — Stage 1 (Local Tracker)

Status: APPROVED (2026-10-17)
Intent: [docs/intent/job-application-tracker.md](docs/intent/job-application-tracker.md)

## Objective

Replace the job-search spreadsheet with a local app that keeps, for every application, the full job
description, applied date, status and its history, links, notes, company contacts, and a dated log
of every conversation. It answers three questions quickly:

1. **Before an interview:** "What is this role, where does it stand, and who have I talked to?"
2. **Follow-up:** "Which open applications have gone quiet long enough that I should check in?"
3. **Resume tuning:** "Give me every rejected or no-response application with its job description,
   as markdown I can paste into Claude, with quick rejections kept apart from later ones."

The user is a single person (the owner) running an active backend and DevOps/platform job search.
The repo is also a portfolio piece, so code, tests, and infrastructure should be clean enough to
show in interviews.

Stage 1 is the only stage specified here. Later stages each get their own spec when they start:

| Stage | Adds |
|---|---|
| 1 (this spec) | API, Postgres, htmx web UI, status history, follow-up list and settings, markdown export, Docker Compose |
| 2 | CI/CD (lint, test, image build and push) |
| 3 | Kubernetes manifests or Helm chart |
| 4 | Terraform for a cloud deployment |

Backlog, not assigned to a stage yet: CSV import (the existing spreadsheet data is stale).

### User stories

- **Applications:** I can create, view, edit, and delete an application with company, role title,
  job URL, full job description (pasted text), location, source (LinkedIn, referral, etc.),
  applied date, status, and free-form notes.
- **Duplicates:** If I try to create an application with the same company, role title, and
  applied date as an existing one, I'm told it's a duplicate and shown a link to the existing
  application. Nothing is created.
- **Links:** I can attach extra labeled links to an application (careers page, recruiter's
  LinkedIn, take-home repo).
- **Status and history:** I can change status and set the date the change happened (defaults to
  today), so I can record things after the fact. Every change is recorded, and the application
  page shows the full status history.
- **Contacts:** I can add contacts at a company (name, title, email, LinkedIn URL, notes). An
  application page shows every contact at that company.
- **Interactions:** I can log an interaction on an application (date, channel, optional contact,
  note). The application page shows them newest first.
- **Follow-up list:** I can see open applications that have gone quiet past the threshold for their
  current status, oldest first.
- **Settings:** I can view and edit the follow-up threshold for each open status on a settings
  page.
- **Search:** I can filter the list by status and search by company or role title.
- **Export:** I can download a markdown file of rejected and no-response applications with their
  full job descriptions, grouped by how far each one got.

### Domain rules

- **Statuses:** `applied`, `screening`, `interviewing`, `offer`, `accepted`, `rejected`,
  `withdrawn`, `no_response`.
- **Open** means `applied`, `screening`, or `interviewing`.
- **Status history:** each status change, including the initial status on create, adds a row with
  `from_status`, `to_status`, `changed_on` (the date it happened), and `recorded_at` (when it was
  entered). Setting the same status again records nothing. History rows are never edited and are
  deleted only along with their application.
- **Change dates:** `changed_on` defaults to today. On create it is `applied_on`. A change date
  can't be in the future, before `applied_on`, or before the newest existing change's
  `changed_on`, so history order always ends at the current status. History is ordered by
  `changed_on`, then `recorded_at`.
- **Last activity** is the latest of: `applied_on`, the newest interaction date, and the newest
  status change's `changed_on`.
- **Follow-up threshold** depends on the current status. Thresholds are stored in the
  `follow_up_thresholds` table and edited on the settings page. A migration seeds the defaults:

  | Status | Default days |
  |---|---|
  | `applied` | 7 |
  | `screening` | 5 |
  | `interviewing` | 3 |

  A threshold is a whole number from 1 to 365. Only open statuses have thresholds.

  An open application needs follow-up when `today - last_activity > threshold[status]`.
- **`no_response`** is set by hand. The app never changes status on its own.
- **Early vs. late rejection:** a `rejected` application is *early* if its history never reached
  `screening`, `interviewing`, or `offer`. Otherwise it's *late*.
- **Duplicates:** company + role title (ignoring case and surrounding whitespace) + `applied_on`
  is unique, enforced by a database unique index. The API returns `409 Conflict` with the ID of
  the existing application. Editing an application into a duplicate is rejected the same way.
- **Channels:** `email`, `linkedin`, `phone`, `video`, `in_person`, `other`.
- **Company names** are unique, ignoring case. Creating an application with a new company name
  creates the company.

### Data model

```
companies       id, name (unique, case-insensitive), website, notes, created_at, updated_at
applications    id, company_id → companies, title, job_url, job_description (text), location,
                source, applied_on (date), status, notes, created_at, updated_at
                UNIQUE (company_id, lower(trim(title)), applied_on)
status_changes  id, application_id → applications (cascade), from_status (nullable on create),
                to_status, changed_on (date), recorded_at (timestamp)
follow_up_thresholds
                status (PK, open statuses only), days (int, CHECK 1–365), updated_at
app_links       id, application_id → applications (cascade), label, url
contacts        id, company_id → companies, name, title, email, linkedin_url, notes,
                created_at, updated_at
interactions    id, application_id → applications (cascade), contact_id → contacts (nullable,
                set null), occurred_on (date), channel, note, created_at
```

Contacts belong to a company, not to an application, so one recruiter can cover several roles.
The link between a contact and an application comes from interactions.

### Markdown export format

```markdown
# Applications for resume review (exported 2026-10-17)

## Rejected without an interview

### Acme Corp — Senior Platform Engineer
- Applied: 2026-09-12
- Status path: applied (2026-09-12) → rejected (2026-09-14)
- URL: https://...

#### Job description
<full text>

---

## Rejected after screening or interviews
...

## No response
...
```

The default export includes all three groups. A `statuses` filter can narrow it down (for example,
early rejections only). Empty groups are left out.

## Tech Stack

- **Language:** Python 3.12, managed with `uv`
- **Web:** FastAPI. The JSON API under `/api` serves as the backend showcase, with OpenAPI docs at
  `/docs`.
- **UI:** server-rendered Jinja2 templates under `/` with htmx 2 for partial updates (inline status
  change, adding interactions or links without a full reload). Vanilla JavaScript only where htmx
  doesn't cover it. Minimal CSS. The htmx file lives in `app/web/static/` and isn't loaded from a
  CDN, so the app works offline.
- **Database:** PostgreSQL 16, SQLAlchemy 2.x (ORM, typed), and Alembic migrations
- **Validation:** Pydantic v2
- **Tests:** pytest and httpx2 (FastAPI TestClient), running against a real Postgres from Compose (no SQLite stand-in)
- **Lint and format:** ruff (lint and format) and mypy (strict on `app/`)
- **Runtime:** a Docker multi-stage image (non-root) and Docker Compose (`app` and `db`, with a
  named volume for data)

## Commands

```
Start everything:     docker compose up --build            # app on http://localhost:8000
Run migrations:       docker compose run --rm app alembic upgrade head
New migration:        docker compose run --rm app alembic revision --autogenerate -m "<msg>"
Tests:                docker compose run --rm app pytest -q
Lint:                 uv run ruff check . && uv run ruff format --check .
Types:                uv run mypy app
Backup DB:            docker compose exec db pg_dump -U tracker tracker > backup.sql
```

A `Makefile` wraps these (`make up`, `make test`, `make lint`, `make backup`).

## Project Structure

```
app/
  main.py            → FastAPI app factory, router wiring
  config.py          → Settings from env (DATABASE_URL)
  db.py              → engine/session setup
  models.py          → SQLAlchemy models
  schemas.py         → Pydantic request/response models
  services/          → domain logic (applications, status, contacts, interactions, follow_up, settings, export)
  api/               → JSON routers (/api/...)
  web/               → HTML routers, templates/ (full pages + htmx partials), static/ (htmx, css, js)
migrations/          → Alembic
tests/
  unit/              → pure logic (follow-up rule, early/late rejection, export rendering)
  integration/       → API + DB through the TestClient against Postgres
docs/intent/         → confirmed intent docs
Dockerfile
compose.yaml
Makefile
.env.example
```

Routes go through services, and services own the domain rules. The API and web routers are thin
and share the same services. All status changes go through one service function, so history can't
be skipped.

## Code Style

```python
OPEN_STATUSES = frozenset({Status.APPLIED, Status.SCREENING, Status.INTERVIEWING})


def needs_follow_up(app: Application, *, today: date, thresholds: Mapping[Status, int]) -> bool:
    """Open application with no activity for longer than its status's threshold."""
    if app.status not in OPEN_STATUSES:
        return False
    return (today - app.last_activity_on).days > thresholds[app.status]
```

- Type hints everywhere, and `mypy --strict` passes on `app/`
- `snake_case` for functions and modules, `PascalCase` for classes, and enums for statuses and
  channels
- Pass `today` in explicitly instead of calling `date.today()` inside logic, so it stays testable
- Comments explain *why*, never restate *what*
- No new dependency without asking (see Boundaries)

## Testing Strategy

- **Unit (`tests/unit`):** follow-up rule edge cases (exactly at the threshold, per-status
  thresholds, no interactions, a back-dated status change counting from its `changed_on`, closed
  statuses), change-date validation (future, before `applied_on`, before the newest change),
  early vs. late rejection classification, and markdown export rendering and grouping.
- **Integration (`tests/integration`):** each API endpoint runs end to end against Postgres, with a
  transaction rolled back per test. This covers CRUD, status history being written on create and
  change with a given or default `changed_on`, rejected invalid change dates, reading and updating
  thresholds (including out-of-range values), duplicate `409` on create and edit (including case and whitespace variants), filtering,
  cascade deletes, the follow-up endpoint, and export.
- **Web UI:** smoke tests that each page and htmx partial returns 200 and shows the key fields. No
  browser automation in stage 1.
- **Coverage:** ≥ 85% on `app/services`. No hard target elsewhere.
- Write tests first for domain rules (follow-up, status history, duplicates, export).

## Boundaries

- **Always:** run `make lint test` before a commit; add an Alembic migration for every schema
  change; validate all input with Pydantic; keep secrets in `.env` (git-ignored) with
  `.env.example` committed; route every status change through the status service.
- **Ask first:** adding a dependency beyond the stack above; changing the data model beyond this
  spec; anything from stages 2–4 or the backlog.
- **Never:** commit `.env` or real application data; call an LLM or any external service from the
  app; load assets from a CDN; drop or rewrite migrations that already ran on the user's data;
  edit status history rows; skip or delete failing tests to get to green.

## Success Criteria

1. `docker compose up --build` on a clean machine brings up the app and Postgres. The app runs
   migrations, and `http://localhost:8000` loads with no network access needed beyond the Docker
   images.
2. From the application page I can see the title, company, status, status history, applied date,
   full job description, links, notes, company contacts, and interactions without navigating
   elsewhere. Changing status there, with a date I pick or today by default, updates the page in
  place (htmx) and adds a history entry with that date.
3. Creating or editing an application into an existing company + title + applied date (ignoring
   case and whitespace in the title) is refused, with a link to the existing application.
4. The follow-up page lists exactly the open applications past their status's threshold, oldest
   first. Changing a threshold on the settings page changes the list right away, with no restart.
   Unit tests cover the boundary at exactly the threshold for each status.
5. The export downloads a `.md` file in the format above, with early rejections, late rejections,
   and no-response applications in separate groups.
6. Data survives `docker compose down` and `up` (named volume), and `make backup` produces a
   restorable dump.
7. `make lint test` passes, with ≥ 85% coverage on `app/services`.
8. The user stops using the spreadsheet: all new applications go in the tracker for one week.

## Out of Scope (Stage 1)

CSV import (backlog); LLM calls inside the app; push, email, or desktop notifications;
authentication or multiple users; scraping job descriptions from URLs; a polished or JS-heavy
frontend; cloud deployment, CI/CD,
Kubernetes, Terraform (stages 2–4); resume storage or versioning.

## Open Questions

None.
