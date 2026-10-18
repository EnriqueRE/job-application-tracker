from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.clock import get_today

TODAY = date(2026, 10, 17)


@pytest.fixture(autouse=True)
def pinned_today(app: FastAPI) -> None:
    app.dependency_overrides[get_today] = lambda: TODAY


def create(client: TestClient, company: str, title: str, *changes: tuple[str, str]) -> None:
    response = client.post(
        "/api/applications",
        json={
            "company": company,
            "title": title,
            "applied_on": "2026-09-01",
            "job_description": f"JD for {title}",
        },
    )
    assert response.status_code == 201
    for status, changed_on in changes:
        changed = client.post(
            f"/api/applications/{response.json()['id']}/status",
            json={"status": status, "changed_on": changed_on},
        )
        assert changed.status_code == 200


@pytest.fixture
def seeded(client: TestClient) -> None:
    create(client, "Acme", "Early reject", ("rejected", "2026-09-03"))
    create(
        client,
        "Globex",
        "Late reject",
        ("screening", "2026-09-05"),
        ("rejected", "2026-09-12"),
    )
    create(client, "Initech", "Ghosted", ("no_response", "2026-10-01"))
    create(client, "Hooli", "Still open")


@pytest.mark.usefixtures("seeded")
def test_export_downloads_markdown_with_all_three_groups(client: TestClient) -> None:
    response = client.get("/api/export.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="applications-for-review-2026-10-17.md"'
    )
    body = response.text
    assert body.startswith("# Applications for resume review (exported 2026-10-17)")
    early = body.index("## Rejected without an interview")
    late = body.index("## Rejected after screening or interviews")
    no_response = body.index("## No response")
    assert early < body.index("Early reject") < late < body.index("Late reject") < no_response
    assert "JD for Ghosted" in body
    assert "Still open" not in body
    assert "applied (2026-09-01) → screening (2026-09-05) → rejected (2026-09-12)" in body


@pytest.mark.usefixtures("seeded")
def test_export_filter_narrows_the_groups(client: TestClient) -> None:
    body = client.get("/api/export.md", params={"statuses": ["rejected_early", "no_response"]}).text

    assert "Early reject" in body
    assert "Ghosted" in body
    assert "Late reject" not in body


def test_export_with_unknown_group_is_422(client: TestClient) -> None:
    assert client.get("/api/export.md", params={"statuses": "applied"}).status_code == 422


def test_export_page_has_the_download_form(client: TestClient) -> None:
    page = client.get("/export").text

    assert 'action="/api/export.md"' in page
    for group in ("rejected_early", "rejected_late", "no_response"):
        assert f'name="statuses" value="{group}" checked' in page
