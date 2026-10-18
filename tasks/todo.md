# Tasks: Job Application Tracker — Stage 1

Plan: [plan.md](plan.md) · Spec: [../SPEC.md](../SPEC.md)

Standard verification for every task (in addition to the task's own checks):
`make lint` (ruff + mypy strict) and `make test` both pass.

---

## Phase 1: Foundation

### Task 1: Python project skeleton
**Description:** Create the `uv` project, a FastAPI app factory with `GET /healthz`, settings
loaded from env, and the ruff, mypy, and pytest configs. No database yet.

**Acceptance criteria:**
- [ ] `uv run uvicorn app.main:app` serves `GET /healthz` → `{"status": "ok"}`
- [ ] `requires-python` is pinned to 3.12, and the dependencies match the approved list in the plan
- [ ] `.gitignore` covers `.env`, `.venv`, `__pycache__`, `*.sql` backups

**Verification:** `uv run pytest -q` (one healthz test) · `uv run ruff check . && uv run mypy app`

**Dependencies:** None
**Files:** `pyproject.toml`, `app/main.py`, `app/config.py`, `tests/test_health.py`, `.gitignore`
**Scope:** S

### Task 2: Docker image, Compose, and Makefile
**Description:** A multi-stage Dockerfile (non-root, `uv`-built venv), `compose.yaml` with `app`
and `db` (Postgres 16, a healthcheck, a named volume, and an init script that creates
`tracker_test`), `.env.example`, and a `Makefile` with `up`, `down`, `test`, `lint`, and `logs`.

**Acceptance criteria:**
- [ ] The prerequisite `docker compose version` works (see plan risks)
- [ ] `make up` builds and starts both containers, and `curl localhost:8000/healthz` returns ok
- [ ] The app container runs as a non-root user and waits for the db healthcheck

**Verification:** `make up && curl -f localhost:8000/healthz` · `docker compose exec app id -u` ≠ 0

**Dependencies:** 1
**Files:** `Dockerfile`, `compose.yaml`, `docker/db-init/01-test-db.sql`, `.env.example`, `Makefile`
**Scope:** M

### Task 3: Database session, Alembic, and test harness
**Description:** Sync SQLAlchemy engine and session dependency, Alembic configured from settings,
an entrypoint that runs `alembic upgrade head` before uvicorn, and a pytest `conftest` with a
per-test transaction rolled back against `tracker_test` (with a guard that refuses any other
database). `/healthz` checks the database.

**Acceptance criteria:**
- [ ] Container start applies migrations automatically (an empty baseline revision for now)
- [ ] `make test` runs inside the container against `tracker_test`, and the guard fails fast if
  pointed at `tracker`
- [ ] `/healthz` returns 503 if the database is unreachable

**Verification:** `make test` · stop `db` and confirm `/healthz` returns 503

**Dependencies:** 2
**Files:** `app/db.py`, `migrations/` (env.py, baseline), `alembic.ini`, `docker/entrypoint.sh`,
`tests/conftest.py`
**Scope:** M

### ✅ Checkpoint: Foundation
- [ ] `make up`, `make lint`, and `make test` are all green from a clean clone
- [ ] Review with the user before continuing

---

## Phase 2: The application record

### Task 4: Create and view an application (API), with duplicate protection
**Description:** Models and migration for `companies`, `applications`, and `status_changes`, with
the hand-written functional unique index. Service `create_application` creates the company if
needed and writes the initial status row (`changed_on = applied_on`) through
`change_status`. `POST /api/applications` and `GET /api/applications/{id}`, with a `409` and
`existing_id` on duplicates.

**Acceptance criteria:**
- [ ] Creating an application returns 201 with its company and a single initial history entry
- [ ] Company names match ignoring case ("acme" reuses "Acme")
- [ ] The same company + `" Senior  Engineer "` vs. `"senior engineer"` (case/trim) + the same date
  → 409 with `existing_id`. A different date → 201.

**Verification:** integration tests in `tests/integration/test_applications.py`

**Dependencies:** 3
**Files:** `app/models.py`, `app/schemas.py`, `app/services/applications.py`,
`app/api/applications.py`, migration, test
**Scope:** M

### Task 5: Web shell, application list, new form, and detail page
**Description:** Base Jinja layout with vendored htmx and minimal CSS. Pages: list (`/`), new
(`/applications/new`), and detail (`/applications/{id}`), all calling the same services. A
duplicate shows an inline message linking to the existing application.

**Acceptance criteria:**
- [ ] I can create an application in the browser and land on its detail page showing every field
  stored so far (including the job description, with line breaks preserved)
- [ ] A duplicate submission keeps the form filled in and shows the "already exists → link" message
- [ ] The page loads no external URLs (check the network tab or `grep -r "https://" app/web`)

**Verification:** web smoke tests (200s and key text) · manual browser check

**Dependencies:** 4
**Files:** `app/web/routes.py`, `app/web/templates/{base,list,form,detail}.html`,
`app/web/static/{htmx.min.js,app.css}`, `tests/integration/test_web.py`
**Scope:** M

### Task 6: Edit and delete an application
**Description:** `PATCH` and `DELETE /api/applications/{id}`, plus the web edit form and delete
button. An edit that creates a duplicate is refused. Delete cascades to history (and, later,
links and interactions). Status isn't editable here, since that goes through Task 7.

**Acceptance criteria:**
- [ ] Editing fields updates `updated_at`, and editing into an existing key → 409 / inline message
- [ ] Deleting removes the application and its history rows, and the company remains
- [ ] `PATCH` with a `status` field is rejected (422)

**Verification:** integration tests · manual edit and delete in the browser

**Dependencies:** 4, 5
**Files:** `app/services/applications.py`, `app/api/applications.py`, `app/web/routes.py`,
`app/web/templates/form.html`, tests
**Scope:** M

### Task 7: Status change with a chosen date, plus history (TDD)
**Description:** Write a pure `validate_change_date(changed_on, *, today, applied_on,
latest_change_on)` test first. `change_status` service and `POST /api/applications/{id}/status`
`{status, changed_on?}`. An htmx partial on the detail page: a status select with a date input
(defaults to today) that swaps in the updated status and history list. Setting the same status
again records nothing.

**Acceptance criteria:**
- [ ] Unit tests: future date, date before `applied_on`, and date before the latest change are
  each rejected, and dates equal to those boundaries are allowed
- [ ] A change with no date uses today. A back-dated change is stored with that `changed_on`, and
  history is ordered by `(changed_on, recorded_at)`
- [ ] The detail page updates in place without a full reload and shows the new history entry

**Verification:** `tests/unit/test_status_rules.py` · integration tests · manual htmx check

**Dependencies:** 4, 5
**Files:** `app/services/status.py`, `app/api/applications.py`, `app/web/routes.py`,
`app/web/templates/_status.html`, tests
**Scope:** M

### ✅ Checkpoint: The application record
- [ ] Spec success criteria 3 and (partly) 2 are met
- [ ] Ready to start logging real applications. Review with the user.

---

## Phase 3: People and context

### Task 8: Links on an application
**Description:** Model and migration for `app_links`, add/remove via API, and an htmx partial on
the detail page.

**Acceptance criteria:**
- [ ] I can add a labeled link (URL validated) and remove it, without a page reload
- [ ] Deleting the application deletes its links

**Verification:** integration tests · manual check
**Dependencies:** 5 · **Files:** models, migration, `app/services/links.py`, API, `_links.html`,
tests · **Scope:** S–M

### Task 9: Company contacts
**Description:** Model and migration for `contacts`, CRUD via API, a company contacts page, and
contacts listed on the application detail page (all contacts at that company), with quick-add
from the detail page.

**Acceptance criteria:**
- [ ] A contact added from one application shows on every application at the same company
- [ ] Email and LinkedIn URL are validated when present, and every field except name is optional
- [ ] Deleting a contact doesn't delete interactions (that's tested in Task 10)

