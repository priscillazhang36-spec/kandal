"""Tests for SMS onboarding: answer parsing, state machine, webhook."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from kandal.models.onboarding import OnboardingSession
from kandal.sms.handler import _parse_answer, route_message


# --- Answer parsing ---

def test_parse_answer_letter():
    assert _parse_answer("A") == 0
    assert _parse_answer("b") == 1
    assert _parse_answer("C") == 2
    assert _parse_answer(" d ") == 3


def test_parse_answer_number():
    assert _parse_answer("1") == 0
    assert _parse_answer("4") == 3


def test_parse_answer_invalid():
    assert _parse_answer("hello") is None
    assert _parse_answer("maybe") is None
    assert _parse_answer("") is None
    assert _parse_answer("5") is None


# --- State machine tests (mock DB + Twilio) ---

def _make_session(**overrides):
    defaults = {
        "id": uuid4(),
        "phone": "+15551234567",
        "state": "awaiting_code",
        "verification_code": "123456",
        "code_expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "code_attempts": 0,
        "profile_id": None,
        "answers": [],
        "collected_basics": {},
    }
    defaults.update(overrides)
    return OnboardingSession(**defaults)


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
@patch("kandal.sms.handler.get_supabase")
def test_correct_verification_code(mock_sb, mock_load, mock_save, mock_send):
    session = _make_session()
    mock_load.return_value = session
    profile_id = str(uuid4())
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().insert().execute.return_value = MagicMock(
        data=[{"id": profile_id}]
    )

    reply = route_message("+15551234567", "123456")

    # May start adaptive profiling or fall back to fixed questions
    assert (
        "glad you're here" in reply
        or "alter ego" in reply
        or "Ready?" in reply
        or "first one" in reply
    )
    assert session.state in ("adaptive_profiling", "onboarding_q1")
    assert str(session.profile_id) == profile_id


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_wrong_verification_code(mock_load, mock_save, mock_send):
    session = _make_session()
    mock_load.return_value = session

    reply = route_message("+15551234567", "000000")

    assert "didn't match" in reply
    assert session.code_attempts == 1
    assert session.state == "awaiting_code"


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_code_max_attempts(mock_load, mock_save, mock_send):
    session = _make_session(code_attempts=2)
    mock_load.return_value = session

    reply = route_message("+15551234567", "000000")

    assert session.state == "expired"
    assert "START" in reply


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_code_expired_by_time(mock_load, mock_save, mock_send):
    session = _make_session(
        code_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    mock_load.return_value = session

    reply = route_message("+15551234567", "123456")

    assert session.state == "expired"
    assert "expired" in reply.lower()


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_question_valid_answer(mock_load, mock_save, mock_send):
    session = _make_session(state="onboarding_q1", profile_id=uuid4())
    mock_load.return_value = session

    reply = route_message("+15551234567", "A")

    assert session.state == "onboarding_q2"
    assert len(session.answers) == 1
    assert session.answers[0] == 0


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_question_invalid_answer(mock_load, mock_save, mock_send):
    session = _make_session(state="onboarding_q1", profile_id=uuid4())
    mock_load.return_value = session

    reply = route_message("+15551234567", "hello")

    assert "A, B, C, or D" in reply
    assert session.state == "onboarding_q1"
    assert len(session.answers) == 0


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_last_question_transitions_to_basics(mock_load, mock_save, mock_send):
    session = _make_session(
        state="onboarding_q10",
        profile_id=uuid4(),
        answers=[0, 1, 2, 3, 0, 1, 2, 3, 0],  # 9 previous answers
    )
    mock_load.return_value = session

    reply = route_message("+15551234567", "B")

    assert session.state == "collecting_name"
    assert len(session.answers) == 10
    assert "name" in reply.lower()


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_collecting_name(mock_load, mock_save, mock_send):
    session = _make_session(state="collecting_name", profile_id=uuid4(), answers=list(range(10)))
    mock_load.return_value = session

    reply = route_message("+15551234567", "Priya")

    assert session.collected_basics["name"] == "Priya"
    assert session.state == "collecting_age"


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_collecting_age_valid(mock_load, mock_save, mock_send):
    session = _make_session(state="collecting_age", profile_id=uuid4(), answers=list(range(10)))
    session.collected_basics = {"name": "Test"}
    mock_load.return_value = session

    reply = route_message("+15551234567", "28")

    assert session.collected_basics["age"] == 28
    assert session.state == "collecting_gender"


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_collecting_age_invalid(mock_load, mock_save, mock_send):
    session = _make_session(state="collecting_age", profile_id=uuid4(), answers=list(range(10)))
    mock_load.return_value = session

    reply = route_message("+15551234567", "twelve")

    assert session.state == "collecting_age"
    assert "18" in reply


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
def test_collecting_gender(mock_load, mock_save, mock_send):
    session = _make_session(state="collecting_gender", profile_id=uuid4(), answers=list(range(10)))
    session.collected_basics = {"name": "Test", "age": 28}
    mock_load.return_value = session

    reply = route_message("+15551234567", "Female")

    assert session.collected_basics["gender"] == "female"
    assert session.state == "collecting_gender_preference"


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._save_session")
@patch("kandal.sms.handler._load_session")
@patch("kandal.sms.handler._finalize")
def test_collecting_city_completes(mock_finalize, mock_load, mock_save, mock_send):
    session = _make_session(
        state="collecting_city",
        profile_id=uuid4(),
        answers=list(range(10)),
        collected_basics={"name": "Priya", "age": 28, "gender": "female"},
    )
    mock_load.return_value = session

    reply = route_message("+15551234567", "NYC")

    assert session.state == "complete"
    assert session.collected_basics["city"] == "NYC"
    mock_finalize.assert_called_once_with(session)
    assert "all set" in reply.lower()


@patch("kandal.profiling.chat.chat_turn")
@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._load_session")
def test_complete_state_reply(mock_load, mock_send, mock_chat):
    from kandal.profiling.chat import ChatTurn
    session = _make_session(state="complete", profile_id=uuid4())
    mock_load.return_value = session
    mock_chat.return_value = ChatTurn(reply="hey you")

    reply = route_message("+15551234567", "hello")

    assert reply == "hey you"


@patch("kandal.sms.handler.send_sms")
@patch("kandal.sms.handler._load_session")
def test_no_session_reply(mock_load, mock_send):
    mock_load.return_value = None

    reply = route_message("+15551234567", "hello")

    assert "START" in reply


# --- Webhook endpoint tests ---

from fastapi.testclient import TestClient
from kandal.api.main import app

client = TestClient(app)


def test_health_still_works():
    resp = client.get("/health")
    assert resp.status_code == 200


@patch("kandal.api.routes.auth.send_sms")
@patch("kandal.api.routes.auth.get_supabase")
def test_start_auth_sends_code(mock_sb, mock_send):
    mock_client = MagicMock()
    mock_sb.return_value = mock_client
    mock_client.table().select().eq().execute.return_value = MagicMock(data=[])
    mock_client.table().upsert().execute.return_value = MagicMock(data=[{}])

    resp = client.post("/auth/start", json={"phone": "+15551234567"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "started"
    mock_send.assert_called_once()


@patch("kandal.api.routes.auth.route_message")
@patch("kandal.api.routes.auth.send_sms")
def test_webhook_routes_message(mock_send, mock_route):
    mock_route.return_value = "ok"

    resp = client.post(
        "/sms/webhook",
        data={"From": "+15551234567", "Body": "A"},
    )

    assert resp.status_code == 200
    assert "Response" in resp.text
    mock_route.assert_called_once_with("+15551234567", "A")
