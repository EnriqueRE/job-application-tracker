import re

from fastapi.testclient import TestClient


def create(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "company": "Acme Corp",
        "title": "Platform Engineer",
        "applied_on": "2026-09-12",
    }
    payload.update(overrides)
    response = client.post("/api/applications", json=payload)
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def test_list_page_shows_empty_state(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "No applications yet" in response.text


def test_list_page_shows_applications_newest_applied_first(client: TestClient) -> None:
    create(client, title="Older role", applied_on="2026-09-01")
    create(client, title="Newer role", company="Globex", applied_on="2026-09-20")

    page = client.get("/").text

    assert page.index("Newer role") < page.index("Older role")
    assert "Globex" in page
    assert "2026-09-20" in page
    assert "applied" in page


def test_list_page_escapes_user_input(client: TestClient) -> None:
    create(client, title="<script>alert(1)</script>")

    page = client.get("/").text

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_pages_load_no_external_assets(client: TestClient) -> None:
    page = client.get("/").text

    assert not re.search(r"""(src|href)=["']?(https?:)?//""", page)
    assert 'src="/static/htmx.min.js"' in page


def test_htmx_is_served_locally(client: TestClient) -> None:
    response = client.get("/static/htmx.min.js")

    assert response.status_code == 200
    assert "htmx" in response.text
