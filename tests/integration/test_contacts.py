from typing import Any

from fastapi.testclient import TestClient


def create_application(
    client: TestClient, company: str = "Acme", title: str = "SRE"
) -> dict[str, Any]:
    response = client.post(
        "/api/applications", json={"company": company, "title": title, "applied_on": "2026-09-12"}
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def test_create_contact_with_only_a_name(client: TestClient) -> None:
    company_id = create_application(client)["company"]["id"]

    response = client.post(f"/api/companies/{company_id}/contacts", json={"name": "Dana Recruiter"})

    assert response.status_code == 201
    contact = response.json()
    assert contact["name"] == "Dana Recruiter"
    assert contact["email"] is None
    assert contact["company_id"] == company_id


def test_list_contacts_at_a_company(client: TestClient) -> None:
    company_id = create_application(client)["company"]["id"]
    client.post(f"/api/companies/{company_id}/contacts", json={"name": "Dana"})
    client.post(f"/api/companies/{company_id}/contacts", json={"name": "Ari"})

    response = client.get(f"/api/companies/{company_id}/contacts")

    assert [c["name"] for c in response.json()] == ["Ari", "Dana"]


def test_contact_on_unknown_company_is_404(client: TestClient) -> None:
    assert client.post("/api/companies/999999/contacts", json={"name": "X"}).status_code == 404


def test_email_and_linkedin_are_validated_when_present(client: TestClient) -> None:
    company_id = create_application(client)["company"]["id"]
    url = f"/api/companies/{company_id}/contacts"

    assert client.post(url, json={"name": "A", "email": "not-an-email"}).status_code == 422
    assert client.post(url, json={"name": "A", "linkedin_url": "linkedin"}).status_code == 422
    assert client.post(url, json={"name": " "}).status_code == 422
    ok = client.post(
        url,
        json={
            "name": "A",
            "email": "a@acme.example",
            "linkedin_url": "https://www.linkedin.com/in/a",
            "title": "Recruiter",
            "notes": "Prefers email",
        },
    )
    assert ok.status_code == 201


def test_patch_and_delete_contact(client: TestClient) -> None:
    company_id = create_application(client)["company"]["id"]
    contact = client.post(f"/api/companies/{company_id}/contacts", json={"name": "Dana"}).json()

    patched = client.patch(f"/api/contacts/{contact['id']}", json={"title": "Hiring manager"})

    assert patched.status_code == 200
    assert patched.json()["title"] == "Hiring manager"
    assert patched.json()["name"] == "Dana"
    assert client.patch(f"/api/contacts/{contact['id']}", json={"name": None}).status_code == 422
    assert client.delete(f"/api/contacts/{contact['id']}").status_code == 204
    assert client.get(f"/api/companies/{company_id}/contacts").json() == []
    assert client.delete(f"/api/contacts/{contact['id']}").status_code == 404


def test_contact_added_from_one_application_shows_on_every_application_at_that_company(
    client: TestClient,
) -> None:
    first = create_application(client, title="SRE")
    second = create_application(client, title="Platform Engineer")
    elsewhere = create_application(client, company="Globex")

    response = client.post(
        f"/applications/{first['id']}/contacts",
        data={"name": "Dana Recruiter", "email": "dana@acme.example"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Dana Recruiter" in response.text
    assert "Dana Recruiter" in client.get(f"/applications/{second['id']}").text
    assert "Dana Recruiter" not in client.get(f"/applications/{elsewhere['id']}").text


def test_quick_add_with_bad_email_shows_error(client: TestClient) -> None:
    app_id = create_application(client)["id"]

    response = client.post(
        f"/applications/{app_id}/contacts",
        data={"name": "Dana", "email": "nope"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 422
    assert 'class="error"' in response.text


def test_edit_and_delete_contact_from_the_detail_page(client: TestClient) -> None:
    application = create_application(client)
    company_id = application["company"]["id"]
    contact = client.post(f"/api/companies/{company_id}/contacts", json={"name": "Dana"}).json()
    base = f"/applications/{application['id']}/contacts/{contact['id']}"
    htmx = {"HX-Request": "true"}

    edit_form = client.get(f"{base}/edit", headers=htmx)
    assert edit_form.status_code == 200
    assert 'value="Dana"' in edit_form.text

    saved = client.post(base, data={"name": "Dana Smith", "title": "Recruiter"}, headers=htmx)
    assert saved.status_code == 200
    assert "Dana Smith" in saved.text

    deleted = client.post(f"{base}/delete", headers=htmx)
    assert deleted.status_code == 200
    assert "Dana Smith" not in deleted.text


def test_contact_of_another_company_cannot_be_edited_from_this_application(
    client: TestClient,
) -> None:
    application = create_application(client)
    other_company = create_application(client, company="Globex")["company"]["id"]
    contact = client.post(f"/api/companies/{other_company}/contacts", json={"name": "Lee"}).json()

    response = client.post(
        f"/applications/{application['id']}/contacts/{contact['id']}/delete",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 404


def test_changing_contacts_tells_the_page_to_refresh_the_interaction_form(
    client: TestClient,
) -> None:
    app_id = create_application(client)["id"]

    response = client.post(
        f"/applications/{app_id}/contacts", data={"name": "Dana"}, headers={"HX-Request": "true"}
    )

    assert response.headers["HX-Trigger"] == "contacts-changed"
