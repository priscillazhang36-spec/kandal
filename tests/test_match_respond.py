"""Unit tests for the photo-reveal respond endpoint."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from kandal.api.main import app

client = TestClient(app)


def _mock_match(profile_a_id, profile_b_id, response_a=None, response_b=None, status="pending_review"):
    return {
        "id": str(uuid4()),
        "profile_a_id": str(profile_a_id),
        "profile_b_id": str(profile_b_id),
        "response_a": response_a,
        "response_b": response_b,
        "status": status,
    }


@patch("kandal.api.routes.matches.get_supabase")
def test_respond_first_accept_sets_one_sided(mock_sb):
    a, b = uuid4(), uuid4()
    match = _mock_match(a, b)
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[match])

    r = client.post(
        f"/matches/{match['id']}/respond",
        json={"profile_id": str(a), "response": "accept"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "a_accepted"
    assert body["is_mutual"] is False


@patch("kandal.api.routes.matches.get_supabase")
def test_respond_second_accept_makes_mutual(mock_sb):
    a, b = uuid4(), uuid4()
    match = _mock_match(a, b, response_a="accepted", status="a_accepted")
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[match])

    r = client.post(
        f"/matches/{match['id']}/respond",
        json={"profile_id": str(b), "response": "accept"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "mutual"
    assert r.json()["is_mutual"] is True


@patch("kandal.api.routes.matches.get_supabase")
def test_respond_decline_sets_declined(mock_sb):
    a, b = uuid4(), uuid4()
    match = _mock_match(a, b, response_a="accepted", status="a_accepted")
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[match])

    r = client.post(
        f"/matches/{match['id']}/respond",
        json={"profile_id": str(b), "response": "decline"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "declined"
    assert r.json()["is_mutual"] is False


@patch("kandal.api.routes.matches.get_supabase")
def test_respond_rejects_outsider(mock_sb):
    a, b = uuid4(), uuid4()
    match = _mock_match(a, b)
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[match])

    r = client.post(
        f"/matches/{match['id']}/respond",
        json={"profile_id": str(uuid4()), "response": "accept"},
    )
    assert r.status_code == 403


@patch("kandal.api.routes.matches.get_supabase")
def test_respond_rejects_invalid_response(mock_sb):
    a, b = uuid4(), uuid4()
    match = _mock_match(a, b)
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[match])

    r = client.post(
        f"/matches/{match['id']}/respond",
        json={"profile_id": str(a), "response": "maybe"},
    )
    assert r.status_code == 400


@patch("kandal.api.routes.matches.get_supabase")
def test_respond_404_when_match_missing(mock_sb):
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[])

    r = client.post(
        f"/matches/{uuid4()}/respond",
        json={"profile_id": str(uuid4()), "response": "accept"},
    )
    assert r.status_code == 404
