import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

DEFAULTS = {"applied": 7, "screening": 5, "interviewing": 3}


def test_fresh_database_has_the_default_thresholds(client: TestClient) -> None:
    response = client.get("/api/settings/follow-up")

    assert response.status_code == 200
    assert response.json() == DEFAULTS


def test_put_updates_thresholds(client: TestClient) -> None:
    response = client.put(
        "/api/settings/follow-up", json={"applied": 10, "screening": 4, "interviewing": 2}
    )

    assert response.status_code == 200
    assert client.get("/api/settings/follow-up").json() == {
        "applied": 10,
        "screening": 4,
        "interviewing": 2,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"applied": 0, "screening": 5, "interviewing": 3},
        {"applied": 366, "screening": 5, "interviewing": 3},
        {"applied": 7, "screening": 5, "interviewing": 3, "rejected": 10},
        {"applied": 7, "screening": 5},
        {"applied": 7.5, "screening": 5, "interviewing": 3},
    ],
)
def test_invalid_thresholds_are_422_and_change_nothing(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.put("/api/settings/follow-up", json=payload)

    assert response.status_code == 422
    assert client.get("/api/settings/follow-up").json() == DEFAULTS


def test_database_rejects_out_of_range_days(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(text("UPDATE follow_up_thresholds SET days = 0"))


def test_database_rejects_thresholds_for_closed_statuses(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO follow_up_thresholds (status, days, updated_at) "
                "VALUES ('rejected', 5, now())"
            )
        )


def test_settings_page_shows_current_values(client: TestClient) -> None:
    page = client.get("/settings").text

    assert 'name="applied" type="number"' in page
    assert 'value="7"' in page


def test_saving_the_settings_page_persists(client: TestClient) -> None:
    response = client.post(
        "/settings",
        data={"applied": "14", "screening": "5", "interviewing": "3"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert client.get("/api/settings/follow-up").json()["applied"] == 14
    assert "Saved" in client.get(response.headers["location"]).text


def test_settings_page_shows_errors_next_to_the_field(client: TestClient) -> None:
    response = client.post(
        "/settings", data={"applied": "0", "screening": "5", "interviewing": "3"}
    )

    assert response.status_code == 422
    assert 'id="applied-error"' in response.text
    assert client.get("/api/settings/follow-up").json() == DEFAULTS
