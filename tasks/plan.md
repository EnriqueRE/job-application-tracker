# Implementation Plan: Job Application Tracker — Stage 1

Spec: [SPEC.md](../SPEC.md) (approved 2026-10-17)
Tasks: [tasks/todo.md](todo.md)
Status: APPROVED (2026-10-17)

## Overview

Build the stage 1 local tracker as thin vertical slices. After each slice, the app runs under
Docker Compose with one more thing you can actually use. The order is foundation first, then the
application record and the interview-prep page (the most urgent need), then status history,
links, contacts, and interactions, and finally follow-ups, settings, and the export. You could
start logging real applications after Phase 2.

## Architecture Decisions

- **Sync SQLAlchemy, not async.** For a single user, async gains nothing and makes sessions, tests,
  and Alembic harder. FastAPI runs sync endpoints in a threadpool. This is easy to revisit later
  (and makes a good story for an interview).
- **One service layer, two thin router sets.** `app/services/*` holds every domain rule. `app/api`
  (JSON) and `app/web` (HTML and htmx) only parse input and render output. Integration tests mostly
  hit `/api`, and web tests are smoke tests.
- **Status changes have one entry point.** `services.status.change_status()` is the only code that
  writes `applications.status`, and it always inserts a `status_changes` row in the same
  transaction. The create flow calls it for the initial row.
- **Duplicate key is a functional unique index** on `(company_id, lower(trim(title)), applied_on)`.
  Alembic autogenerate doesn't detect expression indexes, so this migration is written by hand.
  The service catches `IntegrityError` and turns it into a `DuplicateApplication` error that
  carries the existing ID, which becomes a `409` (API) or an inline message with a link (web).
- **Thresholds live in the database and are read on every request.** No caching, so edits take
  effect immediately (success criterion 4). The table is seeded in a migration.
- **Pure functions for rules.** `needs_follow_up`, `classify_rejection`, `validate_change_date`,
  and `render_export` take plain values (including `today`), so unit tests need no database.
- **Migrations run at container start** (`docker/start.sh`, the image's default command, runs
  `alembic upgrade head` and then uvicorn), so `docker compose up` alone works on a clean machine.
  One-off `docker compose run app <cmd>` replaces the command, so tests never migrate the real DB.
- **Tests use a separate `tracker_test` database** in the same Postgres container, created by an
  init script. Each test runs in a transaction that is rolled back afterwards, so real data is
  never touched.
- **htmx is vendored** into `app/web/static/htmx.min.js` (pinned 2.x version), with no CDN.

### Runtime dependencies (approve as a set)

`fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `psycopg[binary]` (v3 driver), `alembic`,
`pydantic-settings`, `jinja2`, `python-multipart` (needed for HTML form posts).
Dev: `pytest`, `pytest-cov`, `httpx2` (replaced `httpx`, which Starlette deprecated for TestClient), `ruff`, `mypy`.

## Dependency Graph

```
skeleton + compose ──► db + migrations + test harness
                               │
                               ▼
                  applications (create/view, duplicates)
                               │
             ┌─────────────┬───┴──────────┬───────────────┐
             ▼             ▼              ▼               ▼
        edit/delete   status+history    links     contacts ─► interactions
                           │                                       │
                           ├───────────────────┬───────────────────┘
                           ▼                   ▼
                  settings (thresholds) ─► follow-up list
                           │
                           ▼
                        export (needs history for early/late)
```

After Task 4, the branches that fan out (edit/delete, status, links, contacts) are independent
and could be done in any order. The list order is the recommended one.

## Phases

**Phase 1: Foundation (Tasks 1–3).** The repo builds, the containers run, migrations apply, and
the test harness works against Postgres.

**Phase 2: The application record (Tasks 4–7).** Create, view, edit, and delete applications,
with duplicate protection, plus status changes with back-dated history. The real application
starts here.

**Phase 3: People and context (Tasks 8–11).** Links, contacts, interactions, and list
search/filter. After this, the interview-prep page is complete.

**Phase 4: Follow-up and export (Tasks 12–15).** Thresholds and the settings page, the follow-up
list, the markdown export, and backup with a persistence check and README.

There's a checkpoint after each phase. Details and acceptance criteria are in
[todo.md](todo.md).

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The Docker Compose v2 plugin isn't installed (`docker compose` fails in this WSL environment) | High: blocks Task 2 | Prerequisite: install `docker-compose-plugin`, or enable WSL integration in Docker Desktop. Checked at the start of Task 2. |
| The repo sits on `/mnt/c` (Windows filesystem under WSL), so bind mounts and file watching are slow and reload may miss changes | Medium | Recommended: move the repo to the WSL filesystem (`~/projects/...`). If it stays, use polling reload and don't bind-mount `.venv`. |
| Alembic autogenerate misses the expression index and CHECK constraints | Medium: duplicates slip through | Write those migrations by hand, and an integration test asserts a `409` on case and whitespace variants. |
| Back-dating rules interact with history ordering | Medium | Pure `validate_change_date` covered by unit tests for every boundary, plus a DB-level ordering test. |
| Test isolation leaks into real data | High | A separate `tracker_test` DB and a guard in conftest that refuses to run unless the database name ends in `_test`. |
| Local Python is 3.14 but the image is 3.12 | Low | Pin `requires-python = ">=3.12,<3.13"` and let `uv` manage 3.12 locally, so lint and type checks match the container. |
| Scope creep into stage 2+ (CI, K8s) while the tracker isn't usable yet | Medium | Boundaries say "ask first". Stage 2 starts only after the stage 1 checkpoint and a week of real use. |

## Open Questions

1. **Git:** the folder isn't a git repository yet. Should Task 1 run `git init` and commit at each
   checkpoint? A public GitHub remote also matters for the portfolio. Should I create one, or will
   you?
2. **Repo location:** do you want to move the repo off `/mnt/c` into the WSL filesystem before we
   start (recommended), or keep it where it is?
3. **Dependencies:** do you approve the runtime and dev dependency list above?
