"""Per-user Kandal memory: recall, write, extract.

Same brain (soul.md), different memories. Each Kandal carries what it knows
about its user across sessions.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from uuid import UUID

import anthropic

from kandal.core.config import get_settings
from kandal.core.supabase import get_supabase

logger = logging.getLogger(__name__)

VALID_KINDS = {"summary", "fact", "preference", "feeling", "episode"}
DEFAULT_RECALL_LIMIT = 12
# Cosine similarity threshold above which a new memory is considered a duplicate.
DEDUP_THRESHOLD = 0.92
# Time-decay half-life in days for the salience+recency fallback path.
DECAY_HALF_LIFE_DAYS = 30.0


def _embed(text: str) -> list[float] | None:
    """Embed a single string via Voyage. Returns None on failure."""
    try:
        from kandal.profiling.embeddings import embed_narrative
        return embed_narrative(text)
    except Exception as e:
        logger.warning("memory embed failed: %s", e)
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class Memory:
    kind: str
    content: str
    salience: float


def recall(
    profile_id: UUID,
    query: str | None = None,
    limit: int = DEFAULT_RECALL_LIMIT,
) -> list[Memory]:
    """Pull top memories for a profile.

    If `query` is provided, ranks by semantic similarity blended with salience
    and time-decay (server-side via recall_kandal_memories). Otherwise ranks
    by salience * decay (client-side fallback).
    """
    client = get_supabase()

    # Semantic recall path
    if query:
        q_emb = _embed(query)
        if q_emb is not None:
            try:
                resp = client.rpc(
                    "recall_kandal_memories",
                    {
                        "p_profile_id": str(profile_id),
                        "p_query_embedding": q_emb,
                        "p_limit": limit,
                        "p_half_life_days": DECAY_HALF_LIFE_DAYS,
                    },
                ).execute()
                rows = resp.data or []
                if rows:
                    _bump_recall_stats(client, [r["id"] for r in rows])
                    return [
                        Memory(kind=r["kind"], content=r["content"], salience=float(r["salience"]))
                        for r in rows
                    ]
            except Exception as e:
                logger.warning("semantic recall failed, falling back: %s", e)

    # Fallback: salience + decay, client-side
    resp = (
        client.table("kandal_memories")
        .select("id, kind, content, salience, created_at")
        .eq("profile_id", str(profile_id))
        .order("salience", desc=True)
        .order("created_at", desc=True)
        .limit(limit * 3)
        .execute()
    )
    rows = resp.data or []
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    def decayed(row: dict) -> float:
        try:
            created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            age_days = (now - created).total_seconds() / 86400.0
        except Exception:
            age_days = 0.0
        return float(row["salience"]) * math.exp(-age_days / DECAY_HALF_LIFE_DAYS)

    rows.sort(key=decayed, reverse=True)
    rows = rows[:limit]
    if rows:
        _bump_recall_stats(client, [r["id"] for r in rows])
    return [Memory(kind=r["kind"], content=r["content"], salience=float(r["salience"])) for r in rows]


def _bump_recall_stats(client, ids: list[str]) -> None:
    """Best-effort: increment recall_count and update last_recalled_at."""
    if not ids:
        return
    try:
        from datetime import datetime, timezone
        # Postgres can't atomically increment via supabase-py easily;
        # fetch current counts then update. Cheap for small N.
        resp = client.table("kandal_memories").select("id, recall_count").in_("id", ids).execute()
        now_iso = datetime.now(timezone.utc).isoformat()
        for row in resp.data or []:
            client.table("kandal_memories").update({
                "recall_count": (row.get("recall_count") or 0) + 1,
                "last_recalled_at": now_iso,
            }).eq("id", row["id"]).execute()
    except Exception as e:
        logger.debug("bump recall stats failed: %s", e)


def _is_duplicate(
    profile_id: UUID, kind: str, embedding: list[float] | None
) -> tuple[bool, str | None]:
    """Check if a near-identical memory already exists. Returns (is_dup, existing_id)."""
    if embedding is None:
        return False, None
    try:
        client = get_supabase()
        resp = client.rpc(
            "recall_kandal_memories",
            {
                "p_profile_id": str(profile_id),
                "p_query_embedding": embedding,
                "p_limit": 5,
                "p_half_life_days": 9999.0,  # ignore decay for dedup
            },
        ).execute()
        for row in resp.data or []:
            if row["kind"] != kind:
                continue
            # Recall RPC returns blended score, not raw similarity, so re-fetch and compare.
            full = (
                client.table("kandal_memories")
                .select("embedding")
                .eq("id", row["id"])
                .single()
                .execute()
            )
            other = full.data.get("embedding") if full.data else None
            if other and _cosine(embedding, other) >= DEDUP_THRESHOLD:
                return True, row["id"]
    except Exception as e:
        logger.debug("dedup check failed: %s", e)
    return False, None


def _bump_salience(memory_id: str, bump: float = 0.05) -> None:
    """Reinforce an existing memory when a duplicate write arrives."""
    try:
        client = get_supabase()
        resp = client.table("kandal_memories").select("salience").eq("id", memory_id).single().execute()
        cur = float((resp.data or {}).get("salience", 0.5))
        client.table("kandal_memories").update({
            "salience": min(1.0, cur + bump),
        }).eq("id", memory_id).execute()
    except Exception as e:
        logger.debug("bump salience failed: %s", e)


def _profile_exists(profile_id: UUID) -> bool:
    try:
        resp = (
            get_supabase().table("profiles")
            .select("id").eq("id", str(profile_id)).limit(1).execute()
        )
        return bool(resp.data)
    except Exception:
        return False


def write_memory(
    profile_id: UUID,
    kind: str,
    content: str,
    salience: float = 0.5,
    source: str | None = None,
) -> None:
    if kind not in VALID_KINDS:
        raise ValueError(f"invalid memory kind: {kind}")
    content = content.strip()
    if not content:
        return
    if not _profile_exists(profile_id):
        logger.debug("skipping memory write — profile %s missing", profile_id)
        return
    embedding = _embed(content)
    is_dup, existing = _is_duplicate(profile_id, kind, embedding)
    if is_dup and existing:
        _bump_salience(existing)
        return
    get_supabase().table("kandal_memories").insert({
        "profile_id": str(profile_id),
        "kind": kind,
        "content": content,
        "salience": max(0.0, min(1.0, salience)),
        "source": source,
        "embedding": embedding,
    }).execute()


def write_memories(profile_id: UUID, memories: list[dict], source: str | None = None) -> int:
    """Bulk insert with embeddings + dedup. Returns count of new rows written."""
    if not _profile_exists(profile_id):
        logger.debug("skipping bulk memory writes — profile %s missing", profile_id)
        return 0
    written = 0
    for m in memories:
        kind = m.get("kind")
        content = (m.get("content") or "").strip()
        if kind not in VALID_KINDS or not content:
            continue
        try:
            write_memory(
                profile_id,
                kind,
                content,
                salience=float(m.get("salience", 0.5)),
                source=source,
            )
            written += 1
        except Exception as e:
            logger.warning("memory write failed (%s): %s", kind, e)
    return written


def format_memories_for_prompt(memories: list[Memory], name: str | None = None) -> str:
    """Build the 'what you remember about them' block to append to soul."""
    if not memories:
        return ""
    who = name or "this person"
    grouped: dict[str, list[Memory]] = {}
    for m in memories:
        grouped.setdefault(m.kind, []).append(m)

    lines = [f"\n\n---\n\n# What you remember about {who}\n"]
    order = ["summary", "preference", "fact", "feeling", "episode"]
    labels = {
        "summary": "Who they are",
        "preference": "What they want / need",
        "fact": "Things you know",
        "feeling": "How they've been feeling",
        "episode": "Recent things that happened",
    }
    for kind in order:
        items = grouped.get(kind)
        if not items:
            continue
        lines.append(f"\n**{labels[kind]}**")
        for m in items:
            lines.append(f"- {m.content}")
    lines.append(
        "\n\nThis is what you carry from past conversations. Don't recite it back — "
        "just let it shape how you talk to them. Reference specifics naturally when "
        "they're relevant, the way a friend would."
    )
    return "\n".join(lines)


_EXTRACT_PROMPT = """\
You are reading the most recent exchange between Kandal (an AI relationship friend) \
and its user. Extract any DURABLE memories worth carrying into future conversations.

