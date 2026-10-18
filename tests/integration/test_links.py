from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AppLink


def create_application(client: TestClient) -> int:
    response = client.post(
        "/api/applications",
        json={"company": "Acme", "title": "SRE", "applied_on": "2026-09-12"},
    )
    assert response.status_code == 201
    application_id: int = response.json()["id"]
    return application_id


def test_add_link_returns_it_and_shows_it_on_the_application(client: TestClient) -> None:
    app_id = create_application(client)

    response = client.post(
        f"/api/applications/{app_id}/links",
        json={"label": "Take-home repo", "url": "https://github.com/me/take-home"},
    )

    assert response.status_code == 201
    link = response.json()
    assert link["label"] == "Take-home repo"
    links = client.get(f"/api/applications/{app_id}").json()["links"]
    assert links == [link]


def test_link_url_and_label_are_validated(client: TestClient) -> None:
    app_id = create_application(client)
    url = f"/api/applications/{app_id}/links"

    assert client.post(url, json={"label": "x", "url": "javascript:alert(1)"}).status_code == 422
    assert client.post(url, json={"label": " ", "url": "https://a.example"}).status_code == 422


def test_remove_link(client: TestClient) -> None:
    app_id = create_application(client)
    link = client.post(
        f"/api/applications/{app_id}/links", json={"label": "Careers", "url": "https://a.example"}
    ).json()

    response = client.delete(f"/api/applications/{app_id}/links/{link['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/applications/{app_id}").json()["links"] == []


def test_removing_a_link_of_another_application_is_404(client: TestClient) -> None:
    app_id = create_application(client)
    other = client.post(
        "/api/applications",
        json={"company": "Globex", "title": "SRE", "applied_on": "2026-09-12"},
    ).json()["id"]
    link = client.post(
        f"/api/applications/{app_id}/links", json={"label": "Careers", "url": "https://a.example"}
    ).json()

    assert client.delete(f"/api/applications/{other}/links/{link['id']}").status_code == 404


def test_deleting_the_application_deletes_its_links(
    client: TestClient, db_session: Session
) -> None:
    app_id = create_application(client)
    client.post(
        f"/api/applications/{app_id}/links", json={"label": "Careers", "url": "https://a.example"}
    )

    client.delete(f"/api/applications/{app_id}")

    count = db_session.scalar(select(func.count()).where(AppLink.application_id == app_id))
    assert count == 0


def test_htmx_add_and_remove_link_return_the_links_section(client: TestClient) -> None:
    app_id = create_application(client)

    added = client.post(
        f"/applications/{app_id}/links",
        data={"label": "Recruiter LinkedIn", "url": "https://linkedin.example/in/r"},
        headers={"HX-Request": "true"},
    )

    assert added.status_code == 200
    assert "<html" not in added.text
    assert "Recruiter LinkedIn" in added.text
    link_id = client.get(f"/api/applications/{app_id}").json()["links"][0]["id"]

    removed = client.post(
        f"/applications/{app_id}/links/{link_id}/delete", headers={"HX-Request": "true"}
    )

    assert removed.status_code == 200
    assert "Recruiter LinkedIn" not in removed.text


def test_htmx_add_link_with_bad_url_shows_error(client: TestClient) -> None:
    app_id = create_application(client)

    response = client.post(
        f"/applications/{app_id}/links",
        data={"label": "Bad", "url": "nope"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 422
    assert 'class="error"' in response.text


def test_detail_page_has_the_links_section(client: TestClient) -> None:
    app_id = create_application(client)

    page = client.get(f"/applications/{app_id}").text

    assert 'id="links"' in page
    assert f'hx-post="/applications/{app_id}/links"' in page
