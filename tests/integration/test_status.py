from datetime import date, timedelta

from fastapi.testclient import TestClient

APPLIED_ON = "2026-09-12"


def create(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "company": "Acme Corp",
        "title": "Platform Engineer",
        "applied_on": APPLIED_ON,
    }
    payload.update(overrides)
    response = client.post("/api/applications", json=payload)
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def history(body: dict[str, object]) -> list[tuple[str | None, str, str]]:
    rows = body["history"]
    assert isinstance(rows, list)
    return [(r["from_status"], r["to_status"], r["changed_on"]) for r in rows]


def test_status_change_without_a_date_is_recorded_today(client: TestClient) -> None:
    created = create(client)

    response = client.post(
        f"/api/applications/{created['id']}/status", json={"status": "screening"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "screening"
    assert history(body) == [
        (None, "applied", APPLIED_ON),
        ("applied", "screening", date.today().isoformat()),
    ]


def test_back_dated_status_change_keeps_its_date(client: TestClient) -> None:
    created = create(client)

    body = client.post(
        f"/api/applications/{created['id']}/status",
        json={"status": "rejected", "changed_on": "2026-09-14"},
    ).json()

    assert history(body)[-1] == ("applied", "rejected", "2026-09-14")


def test_setting_the_same_status_again_records_nothing(client: TestClient) -> None:
    created = create(client)

    body = client.post(
        f"/api/applications/{created['id']}/status", json={"status": "applied"}
    ).json()

    assert len(history(body)) == 1


def test_history_is_ordered_by_change_date_then_recording_time(client: TestClient) -> None:
    created = create(client)
    url = f"/api/applications/{created['id']}/status"
    client.post(url, json={"status": "screening", "changed_on": "2026-09-20"})
    client.post(url, json={"status": "interviewing", "changed_on": "2026-09-20"})
    client.post(url, json={"status": "offer", "changed_on": "2026-10-01"})

    body = client.get(f"/api/applications/{created['id']}").json()

    assert [to for _, to, _ in history(body)] == ["applied", "screening", "interviewing", "offer"]


def test_invalid_change_dates_are_422_and_change_nothing(client: TestClient) -> None:
    created = create(client)
    url = f"/api/applications/{created['id']}/status"
    client.post(url, json={"status": "screening", "changed_on": "2026-09-20"})
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    for changed_on in (tomorrow, "2026-09-11", "2026-09-19"):
        response = client.post(url, json={"status": "rejected", "changed_on": changed_on})
        assert response.status_code == 422, changed_on

    body = client.get(f"/api/applications/{created['id']}").json()
    assert body["status"] == "screening"
    assert len(history(body)) == 2


def test_unknown_status_is_422(client: TestClient) -> None:
    created = create(client)

    response = client.post(f"/api/applications/{created['id']}/status", json={"status": "ghosted"})

    assert response.status_code == 422


def test_status_change_on_unknown_application_is_404(client: TestClient) -> None:
    response = client.post("/api/applications/999999/status", json={"status": "screening"})

    assert response.status_code == 404


def test_applied_date_cannot_be_edited_past_the_first_status_change(client: TestClient) -> None:
    created = create(client)
    client.post(
        f"/api/applications/{created['id']}/status",
        json={"status": "screening", "changed_on": "2026-09-20"},
    )

    response = client.patch(f"/api/applications/{created['id']}", json={"applied_on": "2026-09-21"})

    assert response.status_code == 422


def test_htmx_status_change_returns_the_updated_status_section(client: TestClient) -> None:
    created = create(client)

    response = client.post(
        f"/applications/{created['id']}/status",
        data={"status": "interviewing", "changed_on": "2026-09-30"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "applied → interviewing" in response.text
    assert "2026-09-30" in response.text


def test_htmx_status_change_with_a_blank_date_uses_today(client: TestClient) -> None:
    created = create(client)

    response = client.post(
        f"/applications/{created['id']}/status",
        data={"status": "screening", "changed_on": ""},
        headers={"HX-Request": "true"},
    )

    assert date.today().isoformat() in response.text


def test_htmx_status_change_with_a_bad_date_shows_the_error_in_place(client: TestClient) -> None:
    created = create(client)

    response = client.post(
        f"/applications/{created['id']}/status",
        data={"status": "screening", "changed_on": "2026-09-01"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 422
    assert "<html" not in response.text
    assert 'class="error"' in response.text


def test_plain_form_status_change_redirects_to_the_detail_page(client: TestClient) -> None:
    created = create(client)

    response = client.post(
        f"/applications/{created['id']}/status",
        data={"status": "screening"},
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_detail_page_has_the_status_form_defaulting_to_today(client: TestClient) -> None:
    created = create(client)

    page = client.get(f"/applications/{created['id']}").text

    assert f'hx-post="/applications/{created["id"]}/status"' in page
    assert f'value="{date.today().isoformat()}"' in page