**Verification:** integration tests · manual check
**Dependencies:** 5 · **Files:** models, migration, `app/services/contacts.py`,
`app/api/contacts.py`, `_contacts.html`, tests · **Scope:** M

### Task 10: Interactions log
**Description:** Model and migration for `interactions`. Log via API and an htmx form on the
detail page (date, channel, optional contact chosen from the company's contacts, note), shown
newest first.

**Acceptance criteria:**
- [ ] An interaction can only reference a contact at the application's company (422 otherwise)
- [ ] Deleting the contact keeps the interaction, with `contact_id` set to null
- [ ] The detail page lists interactions newest first and updates in place

**Verification:** integration tests · manual check
**Dependencies:** 9 · **Files:** models, migration, `app/services/interactions.py`, API,
`_interactions.html`, tests · **Scope:** M

### Task 11: List filtering and search
**Description:** `GET /api/applications?status=&q=`, with `q` matching company or title ignoring
case. The list page gets a status filter and a search box (htmx swaps the table as you type).

**Acceptance criteria:**
- [ ] Filtering by one or more statuses and `q` works together
- [ ] The list shows company, title, status, applied date, and last activity

**Verification:** integration tests · manual check
**Dependencies:** 5 (and 10 for last activity) · **Files:** services, API, `list.html`,
`_rows.html`, tests · **Scope:** S–M

### ✅ Checkpoint: People and context
- [ ] Spec success criterion 2 is fully met (everything for interview prep is on one page)
- [ ] Review with the user

---

## Phase 4: Follow-up and export

### Task 12: Follow-up thresholds and the settings page
**Description:** Migration creating `follow_up_thresholds` (open statuses only, CHECK 1–365),
seeded with 7/5/3. `GET`/`PUT /api/settings/follow-up` and a settings page form.

**Acceptance criteria:**
- [ ] A fresh database has the defaults 7/5/3
- [ ] Out-of-range or non-open-status values → 422, with the database unchanged
- [ ] Saving on the settings page persists the change, and it survives a restart

**Verification:** integration tests · manual check
**Dependencies:** 3 · **Files:** models, migration, `app/services/settings.py`, API,
`settings.html`, tests · **Scope:** M

### Task 13: Follow-up list (TDD)
**Description:** Pure `last_activity_on(...)` and `needs_follow_up(...)`, written test first.
`GET /api/follow-ups` and a follow-up page, oldest first, showing how many days overdue each one
is. Thresholds are read from the database on each request.

**Acceptance criteria:**
- [ ] Unit tests: exactly at the threshold → not listed, one day past → listed, for each open
  status; closed statuses are never listed; a back-dated status change and a recent interaction
  each move last activity
- [ ] Changing a threshold on the settings page changes the follow-up list immediately
- [ ] The list is sorted by last activity, oldest first

**Verification:** `tests/unit/test_follow_up.py` · integration tests · manual check
**Dependencies:** 7, 10, 12 · **Files:** `app/services/follow_up.py`, API, `follow_up.html`,
tests · **Scope:** M

### Task 14: Markdown export (TDD)
**Description:** Pure `classify_rejection(history)` (early/late) and `render_export(...)`, written
test first. `GET /api/export.md?statuses=` returns a `text/markdown` attachment, and the UI has a
download button with status checkboxes.

**Acceptance criteria:**
- [ ] The output matches the spec format: three groups (early rejected, late rejected, no
  response), with empty groups left out, a status path with dates, and the full job description
- [ ] A rejection whose history touched screening, interviewing, or offer is classified late,
  and anything else is early
- [ ] The `statuses` filter narrows the export, and the downloaded file name includes the date

**Verification:** unit golden-file test for rendering · integration test for the endpoint
**Dependencies:** 7 · **Files:** `app/services/export.py`, API, web button, tests · **Scope:** M

### Task 15: Backup, persistence check, and README
**Description:** `make backup` (a timestamped `pg_dump`) and `make restore FILE=...`. A README
with quickstart, the architecture sketch, and a stage roadmap (it doubles as the portfolio
landing page).

**Acceptance criteria:**
- [ ] `make down && make up` keeps all data (named volume)
- [ ] `make backup` and then restoring into a fresh volume brings back the same applications
- [ ] The README quickstart works from a clean clone

**Verification:** manual run of the backup/restore round trip · README walkthrough
**Dependencies:** 2 · **Files:** `Makefile`, `README.md` · **Scope:** S

### ✅ Checkpoint: Stage 1 complete
- [ ] Spec success criteria 1–7 are verified, with ≥ 85% coverage on `app/services`
- [ ] Criterion 8: one week using only the tracker for new applications
- [ ] Review with the user before writing the stage 2 (CI/CD) spec
