from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, StatusChange


def make_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "company": "Acme Corp",
        "title": "Senior Platform Engineer",
        "job_url": "https://acme.example/jobs/1",
        "job_description": "Run Kubernetes.\nWrite Terraform.",
        "location": "Remote",
        "source": "LinkedIn",
        "applied_on": "2026-09-12",
        "notes": "Referred by nobody",
    }
    payload.update(overrides)
    return payload


def test_create_returns_application_with_company_and_initial_history(client: TestClient) -> None:
    response = client.post("/api/applications", json=make_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Senior Platform Engineer"
    assert body["company"]["name"] == "Acme Corp"
    assert body["status"] == "applied"
    assert body["job_description"] == "Run Kubernetes.\nWrite Terraform."
    assert body["history"] == [
        {
            "from_status": None,
            "to_status": "applied",
            "changed_on": "2026-09-12",
            "recorded_at": body["history"][0]["recorded_at"],
        }
    ]


def test_create_with_only_required_fields(client: TestClient) -> None:
    response = client.post(
        "/api/applications",
        json={"company": "Acme", "title": "SRE", "applied_on": "2026-09-12"},
    )

    assert response.status_code == 201
    assert response.json()["job_description"] == ""


def test_get_returns_created_application(client: TestClient) -> None:
    created = client.post("/api/applications", json=make_payload()).json()

    response = client.get(f"/api/applications/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_application_is_404(client: TestClient) -> None:
    assert client.get("/api/applications/999999").status_code == 404


def test_company_name_is_matched_ignoring_case(client: TestClient) -> None:
    first = client.post("/api/applications", json=make_payload(company="Acme")).json()
    second = client.post(
        "/api/applications", json=make_payload(company="  acme ", title="Other role")
    ).json()

    assert second["company"]["id"] == first["company"]["id"]
    assert second["company"]["name"] == "Acme"


def test_duplicate_ignoring_title_case_and_whitespace_is_409(client: TestClient) -> None:
    first = client.post("/api/applications", json=make_payload(title="Senior  Engineer")).json()

    response = client.post(
        "/api/applications", json=make_payload(company="ACME CORP", title=" senior  engineer ")
    )

    assert response.status_code == 409
    assert response.json()["existing_id"] == first["id"]


def test_same_role_on_a_different_date_is_not_a_duplicate(client: TestClient) -> None:
    client.post("/api/applications", json=make_payload())

    response = client.post("/api/applications", json=make_payload(applied_on="2026-09-13"))

    assert response.status_code == 201


def test_blank_company_or_title_is_422(client: TestClient) -> None:
    assert client.post("/api/applications", json=make_payload(company="  ")).status_code == 422
    assert client.post("/api/applications", json=make_payload(title="")).status_code == 422


def test_invalid_job_url_is_422(client: TestClient) -> None:
    response = client.post("/api/applications", json=make_payload(job_url="not a url"))

    assert response.status_code == 422


def test_applied_date_in_the_future_is_422(client: TestClient) -> None:
    tomorrow = date.fromordinal(date.today().toordinal() + 1).isoformat()

    response = client.post("/api/applications", json=make_payload(applied_on=tomorrow))

    assert response.status_code == 422


def test_list_returns_applications_newest_applied_first(client: TestClient) -> None:
    client.post("/api/applications", json=make_payload(title="Older", applied_on="2026-09-01"))
    client.post("/api/applications", json=make_payload(title="Newer", applied_on="2026-09-20"))

    response = client.get("/api/applications")

    assert response.status_code == 200
    assert [a["title"] for a in response.json()] == ["Newer", "Older"]


def test_patch_updates_fields_and_updated_at(client: TestClient) -> None:
    created = client.post("/api/applications", json=make_payload()).json()

    response = client.patch(
        f"/api/applications/{created['id']}", json={"notes": "Recruiter called", "location": ""}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["notes"] == "Recruiter called"
    assert body["location"] == ""
    assert body["title"] == created["title"]
    assert body["updated_at"] > created["updated_at"]


def test_patch_can_move_the_application_to_another_company(client: TestClient) -> None:
    created = client.post("/api/applications", json=make_payload()).json()

    body = client.patch(f"/api/applications/{created['id']}", json={"company": "Globex"}).json()

    assert body["company"]["name"] == "Globex"
    assert body["company"]["id"] != created["company"]["id"]


def test_patch_into_an_existing_key_is_409(client: TestClient) -> None:
    first = client.post("/api/applications", json=make_payload(title="SRE")).json()
    second = client.post("/api/applications", json=make_payload(title="Platform")).json()

    response = client.patch(f"/api/applications/{second['id']}", json={"title": " sre "})

    assert response.status_code == 409
    assert response.json()["existing_id"] == first["id"]
    assert client.get(f"/api/applications/{second['id']}").json()["title"] == "Platform"


def test_patch_with_status_is_422(client: TestClient) -> None:
    created = client.post("/api/applications", json=make_payload()).json()

    response = client.patch(f"/api/applications/{created['id']}", json={"status": "offer"})

    assert response.status_code == 422


def test_patch_cannot_null_a_required_field(client: TestClient) -> None:
    created = client.post("/api/applications", json=make_payload()).json()

    response = client.patch(f"/api/applications/{created['id']}", json={"title": None})

    assert response.status_code == 422


def test_patch_unknown_application_is_404(client: TestClient) -> None:
    assert client.patch("/api/applications/999999", json={"notes": "x"}).status_code == 404


def test_delete_removes_application_and_history_but_keeps_company(
    client: TestClient, db_session: Session
) -> None:
    created = client.post("/api/applications", json=make_payload()).json()

    response = client.delete(f"/api/applications/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/applications/{created['id']}").status_code == 404
    history = db_session.scalar(
        select(func.count()).where(StatusChange.application_id == created["id"])
    )
    assert history == 0
    assert db_session.get(Company, created["company"]["id"]) is not None


def test_delete_unknown_application_is_404(client: TestClient) -> None:
    assert client.delete("/api/applications/999999").status_code == 404


def test_patch_applied_date_into_the_future_is_422(client: TestClient) -> None:
    created = client.post("/api/applications", json=make_payload()).json()
    tomorrow = date.fromordinal(date.today().toordinal() + 1).isoformat()

    response = client.patch(f"/api/applications/{created['id']}", json={"applied_on": tomorrow})

    assert response.status_code == 422
