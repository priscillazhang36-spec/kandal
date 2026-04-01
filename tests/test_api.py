from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from kandal.api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@patch("kandal.api.routes.profiles.get_supabase")
def test_create_profile(mock_sb):
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    uid = str(uuid4())
    mock_client.table().insert().execute.return_value = MagicMock(
        data=[{"id": uid, "name": "Alice", "age": 28, "gender": "female", "city": "NYC", "bio": "", "is_active": True}]
    )
    resp = client.post("/profiles/", json={"name": "Alice", "age": 28, "gender": "female"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Alice"


@patch("kandal.api.routes.profiles.get_supabase")
def test_get_profile_not_found(mock_sb):
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[])
    resp = client.get(f"/profiles/{uuid4()}")
    assert resp.status_code == 404
