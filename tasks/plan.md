# Implementation Plan: Job Application Tracker — Stage 1

Spec: [SPEC.md](../SPEC.md) (approved 2026-10-17)
Tasks: tracked as GitHub issues, one per task (issue #N = Task N), grouped into phase
milestones, with "blocked by" links for dependencies: <https://github.com/EnriqueRE/job-application-tracker/issues>
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
#1 skeleton ─► #2 docker ─► #3 db + harness ─┬─► #16 backup + README
                                             ▼
                                #4 create/view API + duplicates
                                             ▼
                                #5 web shell + list page ─┬─► #12 search/filter
                                             │            ├─► #13 thresholds + settings ─┐
                                             ▼            └─────────────┐                │
                                #6 new form + detail page               │                │
                     ┌──────────┬────────────┼───────────┐              │                │
                     ▼          ▼            ▼           ▼              │                │
                #7 edit/del  #8 status   #9 links   #10 contacts        │                │
                                │                        ▼              │                │
                                │                   #11 interactions    │                │
                                ├─────────► #15 export ◄────────────────┘                │
                                └───────────────────┬────────────────────────────────────┘
                                                    ▼
                                    #14 follow-up list (+ #11)
```

After #6, the branches (#7, #8, #9, #10) are independent and can be done in any order, as are
#12 and #13 after #5. Issue order is the recommended order.

## Task List

The issues hold each task's description, acceptance criteria, verification, files, and size.
This section is only an index.

### [Phase 1: Foundation](https://github.com/EnriqueRE/job-application-tracker/milestone/1) (closed)
- [x] [#1](https://github.com/EnriqueRE/job-application-tracker/issues/1) Python project skeleton
- [x] [#2](https://github.com/EnriqueRE/job-application-tracker/issues/2) Docker image, Compose, and Makefile
- [x] [#3](https://github.com/EnriqueRE/job-application-tracker/issues/3) Database session, Alembic, and test harness

Checkpoint: green from a clean clone; reviewed with the owner.

### [Phase 2: The application record](https://github.com/EnriqueRE/job-application-tracker/milestone/2)
- [ ] [#4](https://github.com/EnriqueRE/job-application-tracker/issues/4) Create and view an application (API), with duplicate protection
- [ ] [#5](https://github.com/EnriqueRE/job-application-tracker/issues/5) Web shell and application list page
- [ ] [#6](https://github.com/EnriqueRE/job-application-tracker/issues/6) New-application form and detail page
- [ ] [#7](https://github.com/EnriqueRE/job-application-tracker/issues/7) Edit and delete an application
- [ ] [#8](https://github.com/EnriqueRE/job-application-tracker/issues/8) Status change with a chosen date, plus history (TDD)

Checkpoint: spec success criteria 3 and (partly) 2 are met, so real applications can be logged.
Review with the owner.

### [Phase 3: People and context](https://github.com/EnriqueRE/job-application-tracker/milestone/3)
- [ ] [#9](https://github.com/EnriqueRE/job-application-tracker/issues/9) Links on an application
- [ ] [#10](https://github.com/EnriqueRE/job-application-tracker/issues/10) Company contacts
- [ ] [#11](https://github.com/EnriqueRE/job-application-tracker/issues/11) Interactions log
- [ ] [#12](https://github.com/EnriqueRE/job-application-tracker/issues/12) List filtering and search

Checkpoint: spec success criterion 2 is fully met (interview prep on one page). Review with the
owner.

### [Phase 4: Follow-up and export](https://github.com/EnriqueRE/job-application-tracker/milestone/4)
- [ ] [#13](https://github.com/EnriqueRE/job-application-tracker/issues/13) Follow-up thresholds and settings page
- [ ] [#14](https://github.com/EnriqueRE/job-application-tracker/issues/14) Follow-up list and last-activity column (TDD)
- [ ] [#15](https://github.com/EnriqueRE/job-application-tracker/issues/15) Markdown export for resume review (TDD)
- [ ] [#16](https://github.com/EnriqueRE/job-application-tracker/issues/16) Backup, persistence check, and README
- [ ] [#17](https://github.com/EnriqueRE/job-application-tracker/issues/17) Checkpoint: Stage 1 complete (blocked by #4–#16, plus a week of real use)

### Changes from the first breakdown
- Old Task 5 was split into #5 (shell and list) and #6 (form and detail), because it touched about
  8 files. Everything after it shifted up by one.
- The last-activity column moved from search/filter (#12) to the follow-up task (#14), because it
  needs status history and the follow-up rule.
- Settings (#13) and export (#15) now depend on the web shell (#5), since both add pages.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| ~~The Docker Compose v2 plugin isn't installed~~ | Resolved | Installed before #2. |
| The repo sits on `/mnt/c` (Windows filesystem under WSL), so bind mounts and file watching are slow and reload may miss changes | Medium | Recommended: move the repo to the WSL filesystem (`~/projects/...`). If it stays, use polling reload and don't bind-mount `.venv`. |
| Alembic autogenerate misses the expression index and CHECK constraints | Medium: duplicates slip through | Write those migrations by hand, and an integration test asserts a `409` on case and whitespace variants. |
| Back-dating rules interact with history ordering | Medium | Pure `validate_change_date` covered by unit tests for every boundary, plus a DB-level ordering test. |
| Test isolation leaks into real data | High | A separate `tracker_test` DB and a guard in conftest that refuses to run unless the database name ends in `_test`. |
| Local Python is 3.14 but the image is 3.12 | Low | Pin `requires-python = ">=3.12,<3.13"` and let `uv` manage 3.12 locally, so lint and type checks match the container. |
| Scope creep into stage 2+ (CI, K8s) while the tracker isn't usable yet | Medium | Boundaries say "ask first". Stage 2 starts only after the stage 1 checkpoint and a week of real use. |

## Open Questions

1. **Repo location:** the repo is still on `/mnt/c`. Move it to the WSL filesystem before Docker
   work gets heavier (recommended), or keep it there?

Resolved: git initialized and pushed to GitHub, dependencies approved (with `httpx2` in place of
`httpx`), and tasks tracked in GitHub Issues.
