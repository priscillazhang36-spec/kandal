"""Adaptive profiling conversation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

import anthropic

from kandal.core.config import get_settings
from kandal.profiling.extractor import assess_coverage, extract_traits
from kandal.profiling.memory import (
    format_memories_for_prompt,
    recall,
    seed_from_onboarding,
)
from kandal.profiling.pool_stats import PoolStats
from kandal.profiling.prompts import (
    SUMMARY_SYSTEM_PROMPT,
    TRAIT_DIMENSIONS,
    build_conversation_prompt,
    build_summary_prompt,
)
from kandal.questionnaire.inference import InferredTraits

logger = logging.getLogger(__name__)

COVERAGE_THRESHOLD = 0.7
# Soft target: aim for ~20 min total. We don't end at this number — it's just
# what Kandal uses to tell the user "we're about halfway / closing in."
TARGET_QUESTION_COUNT = 14
# Hard safety cap. Past this, we finalize even if essentials are missing —
# better to ship an incomplete profile than loop forever.
HARD_QUESTION_CAP = 22
# Assess coverage every N turns to reduce LLM calls
COVERAGE_CHECK_INTERVAL = 2

# Spark pillars Kandal MUST gather real signal on before finalizing freeform.
# The long-term categorical self-pillars (attachment / love languages / conflict
# / history) come from the post-summary long-term MCQ loop — not gated here.
# Taste and attraction are nice-to-have but not blocking (users who don't want
# to share past attraction shouldn't be forced).
ESSENTIAL_DIMENSIONS = [
    "emotional_dynamics",   # how it feels to be loved by them + what they need
    "partner_vibe",         # what kind of person they're looking for
    "spark_aliveness",      # what's firing in them right now
]
ESSENTIAL_THRESHOLD = 0.6

OPENING_MESSAGE = (
    "Hey — I'm Kandal :)\n\n"
    "Quick context on what this is, because it's a little different. I'm "
    "basically your alter ego for dating. Instead of you swiping through "
    "strangers, I get to know you — like, actually know you — and then I go "
    "talk to other people's Kandals to find someone who'd genuinely fit. "
    "No profiles to write, no photos to agonize over. Just a conversation "
    "with me, and then I do the rest.\n\n"
    "For that to work though, I need to actually know you. We'll talk for "
    "about 10-15 minutes — starts with what you're into and what's firing in "
    "you right now, gets into the realer stuff later (how you love, what you "
    "need from a partner). A sentence or two is plenty per answer.\n\n"
    "Okay, diving in — what's something you're actually into right now? A "
    "rabbit hole, a show you can't shut up about, a project, a place you keep "
    "going back to, anything. Doesn't have to be deep."
)

def _parse_letter_abcd(text: str) -> int | None:
    """Extract A/B/C/D → index 0..3 from a user reply. Accepts '1'..'4' too."""
    import re as _re
    cleaned = text.strip().upper()
    m = _re.search(r"(?<![A-Z])([A-D])(?![A-Z])", cleaned)
    if m:
        return "ABCD".index(m.group(1))
    if cleaned in {"1", "2", "3", "4"}:
        return int(cleaned) - 1
    return None


_CONFIRM_YES = frozenset({
    "yes", "yeah", "yep", "y", "looks good", "correct", "confirmed",
    "that's right", "lock it in", "good", "perfect", "sure", "yea",
    "that's me", "spot on", "nailed it", "all good",
})


@dataclass
class ProfilingState:
    profile_id: UUID
    messages: list[dict] = field(default_factory=list)
    coverage: dict[str, float] = field(default_factory=dict)
    questions_asked: int = 0
    max_questions: int = TARGET_QUESTION_COUNT  # soft target, not a hard cap
    awaiting_confirmation: bool = False
    awaiting_spark: bool = False       # spark scenario MCQs
    awaiting_longterm: bool = False    # long-term compatibility MCQs
    awaiting_basics: bool = False      # logistics MCQs (gender, kids, etc.)
    pending_traits: dict | None = None
    pending_narrative: str | None = None
    spark_index: int = 0
    longterm_answers: list[int] = field(default_factory=list)
    longterm_index: int = 0
    basics_index: int = 0


@dataclass
class ProfilingTurn:
    reply: str
    is_complete: bool
    awaiting_confirmation: bool = False
    awaiting_spark: bool = False
    awaiting_longterm: bool = False
    awaiting_basics: bool = False
    traits: InferredTraits | None = None
    narrative: str | None = None
    coverage: dict[str, float] = field(default_factory=dict)


def _get_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _all_covered(coverage: dict[str, float]) -> bool:
    return all(coverage.get(dim, 0.0) >= COVERAGE_THRESHOLD for dim in TRAIT_DIMENSIONS)


def _missing_essentials(coverage: dict[str, float]) -> list[str]:
    """Essential pillars still below threshold."""
    return [d for d in ESSENTIAL_DIMENSIONS if coverage.get(d, 0.0) < ESSENTIAL_THRESHOLD]


class ProfilingEngine:
    """Drives an adaptive matchmaking conversation."""

    def __init__(self, pool_stats: PoolStats | None = None):
        self.pool_stats = pool_stats

    def start(self, profile_id: UUID) -> tuple[ProfilingState, str]:
        """Begin a new profiling conversation. Returns (state, opening_message)."""
        state = ProfilingState(
            profile_id=profile_id,
            messages=[{"role": "assistant", "content": OPENING_MESSAGE}],
            coverage={dim: 0.0 for dim in TRAIT_DIMENSIONS},
            questions_asked=1,
        )
        return state, OPENING_MESSAGE

    def next_turn(self, state: ProfilingState, user_reply: str) -> ProfilingTurn:
        """Process user reply, return next question or completion."""
        state.messages.append({"role": "user", "content": user_reply})

        # Deterministic MCQ loops: spark → long-term → basics
        if state.awaiting_spark:
            return self._handle_spark(state, user_reply)
        if state.awaiting_longterm:
            return self._handle_longterm(state, user_reply)
        if state.awaiting_basics:
            return self._handle_basics(state, user_reply)

        # Handle confirmation response
        if state.awaiting_confirmation:
            return self._handle_confirmation(state, user_reply)

        # Assess coverage periodically
        if state.questions_asked % COVERAGE_CHECK_INTERVAL == 0 or state.questions_asked >= state.max_questions - 1:
            state.coverage = assess_coverage(state.messages)

        # Finalize only when essentials are covered (or hard safety cap hit).
        # The target question count is a soft signal for pacing — not a stop.
        missing = _missing_essentials(state.coverage)
        # Hard rule: essentials MUST be covered. No path to summary while any
        # essential is below threshold, except the safety cap.
        essentials_ok = not missing
        should_finalize = (
            (essentials_ok and _all_covered(state.coverage) and state.questions_asked >= 5)
            or state.questions_asked >= HARD_QUESTION_CAP
        )

        if should_finalize:
            return self._prepare_summary(state)

        # Pull any memories from prior sessions (empty on first onboarding).
        try:
            memories = recall(state.profile_id)
            memory_block = format_memories_for_prompt(memories)
        except Exception as e:
            logger.warning("memory recall failed: %s", e)
            memory_block = ""

        system_prompt = build_conversation_prompt(
            questions_asked=state.questions_asked,
            max_questions=state.max_questions,
            coverage=state.coverage,
            pool_stats=self.pool_stats,
            memory_block=memory_block,
            missing_essentials=missing,
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

        return ProfilingTurn(
            reply=reply,
            is_complete=False,
            coverage=state.coverage,
        )

    def _prepare_summary(self, state: ProfilingState) -> ProfilingTurn:
        """Extract traits and generate confirmation summary."""
        traits, narrative, low_conf = extract_traits(state.messages)
        summary = self._generate_summary(traits, narrative, low_conf)

        state.messages.append({"role": "assistant", "content": summary})
        state.awaiting_confirmation = True
        state.pending_traits = traits.model_dump()
        state.pending_narrative = narrative

        return ProfilingTurn(
            reply=summary,
            is_complete=False,
            awaiting_confirmation=True,
            traits=traits,
            narrative=narrative,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    def _handle_confirmation(self, state: ProfilingState, user_reply: str) -> ProfilingTurn:
        """Handle user's response to the profile summary."""
        if user_reply.strip().lower() in _CONFIRM_YES:
            state.awaiting_confirmation = False
            # Transition to spark scenario MCQs.
            return self._start_spark(state)

        # User wants corrections — re-extract with correction context
        traits, narrative, low_conf = extract_traits(state.messages)
        summary = self._generate_summary(traits, narrative, low_conf)

        state.pending_traits = traits.model_dump()
        state.pending_narrative = narrative
        state.messages.append({"role": "assistant", "content": summary})

        return ProfilingTurn(
            reply=summary,
            is_complete=False,
            awaiting_confirmation=True,
            traits=traits,
            narrative=narrative,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    # --- Spark scenario MCQs (humor / conversational / energy / ambition) ---

    def _start_spark(self, state: ProfilingState) -> ProfilingTurn:
        """Kick off the spark scenario MCQ loop."""
        from kandal.profiling.spark_mcqs import next_question
        state.spark_index = 0
        nq = next_question(state.pending_traits or {}, state.spark_index)
        if nq is None:
            return self._start_longterm(state)
        question, idx = nq
        state.awaiting_spark = True
        state.spark_index = idx
        intro = (
            "Perfect. Okay, a few quick scenario picks to sharpen the signal.\n\n"
            + question.prompt
        )
        state.messages.append({"role": "assistant", "content": intro})
        return ProfilingTurn(
            reply=intro,
            is_complete=False,
            awaiting_spark=True,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    def _handle_spark(self, state: ProfilingState, user_reply: str) -> ProfilingTurn:
        from kandal.profiling.spark_mcqs import QUESTIONS, apply_answer, next_question

        question = QUESTIONS[state.spark_index]
        parsed = question.parse(user_reply)
        if parsed is None:
            retry = f"Didn't quite catch that. Pick a letter (A-D).\n\n{question.prompt}"
            state.messages.append({"role": "assistant", "content": retry})
            return ProfilingTurn(
                reply=retry,
                is_complete=False,
                awaiting_spark=True,
                coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
            )

        apply_answer(state.pending_traits, question, parsed)
        nq = next_question(state.pending_traits, state.spark_index + 1)
        if nq is None:
            state.awaiting_spark = False
            return self._start_longterm(state)

        next_q, next_idx = nq
        state.spark_index = next_idx
        state.messages.append({"role": "assistant", "content": next_q.prompt})
        return ProfilingTurn(
            reply=next_q.prompt,
            is_complete=False,
            awaiting_spark=True,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    # --- Long-term compatibility MCQs (attachment / LL / conflict / history) ---

    def _start_longterm(self, state: ProfilingState) -> ProfilingTurn:
        """Kick off the long-term compatibility MCQ loop (questionnaire/questions.py)."""
        from kandal.questionnaire.questions import QUESTIONS as LT_QUESTIONS
        state.longterm_index = 0
        state.longterm_answers = []
        if not LT_QUESTIONS:
            return self._start_basics(state)
        q = LT_QUESTIONS[0]
        state.awaiting_longterm = True
        prompt = self._format_longterm_prompt(q)
        intro = "A few more quick scenarios — these help me understand the long-game stuff.\n\n" + prompt
        state.messages.append({"role": "assistant", "content": intro})
        return ProfilingTurn(
            reply=intro,
            is_complete=False,
            awaiting_longterm=True,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    @staticmethod
    def _format_longterm_prompt(q: dict) -> str:
        letters = "ABCD"
        lines = [q["text"], ""]
        for i, opt in enumerate(q["options"]):
            lines.append(f"{letters[i]}) {opt['text']}")
        return "\n".join(lines)

    def _handle_longterm(self, state: ProfilingState, user_reply: str) -> ProfilingTurn:
        from kandal.questionnaire.questions import QUESTIONS as LT_QUESTIONS

        q = LT_QUESTIONS[state.longterm_index]
        parsed = _parse_letter_abcd(user_reply)
        if parsed is None:
            retry = f"Didn't quite catch that. Pick a letter (A-D).\n\n{self._format_longterm_prompt(q)}"
            state.messages.append({"role": "assistant", "content": retry})
            return ProfilingTurn(
                reply=retry,
                is_complete=False,
                awaiting_longterm=True,
                coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
            )

        state.longterm_answers.append(parsed)
        state.longterm_index += 1

        if state.longterm_index >= len(LT_QUESTIONS):
            # All answered — run inference and merge into pending_traits.
            from kandal.questionnaire.inference import infer_traits
            lt_traits = infer_traits(state.longterm_answers)
            merge = {
                "attachment_style": lt_traits.attachment_style,
                "love_language_giving": lt_traits.love_language_giving,
                "love_language_receiving": lt_traits.love_language_receiving,
                "conflict_style": lt_traits.conflict_style,
                "relationship_history": lt_traits.relationship_history,
            }
            if state.pending_traits is None:
                state.pending_traits = {}
            state.pending_traits.update(merge)
            state.awaiting_longterm = False
            return self._start_basics(state)

        next_q = LT_QUESTIONS[state.longterm_index]
        prompt = self._format_longterm_prompt(next_q)
        state.messages.append({"role": "assistant", "content": prompt})
        return ProfilingTurn(
            reply=prompt,
            is_complete=False,
            awaiting_longterm=True,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    # --- Basics (logistics) MCQs ---

    def _start_basics(self, state: ProfilingState) -> ProfilingTurn:
        """Kick off the post-summary basics MCQ loop."""
        from kandal.profiling.basics import next_question
        state.basics_index = 0
        nq = next_question(state.pending_traits or {}, state.basics_index)
        if nq is None:
            # Nothing to collect — finalize directly.
            traits = InferredTraits(**(state.pending_traits or {}))
            return self._finalize(state, traits, state.pending_narrative)
        question, idx = nq
        state.awaiting_basics = True
        state.basics_index = idx
        intro = (
            "Almost done — just a few quick logistics.\n\n"
            + question.prompt
        )
        state.messages.append({"role": "assistant", "content": intro})
        return ProfilingTurn(
            reply=intro,
            is_complete=False,
            awaiting_basics=True,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    def _handle_basics(self, state: ProfilingState, user_reply: str) -> ProfilingTurn:
        """Parse the user's basics MCQ answer and advance to the next, or finalize."""
        from kandal.profiling.basics import QUESTIONS, apply_answer, next_question

        question = QUESTIONS[state.basics_index]
        parsed = question.parse(user_reply)
        if parsed is None:
            retry = f"Didn't quite catch that. Pick a letter, or tell me in your own words.\n\n{question.prompt}"
            state.messages.append({"role": "assistant", "content": retry})
            return ProfilingTurn(
                reply=retry,
                is_complete=False,
                awaiting_basics=True,
                coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
            )

        apply_answer(state.pending_traits, question, parsed)

        nq = next_question(state.pending_traits, state.basics_index + 1)
        if nq is None:
            state.awaiting_basics = False
            traits = InferredTraits(**(state.pending_traits or {}))
            return self._finalize(state, traits, state.pending_narrative)

        next_q, next_idx = nq
        state.basics_index = next_idx
        state.messages.append({"role": "assistant", "content": next_q.prompt})
        return ProfilingTurn(
            reply=next_q.prompt,
            is_complete=False,
            awaiting_basics=True,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    def _finalize(self, state: ProfilingState, traits: InferredTraits, narrative: str) -> ProfilingTurn:
        """Wrap up after all post-summary MCQs are done."""
        closing = (
            "Locked in. Your alter ego is live and ready to find your person."
        )
        state.messages.append({"role": "assistant", "content": closing})
        state.awaiting_confirmation = False
        state.awaiting_spark = False
        state.awaiting_longterm = False
        state.awaiting_basics = False
        state.coverage = {dim: 1.0 for dim in TRAIT_DIMENSIONS}

        try:
            seed_from_onboarding(state.profile_id, state.pending_traits or {}, narrative)
        except Exception as e:
            logger.warning("memory seed failed for %s: %s", state.profile_id, e)

        return ProfilingTurn(
            reply=closing,
            is_complete=True,
            traits=traits,
            narrative=narrative,
            coverage=state.coverage,
        )

    def _generate_summary(
        self, traits: InferredTraits, narrative: str, low_conf: set[str] | None = None
    ) -> str:
        """Use Claude to generate a human-readable summary for confirmation."""
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": build_summary_prompt(traits, narrative, low_conf or set()),
            }],
        )
        return response.content[0].text
