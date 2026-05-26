"""Extract the IdealType artifact from a completed ideal_type_discovery
conversation. Runs once, after Stage 3 vignettes complete.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from kandal.core.config import get_settings
from kandal.profiling.ideal_type_prompts import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def _get_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _parse_json_response(raw: str) -> Any:
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())


def _format_conversation(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        role = "Kandal" if m["role"] == "assistant" else "User"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def _format_vignettes(vignettes: list[dict]) -> str:
    if not vignettes:
        return "(none — vignette stage did not run)"
    lines = []
    for i, p in enumerate(vignettes):
        a = p.get("a", {})
        b = p.get("b", {})
        lines.append(
            f"Pair {i} (axis={p.get('axis')}):\n"
            f"  A: {a.get('name')} — {a.get('sketch')}\n"
            f"  B: {b.get('name')} — {b.get('sketch')}"
        )
    return "\n".join(lines)


def extract_ideal_type(messages: list[dict], vignettes: list[dict]) -> dict:
    """Single LLM call. Returns a dict matching the EXTRACTION_PROMPT schema.

    Caller validates / coerces fields into an IdealType model.
    """
    convo = _format_conversation(messages)
    vignette_block = _format_vignettes(vignettes)
    user_content = (
        f"Conversation:\n\n{convo}\n\n"
        f"---\n\nVignettes that were presented in Stage 3:\n\n{vignette_block}"
    )

    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=EXTRACTION_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text
    try:
        data = _parse_json_response(raw)
    except (json.JSONDecodeError, IndexError) as e:
        # Re-raised — caller logs at warning. Debug here for local visibility.
        logger.debug("ideal_type extractor returned invalid JSON: %s | raw=%s", e, raw[:500])
        raise

    return _coerce_artifact(data)


def _coerce_artifact(data: dict) -> dict:
    """Validate / clean the LLM output. Drop malformed entries silently."""
    out: dict = {
        "pull_pattern": _str_or_none(data.get("pull_pattern"), min_len=10),
        "break_pattern": _str_or_none(data.get("break_pattern"), min_len=10),
        "pull_pattern_quote": _str_or_none(data.get("pull_pattern_quote"), min_len=8),
        "partner_traits": _str_list(data.get("partner_traits")),
        "icks": _str_list(data.get("icks")),
        "past_pulls": [],
        "vignette_choices": [],
    }

    for p in data.get("past_pulls") or []:
        if not isinstance(p, dict):
            continue
        out["past_pulls"].append({
            "description": _str_or_none(p.get("description")),
            "what_brought_together": _str_or_none(p.get("what_brought_together")),
            "what_broke_apart": _str_or_none(p.get("what_broke_apart")),
            "brought_quote": _str_or_none(p.get("brought_quote"), min_len=8),
            "broke_quote": _str_or_none(p.get("broke_quote"), min_len=8),
        })

    for c in data.get("vignette_choices") or []:
        if not isinstance(c, dict):
            continue
        picked = c.get("picked")
        if picked not in {"a", "b"}:
            continue
        pi = c.get("pair_index")
        if not isinstance(pi, int):
            continue
        out["vignette_choices"].append({
            "pair_index": pi,
            "picked": picked,
            "tipped_reason": _str_or_none(c.get("tipped_reason")),
            "tipped_quote": _str_or_none(c.get("tipped_quote"), min_len=8),
        })

    return out


def _str_or_none(v, min_len: int = 1) -> str | None:
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v if len(v) >= min_len else None


def _str_list(v) -> list[str]:
    if not isinstance(v, list):
        return []
    return [s.strip() for s in v if isinstance(s, str) and s.strip()]
