from datetime import date
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.clock import get_today

TODAY = date(2026, 10, 17)


@pytest.fixture(autouse=True)
def pinned_today(app: FastAPI) -> None:
    app.dependency_overrides[get_today] = lambda: TODAY


def create(client: TestClient, title: str, applied_on: str, **extra: Any) -> int:
    response = client.post(
        "/api/applications",
        json={"company": "Acme", "title": title, "applied_on": applied_on, **extra},
    )
    assert response.status_code == 201, response.text
    application_id: int = response.json()["id"]
    return application_id


def follow_up_titles(client: TestClient) -> list[str]:
    response = client.get("/api/follow-ups")
    assert response.status_code == 200
    return [row["title"] for row in response.json()]


def test_lists_exactly_the_quiet_open_applications_oldest_first(client: TestClient) -> None:
    create(client, "Applied 8 days ago", "2026-10-09")
    create(client, "Applied 7 days ago", "2026-10-10")
    create(client, "Applied 30 days ago", "2026-09-17")
    create(client, "Rejected long ago", "2026-08-01", status="rejected")
    screening = create(client, "Screening 6 days ago", "2026-09-01")
    client.post(
        f"/api/applications/{screening}/status",
        json={"status": "screening", "changed_on": "2026-10-11"},
    )
    talking = create(client, "Applied long ago but emailed yesterday", "2026-09-01")
    client.post(
        f"/api/applications/{talking}/interactions",
        json={"channel": "email", "occurred_on": "2026-10-16"},
    )

    assert follow_up_titles(client) == [
        "Applied 30 days ago",
        "Applied 8 days ago",
        "Screening 6 days ago",
    ]


def test_follow_up_rows_show_last_activity_and_days_overdue(client: TestClient) -> None:
    create(client, "Applied 10 days ago", "2026-10-07")

    row = client.get("/api/follow-ups").json()[0]

    assert row["status"] == "applied"
    assert row["company"] == "Acme"
    assert row["last_activity_on"] == "2026-10-07"
    assert row["days_since_activity"] == 10
    assert row["threshold_days"] == 7
    assert row["days_overdue"] == 3


def test_changing_a_threshold_changes_the_list_immediately(client: TestClient) -> None:
    create(client, "Applied 10 days ago", "2026-10-07")
    assert follow_up_titles(client) == ["Applied 10 days ago"]

    client.put("/api/settings/follow-up", json={"applied": 14, "screening": 5, "interviewing": 3})

    assert follow_up_titles(client) == []


def test_changing_a_threshold_on_the_settings_page_changes_the_follow_up_page(
    client: TestClient,
) -> None:
    create(client, "Applied 10 days ago", "2026-10-07")
    assert "Applied 10 days ago" in client.get("/follow-ups").text

    client.post("/settings", data={"applied": "14", "screening": "5", "interviewing": "3"})

    page = client.get("/follow-ups").text
    assert "Applied 10 days ago" not in page
    assert "Nothing to follow up" in page


def test_follow_up_page_shows_days_overdue(client: TestClient) -> None:
    create(client, "Applied 10 days ago", "2026-10-07")

    page = client.get("/follow-ups").text

    assert "2026-10-07" in page
    assert "3 days overdue" in page


def test_list_page_has_a_last_activity_column(client: TestClient) -> None:
    application = create(client, "SRE", "2026-09-12")
    client.post(
        f"/api/applications/{application}/interactions",
        json={"channel": "phone", "occurred_on": "2026-10-03"},
    )

    page = client.get("/").text

    assert "Last activity" in page
    assert "2026-10-03" in page
