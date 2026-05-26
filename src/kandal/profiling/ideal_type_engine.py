"""Ideal-type discovery conversation engine.

Drives the 5-stage flow:
  0. Dealbreaker MCQs (deterministic loop)
  1. Past-pull excavation (LLM freeform, phase-gated)
  2. The "ick" beat (still LLM freeform, last phase)
  3. Vignette forced-choice (one LLM generation call, then deterministic loop)
  4. Pattern readback + confirm (one LLM call, then yes/correction)

State persists on the `ideal_types` Supabase row. The engine itself is
side-effect-free besides the LLM calls — DB I/O happens in the route layer.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

import anthropic

from kandal.core.config import get_settings
from kandal.profiling import ideal_type_dealbreakers as db_mcqs
from kandal.profiling.ideal_type_celebrities import (
    format_celebrity_pair,
    generate_celebrity_pairs,
    parse_pick,
)
from kandal.profiling.ideal_type_extractor import extract_ideal_type
from kandal.profiling.ideal_type_prompts import (
    COVERAGE_CHECK_PROMPT,
    OPENING_MESSAGE,
    build_conversation_prompt,
    format_readback,
)
from kandal.profiling.ideal_type_vignettes import (
    format_pair_for_user,
    generate_vignettes,
)

logger = logging.getLogger(__name__)


IDEAL_TYPE_TARGET_QUESTIONS = 7   # soft target for freeform turns (Stages 1+2)
IDEAL_TYPE_HARD_CAP = 12          # hard cap on freeform turns
COVERAGE_CHECK_MIN_TURN = 5       # first turn at which coverage can be checked
COVERAGE_CHECK_EVERY = 2          # re-fire cadence after the first check


_CONFIRM_YES = frozenset({
    "yes", "yeah", "yep", "y", "looks good", "correct", "confirmed",
    "that's right", "lock it in", "good", "perfect", "sure", "yea",
    "that's me", "spot on", "nailed it", "all good",
})


@dataclass
class IdealTypeState:
    profile_id: UUID
    messages: list[dict] = field(default_factory=list)
    # Stages: dealbreakers → celebrity_picks → freeform → vignettes →
    # awaiting_confirmation → complete
    stage: str = "dealbreakers"

    # Stage 0
    dealbreaker_index: int = 0
    dealbreaker_answers: dict = field(default_factory=dict)

    # Stage 0.5 — celebrity forced-choice
    celebrity_pairs: list[dict] = field(default_factory=list)
    celebrity_pair_index: int = 0
    celebrity_choices: list[dict] = field(default_factory=list)

    # Stage 1+2
    questions_asked: int = 0  # freeform turns only
    last_coverage_check_turn: int = -1

    # Stage 3
    vignettes: list[dict] = field(default_factory=list)
    vignette_index: int = 0
    vignette_replies: list[str] = field(default_factory=list)

    # Stage 4
    pending_artifact: dict | None = None


@dataclass
class IdealTypeTurn:
    reply: str
    is_complete: bool = False
    stage: str = "dealbreakers"
    artifact: dict | None = None


def _get_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _parse_json_response(raw: str):
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())


class IdealTypeEngine:
    """Drives the ideal_type_discovery conversation."""

    def start(self, profile_id: UUID) -> tuple[IdealTypeState, str]:
        """Begin a new ideal-type session. Returns (state, opening_message).

        The opening message is the mode intro + the first dealbreaker question.
        """
        state = IdealTypeState(profile_id=profile_id, stage="dealbreakers")
        first_q, idx = db_mcqs.next_question(state.dealbreaker_answers, 0)
        state.dealbreaker_index = idx
        opening = f"{OPENING_MESSAGE}\n\n{first_q.prompt}"
        state.messages.append({"role": "assistant", "content": opening})
        return state, opening

    def next_turn(self, state: IdealTypeState, user_reply: str) -> IdealTypeTurn:
        """Process one user reply, return the next message + state changes."""
        state.messages.append({"role": "user", "content": user_reply})

        if state.stage == "dealbreakers":
            return self._handle_dealbreaker(state, user_reply)
        if state.stage == "celebrity_picks":
            return self._handle_celebrity_pick(state, user_reply)
        if state.stage == "freeform":
            return self._handle_freeform(state, user_reply)
        if state.stage == "vignettes":
            return self._handle_vignette(state, user_reply)
        if state.stage == "awaiting_confirmation":
            return self._handle_confirmation(state, user_reply)

        # Already complete — shouldn't be called.
        return IdealTypeTurn(
            reply="This session is already complete.",
            is_complete=True,
            stage=state.stage,
            artifact=state.pending_artifact,
        )

    # --- Stage 0: dealbreaker MCQ loop ---

    def _handle_dealbreaker(self, state: IdealTypeState, user_reply: str) -> IdealTypeTurn:
        question = db_mcqs.QUESTIONS[state.dealbreaker_index]
        parsed = question.parse(user_reply)
        if parsed is None:
            retry = (
                f"Didn't quite catch that. Pick a letter, or tell me in your own words.\n\n"
                f"{question.prompt}"
            )
            state.messages.append({"role": "assistant", "content": retry})
            return IdealTypeTurn(reply=retry, stage="dealbreakers")

        db_mcqs.apply_answer(state.dealbreaker_answers, question, parsed)

        nxt = db_mcqs.next_question(state.dealbreaker_answers, state.dealbreaker_index + 1)
        if nxt is None:
            return self._start_celebrity_picks(state)

        next_q, next_idx = nxt
        state.dealbreaker_index = next_idx
        state.messages.append({"role": "assistant", "content": next_q.prompt})
        return IdealTypeTurn(reply=next_q.prompt, stage="dealbreakers")

    # --- Stage 0.5: celebrity forced-choice ---

    def _start_celebrity_picks(self, state: IdealTypeState) -> IdealTypeTurn:
        """Generate celebrity pairs tailored to gender + ethnicity preference."""
        try:
            pairs = generate_celebrity_pairs(
                gender_preference=state.dealbreaker_answers.get("gender_preference") or [],
                ethnicity_preference=state.dealbreaker_answers.get("ethnicity_preference") or ["any"],
                age_min=state.dealbreaker_answers.get("age_min"),
                age_max=state.dealbreaker_answers.get("age_max"),
            )
        except Exception as e:
            # Graceful degradation — session continues without the visual
            # signal. Warning (not error) so this doesn't page on Sentry.
            logger.warning("celebrity pair generation failed, skipping stage: %s", e)
            return self._start_freeform(state)

        state.celebrity_pairs = pairs
        state.celebrity_pair_index = 0
        state.stage = "celebrity_picks"

        intro = (
            "Now a quick visual read — I'll show you some pairs of well-known "
            "people. Pick whichever pulls you more, and tell me what tipped "
            "it. Quick reactions, no overthinking.\n\n"
            + format_celebrity_pair(pairs[0], 0, len(pairs))
        )
        state.messages.append({"role": "assistant", "content": intro})
        return IdealTypeTurn(reply=intro, stage="celebrity_picks")

    def _handle_celebrity_pick(self, state: IdealTypeState, user_reply: str) -> IdealTypeTurn:
        """Capture the pick + verbatim reply, advance to the next pair or freeform."""
        pair = state.celebrity_pairs[state.celebrity_pair_index]
        picked = parse_pick(user_reply)
        state.celebrity_choices.append({
            "pair_index": state.celebrity_pair_index,
            "axis": pair.get("axis"),
            "a": pair.get("a"),
            "b": pair.get("b"),
            "picked": picked,
            "user_reply": user_reply,
        })
        state.celebrity_pair_index += 1

        if state.celebrity_pair_index >= len(state.celebrity_pairs):
            return self._start_freeform(state)

        next_pair = state.celebrity_pairs[state.celebrity_pair_index]
        prompt = format_celebrity_pair(
            next_pair, state.celebrity_pair_index, len(state.celebrity_pairs)
        )
        state.messages.append({"role": "assistant", "content": prompt})
        return IdealTypeTurn(reply=prompt, stage="celebrity_picks")

    def _start_freeform(self, state: IdealTypeState) -> IdealTypeTurn:
        """Transition from dealbreakers into Stage 1+2 freeform."""
        state.stage = "freeform"
        state.questions_asked = 0
        intro = (
            "Good, that's the easy part. Now the real stuff.\n\n"
            "Tell me about the past relationship that mattered most — even if "
            "it was short, or never officially became one. Could be an ex, a "
            "serious situationship, the one that almost was. Pick whichever "
            "first comes to mind.\n\n"
            "Two questions about it. First: what initially drew you in? Not "
            "the qualities ('they were smart') — the actual moment or thing "
            "that hooked you."
        )
        state.messages.append({"role": "assistant", "content": intro})
        state.questions_asked += 1
        return IdealTypeTurn(reply=intro, stage="freeform")

    # --- Stage 1+2: freeform past-pull + ick ---

    def _handle_freeform(self, state: IdealTypeState, user_reply: str) -> IdealTypeTurn:
        # Decide whether to exit freeform.
        # Hard cap is the safety net; coverage check re-fires every N turns
        # starting from COVERAGE_CHECK_MIN_TURN. Without re-fire, the engine
        # gets stuck looping LLM turns past the point where signal is complete.
        if state.questions_asked >= IDEAL_TYPE_HARD_CAP:
            return self._start_vignettes(state)

        if (
            state.questions_asked >= COVERAGE_CHECK_MIN_TURN
            and state.questions_asked - state.last_coverage_check_turn >= COVERAGE_CHECK_EVERY
        ):
            state.last_coverage_check_turn = state.questions_asked
            try:
                covered = self._coverage_check(state.messages)
            except Exception as e:
                logger.warning("ideal_type coverage check failed: %s", e)
                covered = {"pulls_covered": False, "ick_covered": False}
            if covered.get("pulls_covered") and covered.get("ick_covered"):
                return self._start_vignettes(state)

        # Otherwise: generate next freeform turn from the LLM.
        system_prompt = build_conversation_prompt(
            questions_asked=state.questions_asked,
            hard_cap=IDEAL_TYPE_HARD_CAP,
        )
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=system_prompt,
            messages=state.messages,
        )
        reply = response.content[0].text
        state.messages.append({"role": "assistant", "content": reply})
        state.questions_asked += 1
        return IdealTypeTurn(reply=reply, stage="freeform")

    def _coverage_check(self, messages: list[dict]) -> dict:
        """Single LLM call. Returns {'pulls_covered': bool, 'ick_covered': bool}."""
        client = _get_client()
        convo = "\n".join(
            f"{'Kandal' if m['role'] == 'assistant' else 'User'}: {m['content']}"
            for m in messages
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            system=COVERAGE_CHECK_PROMPT,
            messages=[{"role": "user", "content": f"Conversation so far:\n\n{convo}"}],
        )
        data = _parse_json_response(response.content[0].text)
        return {
            "pulls_covered": bool(data.get("pulls_covered")),
            "ick_covered": bool(data.get("ick_covered")),
        }

    # --- Stage 3: vignette generation + forced-choice loop ---

    def _start_vignettes(self, state: IdealTypeState) -> IdealTypeTurn:
        """Run the preliminary extraction, generate vignettes, send the first pair."""
        # Preliminary extract just to feed past_pulls + icks into the generator.
        # We'll re-extract everything (including vignette choices) at the end.
        try:
            prelim = extract_ideal_type(state.messages, vignettes=[])
        except Exception as e:
            logger.warning("preliminary extraction failed: %s", e)
            # Best effort fallback — let the generator work with empty context.
            prelim = {"past_pulls": [], "icks": []}

        try:
            pairs = generate_vignettes(
                past_pulls=prelim.get("past_pulls", []),
                icks=prelim.get("icks", []),
                dealbreakers=state.dealbreaker_answers,
            )
        except Exception as e:
            logger.warning("vignette generation failed, skipping stage 3: %s", e)
            # Skip Stage 3 entirely if the generator fails — go straight to readback.
            state.vignettes = []
            return self._prepare_readback(state)

        state.vignettes = pairs
        state.vignette_index = 0
        state.stage = "vignettes"

        intro = (
            "Okay, now the interesting part. I'm going to show you a couple of "
            "people and you tell me which one pulls you more. Quick reactions, "
            "not analysis.\n\n"
            + format_pair_for_user(pairs[0], 0, len(pairs))
        )
        state.messages.append({"role": "assistant", "content": intro})
        return IdealTypeTurn(reply=intro, stage="vignettes")

    def _handle_vignette(self, state: IdealTypeState, user_reply: str) -> IdealTypeTurn:
        # The user's reply text is captured (the "what tipped it" verbatim).
        # We just need to advance to the next vignette or finish the loop.
        # Validation of pick (A/B) happens at extraction time — we let them
        # answer freely here ("definitely B because she sounds more present").
        state.vignette_replies.append(user_reply)
        state.vignette_index += 1

        if state.vignette_index >= len(state.vignettes):
            return self._prepare_readback(state)

        next_pair = state.vignettes[state.vignette_index]
        prompt = format_pair_for_user(next_pair, state.vignette_index, len(state.vignettes))
        state.messages.append({"role": "assistant", "content": prompt})
        return IdealTypeTurn(reply=prompt, stage="vignettes")

    # --- Stage 4: readback + confirmation ---

    def _prepare_readback(self, state: IdealTypeState) -> IdealTypeTurn:
        """Full extraction + LLM readback narration."""
        try:
            artifact = extract_ideal_type(state.messages, state.vignettes)
        except Exception as e:
            # Empty artifact is the right fallback — the route layer can
            # detect missing pull_pattern + alert separately if needed.
            logger.warning("final extraction failed: %s", e)
            artifact = {
                "pull_pattern": None,
                "pull_pattern_quote": None,
                "partner_traits": [],
                "past_pulls": [],
                "icks": [],
                "vignette_choices": [],
            }

        state.pending_artifact = artifact
        readback = format_readback(
            artifact, state.dealbreaker_answers, state.celebrity_choices
        )
        state.messages.append({"role": "assistant", "content": readback})
        state.stage = "awaiting_confirmation"
        return IdealTypeTurn(
            reply=readback,
            stage="awaiting_confirmation",
            artifact=artifact,
        )

    def _handle_confirmation(self, state: IdealTypeState, user_reply: str) -> IdealTypeTurn:
        if user_reply.strip().lower() in _CONFIRM_YES:
            return self._finalize(state)

        # Correction: re-extract from the now-extended conversation and re-readback.
        try:
            artifact = extract_ideal_type(state.messages, state.vignettes)
        except Exception as e:
            logger.warning("re-extraction during correction failed: %s", e)
            artifact = state.pending_artifact or {}

        state.pending_artifact = artifact
        readback = format_readback(
            artifact, state.dealbreaker_answers, state.celebrity_choices
        )
        state.messages.append({"role": "assistant", "content": readback})
        return IdealTypeTurn(
            reply=readback,
            stage="awaiting_confirmation",
            artifact=artifact,
        )

    def _finalize(self, state: IdealTypeState) -> IdealTypeTurn:
        closing = (
            "Locked in. That's your pattern. You can come back and refine this "
            "anytime — and whenever you're ready to actually start matching, "
            "let me know."
        )
        state.messages.append({"role": "assistant", "content": closing})
        state.stage = "complete"
        return IdealTypeTurn(
            reply=closing,
            is_complete=True,
            stage="complete",
            artifact=state.pending_artifact,
        )
