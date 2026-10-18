from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient


def create_application(client: TestClient, company: str = "Acme") -> dict[str, Any]:
    response = client.post(
        "/api/applications", json={"company": company, "title": "SRE", "applied_on": "2026-09-12"}
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def create_contact(client: TestClient, company_id: int, name: str = "Dana") -> int:
    response = client.post(f"/api/companies/{company_id}/contacts", json={"name": name})
    assert response.status_code == 201
    contact_id: int = response.json()["id"]
    return contact_id


def test_log_interaction_with_a_contact(client: TestClient) -> None:
    application = create_application(client)
    contact_id = create_contact(client, application["company"]["id"])

    response = client.post(
        f"/api/applications/{application['id']}/interactions",
        json={
            "occurred_on": "2026-09-15",
            "channel": "phone",
            "contact_id": contact_id,
            "note": "Recruiter screen, 30 min",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["channel"] == "phone"
    assert body["contact"]["name"] == "Dana"
    assert body["occurred_on"] == "2026-09-15"


def test_interaction_date_defaults_to_today_and_contact_is_optional(client: TestClient) -> None:
    application = create_application(client)

    body = client.post(
        f"/api/applications/{application['id']}/interactions",
        json={"channel": "email", "note": "Sent thank-you"},
    ).json()

    assert body["occurred_on"] == date.today().isoformat()
    assert body["contact"] is None


def test_interaction_in_the_future_or_with_unknown_channel_is_422(client: TestClient) -> None:
    url = f"/api/applications/{create_application(client)['id']}/interactions"
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    assert client.post(url, json={"channel": "email", "occurred_on": tomorrow}).status_code == 422
    assert client.post(url, json={"channel": "carrier pigeon"}).status_code == 422


def test_contact_from_another_company_is_422(client: TestClient) -> None:
    application = create_application(client)
    other_company = create_application(client, company="Globex")["company"]["id"]
    stranger = create_contact(client, other_company, name="Lee")

    response = client.post(
        f"/api/applications/{application['id']}/interactions",
        json={"channel": "email", "contact_id": stranger},
    )

    assert response.status_code == 422


def test_interactions_are_listed_newest_first(client: TestClient) -> None:
    application = create_application(client)
    url = f"/api/applications/{application['id']}/interactions"
    client.post(url, json={"channel": "email", "occurred_on": "2026-09-14", "note": "first"})
    client.post(url, json={"channel": "video", "occurred_on": "2026-09-20", "note": "third"})
    client.post(url, json={"channel": "phone", "occurred_on": "2026-09-14", "note": "second"})

    body = client.get(f"/api/applications/{application['id']}").json()

    assert [i["note"] for i in body["interactions"]] == ["third", "second", "first"]


def test_deleting_the_contact_keeps_the_interaction(client: TestClient) -> None:
    application = create_application(client)
    contact_id = create_contact(client, application["company"]["id"])
    client.post(
        f"/api/applications/{application['id']}/interactions",
        json={"channel": "linkedin", "contact_id": contact_id, "note": "Connected"},
    )

    client.delete(f"/api/contacts/{contact_id}")

    interactions = client.get(f"/api/applications/{application['id']}").json()["interactions"]
    assert len(interactions) == 1
    assert interactions[0]["contact"] is None
    assert interactions[0]["note"] == "Connected"


def test_delete_interaction(client: TestClient) -> None:
    application = create_application(client)
    interaction = client.post(
        f"/api/applications/{application['id']}/interactions", json={"channel": "other"}
    ).json()
    url = f"/api/applications/{application['id']}/interactions/{interaction['id']}"

    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404


def test_htmx_log_interaction_updates_the_section(client: TestClient) -> None:
    application = create_application(client)
    contact_id = create_contact(client, application["company"]["id"])

    response = client.post(
        f"/applications/{application['id']}/interactions",
        data={
            "occurred_on": "2026-09-16",
            "channel": "video",
            "contact_id": str(contact_id),
            "note": "Panel interview",
        },
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "Panel interview" in response.text
    assert "Dana" in response.text


def test_htmx_log_interaction_with_blank_contact_and_date(client: TestClient) -> None:
    application = create_application(client)

    response = client.post(
        f"/applications/{application['id']}/interactions",
        data={"occurred_on": "", "channel": "email", "contact_id": "", "note": "Follow-up"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert date.today().isoformat() in response.text


def test_detail_page_offers_only_this_companys_contacts(client: TestClient) -> None:
    application = create_application(client)
    create_contact(client, application["company"]["id"], name="Dana")
    other_company = create_application(client, company="Globex")["company"]["id"]
    create_contact(client, other_company, name="Lee")

    page = client.get(f"/applications/{application['id']}").text

    assert 'id="interactions"' in page
    assert ">Dana</option>" in page
    assert ">Lee</option>" not in page
