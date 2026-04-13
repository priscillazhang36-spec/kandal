"""Ongoing Kandal chat: post-onboarding conversations.

Distinct from ProfilingEngine (one-shot interview). This is the "1am text"
loop — same brain (soul.md), enriched with everything Kandal remembers about
the user from past sessions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import anthropic

from kandal.core.config import get_settings
from kandal.core.supabase import get_supabase
from kandal.profiling.memory import (
    extract_memories_from_exchange,
    format_memories_for_prompt,
    recall,
    write_memories,
)
from kandal.profiling.prompts import build_chat_prompt

logger = logging.getLogger(__name__)

# How many recent messages to feed the memory extractor each turn.
_EXTRACT_WINDOW = 4


@dataclass
class ChatTurn:
    reply: str
    memories_written: int = 0


class ProfileMissingError(Exception):
    """Raised when chat_turn is called for a profile_id with no matching row.
    Usually means the profile was deleted (test cleanup, manual wipe, GDPR delete)
    while the SMS session still references the old id."""


def _profile_exists(profile_id: UUID) -> bool:
    resp = (
        get_supabase()
        .table("profiles")
        .select("id")
        .eq("id", str(profile_id))
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def _load_or_create_chat(profile_id: UUID) -> tuple[str, list[dict]]:
    """Return (chat_id, messages) for the most recent chat, or create one."""
    client = get_supabase()
    resp = (
        client.table("kandal_chats")
        .select("id, messages")
        .eq("profile_id", str(profile_id))
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]["id"], resp.data[0]["messages"] or []

    created = (
        client.table("kandal_chats")
        .insert({"profile_id": str(profile_id), "messages": []})
        .execute()
    )
    return created.data[0]["id"], []


def _save_chat(chat_id: str, messages: list[dict]) -> None:
    from datetime import datetime, timezone
    get_supabase().table("kandal_chats").update({
        "messages": messages,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", chat_id).execute()


def _profile_name(profile_id: UUID) -> str | None:
    try:
        resp = (
            get_supabase()
            .table("profiles")
            .select("name")
            .eq("id", str(profile_id))
            .single()
            .execute()
        )
        return (resp.data or {}).get("name")
    except Exception:
        return None


def chat_turn(profile_id: UUID, user_message: str) -> ChatTurn:
    """Run one turn of ongoing Kandal chat. Persists message + extracts memories."""
    if not _profile_exists(profile_id):
        raise ProfileMissingError(str(profile_id))
    chat_id, messages = _load_or_create_chat(profile_id)
    messages.append({"role": "user", "content": user_message})

    memories = recall(profile_id, query=user_message)
    memory_block = format_memories_for_prompt(memories, _profile_name(profile_id))
    system_prompt = build_chat_prompt(memory_block)

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=system_prompt,
        messages=messages,
    )
    reply = response.content[0].text
    messages.append({"role": "assistant", "content": reply})
    _save_chat(chat_id, messages)

    # Extract durable memories from this exchange (best-effort).
    written = 0
    try:
        extracted = extract_memories_from_exchange(messages[-_EXTRACT_WINDOW:])
        if extracted:
            written = write_memories(profile_id, extracted, source=f"chat:{chat_id}")
    except Exception as e:
        logger.warning("memory write failed: %s", e)

    return ChatTurn(reply=reply, memories_written=written)
