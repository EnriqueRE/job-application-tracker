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


def form(**overrides: str) -> dict[str, str]:
    fields = {
        "company": "Acme Corp",
        "title": "Platform Engineer",
        "job_url": "https://acme.example/jobs/1",
        "job_description": "Line one\nLine two",
        "location": "Remote",
        "source": "Referral",
        "applied_on": "2026-09-12",
        "notes": "Ask about on-call",
    }
    fields.update(overrides)
    return fields


def test_new_application_form_renders(client: TestClient) -> None:
    response = client.get("/applications/new")

    assert response.status_code == 200
    for name in ("company", "title", "job_url", "job_description", "applied_on", "notes"):
        assert f'name="{name}"' in response.text


def test_submitting_the_form_redirects_to_the_detail_page(client: TestClient) -> None:
    response = client.post("/applications", data=form(), follow_redirects=False)

    assert response.status_code == 303
    assert re.fullmatch(r"/applications/\d+", response.headers["location"])


def test_detail_page_shows_every_stored_field(client: TestClient) -> None:
    location = client.post("/applications", data=form(), follow_redirects=False).headers["location"]

    page = client.get(location).text

    for text in (
        "Acme Corp",
        "Platform Engineer",
        "https://acme.example/jobs/1",
        "Remote",
        "Referral",
        "2026-09-12",
        "Ask about on-call",
        "applied",
    ):
        assert text in page
    assert "Line one\nLine two" in page
    assert 'class="preserve"' in page


def test_list_links_to_the_detail_page(client: TestClient) -> None:
    created = create(client)

    assert f'href="/applications/{created["id"]}"' in client.get("/").text


def test_unknown_detail_page_is_404(client: TestClient) -> None:
    assert client.get("/applications/999999").status_code == 404


def test_duplicate_submission_keeps_the_form_and_links_to_the_existing_one(
    client: TestClient,
) -> None:
    existing = create(client, title="Platform Engineer")

    response = client.post(
        "/applications", data=form(title=" platform engineer ", notes="second try")
    )

    assert response.status_code == 409
    assert "already exists" in response.text
    assert f'href="/applications/{existing["id"]}"' in response.text
    assert "second try" in response.text


def test_validation_errors_are_shown_next_to_the_field(client: TestClient) -> None:
    response = client.post("/applications", data=form(title="", job_url="nope"))

    assert response.status_code == 422
    assert 'id="title-error"' in response.text
    assert 'id="job_url-error"' in response.text
    assert 'value="Acme Corp"' in response.text


def test_blank_optional_url_is_accepted(client: TestClient) -> None:
    response = client.post("/applications", data=form(job_url=""), follow_redirects=False)

    assert response.status_code == 303
