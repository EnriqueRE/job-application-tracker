from fastapi.testclient import TestClient


def seed(client: TestClient) -> None:
    rows = [
        ("Acme Corp", "Platform Engineer", "applied"),
        ("Acme Corp", "SRE", "screening"),
        ("Globex", "Senior Platform Engineer", "rejected"),
        ("Initech", "Backend Developer", "applied"),
    ]
    for company, title, status in rows:
        response = client.post(
            "/api/applications",
            json={"company": company, "title": title, "applied_on": "2026-09-12", "status": status},
        )
        assert response.status_code == 201


def titles(client: TestClient, params: dict[str, str | list[str]]) -> set[str]:
    response = client.get("/api/applications", params=params)
    assert response.status_code == 200
    return {a["title"] for a in response.json()}


def test_filter_by_one_status(client: TestClient) -> None:
    seed(client)

    assert titles(client, {"status": "applied"}) == {"Platform Engineer", "Backend Developer"}


def test_filter_by_several_statuses(client: TestClient) -> None:
    seed(client)

    assert titles(client, {"status": ["screening", "rejected"]}) == {
        "SRE",
        "Senior Platform Engineer",
    }


def test_search_matches_title_ignoring_case(client: TestClient) -> None:
    seed(client)

    assert titles(client, {"q": "platform"}) == {"Platform Engineer", "Senior Platform Engineer"}


def test_search_matches_company_ignoring_case(client: TestClient) -> None:
    seed(client)

    assert titles(client, {"q": "ACME"}) == {"Platform Engineer", "SRE"}


def test_status_and_search_combine(client: TestClient) -> None:
    seed(client)

    assert titles(client, {"q": "platform", "status": "rejected"}) == {"Senior Platform Engineer"}


def test_search_treats_wildcards_literally(client: TestClient) -> None:
    seed(client)

    assert titles(client, {"q": "%"}) == set()


def test_unknown_status_filter_is_422(client: TestClient) -> None:
    assert client.get("/api/applications", params={"status": "ghosted"}).status_code == 422


def test_list_page_filters_and_htmx_gets_only_the_rows(client: TestClient) -> None:
    seed(client)

    full = client.get("/", params={"q": "globex"})
    rows = client.get("/", params={"q": "globex"}, headers={"HX-Request": "true"})

    assert "Senior Platform Engineer" in full.text
    assert "Backend Developer" not in full.text
    assert 'name="q"' in full.text
    assert 'value="globex"' in full.text
    assert "<html" not in rows.text
    assert "Senior Platform Engineer" in rows.text
    assert "Backend Developer" not in rows.text


def test_list_page_keeps_checked_statuses(client: TestClient) -> None:
    seed(client)

    page = client.get("/", params={"status": "screening"}).text

    assert 'value="screening" checked' in page
    assert "SRE" in page
    assert "Backend Developer" not in page


def test_list_page_says_when_nothing_matches(client: TestClient) -> None:
    seed(client)

    page = client.get("/", params={"q": "nothing like this"}).text

    assert "No applications match" in page


def test_htmx_history_restore_gets_the_full_page(client: TestClient) -> None:
    response = client.get("/", headers={"HX-Request": "true", "HX-History-Restore-Request": "true"})

    assert "<html" in response.text