Only extract things that would still matter weeks from now. Skip pleasantries, \
small talk, and anything already obvious from a profile.

Return JSON: {"memories": [{"kind": ..., "content": ..., "salience": ...}]}

kind must be one of:
- "fact"       — concrete biographical detail (job change, moved cities, sibling's name)
- "preference" — something they want/need/dislike in dating or partners
- "feeling"    — an emotional state worth remembering (anxious about X, healing from Y)
- "episode"    — a specific event they shared (date with X went badly, fight with ex)
- "summary"    — only for big shifts in self-understanding; rare

content: one sentence, written from Kandal's POV ("she's been feeling stuck since...").
salience: 0.0-1.0. 0.8+ for things that change how to talk to them. 0.4-0.6 default. \
0.2 for minor color.

Return {"memories": []} if nothing durable came up.
"""


def extract_memories_from_exchange(recent_messages: list[dict]) -> list[dict]:
    """LLM-extract durable memories from a recent slice of conversation."""
    if not recent_messages:
        return []
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent_messages
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=_EXTRACT_PROMPT,
            messages=[{"role": "user", "content": transcript}],
        )
        text = resp.content[0].text.strip()
        # Strip code fences if present
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json").strip()
        data = json.loads(text)
        return data.get("memories", [])
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning("memory extraction failed: %s", e)
        return []


def seed_from_onboarding(
    profile_id: UUID,
    traits: dict,
    narrative: str | None,
) -> int:
    """Convert finalized onboarding traits into seed memories.

    Called once when the onboarding interview completes. After this, ongoing
    chats add incrementally via extract_memories_from_exchange.
    """
    memories: list[dict] = []

    if narrative:
        memories.append({
            "kind": "summary",
            "content": narrative.strip(),
            "salience": 0.9,
        })

    if eg := traits.get("emotional_giving"):
        memories.append({"kind": "summary", "content": f"How they love: {eg}", "salience": 0.85})
    if en := traits.get("emotional_needs"):
        memories.append({"kind": "preference", "content": f"What they need: {en}", "salience": 0.9})

    if att := traits.get("attachment_style"):
        memories.append({"kind": "fact", "content": f"Attachment style: {att}.", "salience": 0.7})
    if conflict := traits.get("conflict_style"):
        memories.append({"kind": "fact", "content": f"Conflict style: {conflict}.", "salience": 0.7})
    if hist := traits.get("relationship_history"):
        memories.append({"kind": "fact", "content": f"Relationship history: {hist}.", "salience": 0.6})

    if interests := traits.get("interests"):
        memories.append({
            "kind": "fact",
            "content": f"Into: {', '.join(interests)}.",
            "salience": 0.5,
        })
    if values := traits.get("values"):
        memories.append({
            "kind": "preference",
            "content": f"Values: {', '.join(values)}.",
            "salience": 0.7,
        })
    if pp := traits.get("partner_personality"):
        memories.append({
            "kind": "preference",
            "content": f"Drawn to partners who are: {', '.join(pp)}.",
            "salience": 0.75,
        })

    return write_memories(profile_id, memories, source="onboarding")
