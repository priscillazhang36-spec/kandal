"""Adaptive profiling conversation engine."""

from __future__ import annotations

import logging
import re
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

# Pillars Kandal MUST gather signal on before finalizing. The categorical
# self-pillars (attachment / love languages / conflict style) are still tracked
# in coverage and fed to the ranker — but they're weak self-reports on their own,
# so we don't block on them. The qualitative narrative + partner-side signal is
# what actually drives the LLM judge.
ESSENTIAL_DIMENSIONS = [
    "emotional_dynamics",      # giving + needs — the qualitative core
    "relationship_history",    # huge context for any read
    "partner_preferences",     # dealbreaker filter can't run without this
    "matching_priorities",     # LLM judge needs "what they're looking for"
    "birth_info",              # birthday + current city — basic logistics
    "lifestyle_basics",        # intent, kids, age range, distance (MCQ set)
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
    "For that to work though, I need to actually know you. So we're gonna "
    "talk for about 10-15 minutes. Starts easy (what you're into, how you "
    "spend your time) and gets into the realer stuff later (how you love, "
    "what you need from a partner). No right answers, no essays — a sentence "
    "or two is plenty. The more honest you are, the better I can do my job.\n\n"
    "Okay, easy one first — what's something that made you smile this week?"
)

RANKING_QUESTION = (
    "Ok last thing — when I'm out there finding your person, what should I "
    "care about most? Rank these 1-5 (1 = most important):\n\n"
    "A) Shared interests & lifestyle\n"
    "B) Emotional connection (attachment, love languages)\n"
    "C) How you both handle conflict\n"
    "D) Destiny & cosmic alignment\n"
    "E) Shared values & personality"
)

_CONFIRM_YES = frozenset({
    "yes", "yeah", "yep", "y", "looks good", "correct", "confirmed",
    "that's right", "lock it in", "good", "perfect", "sure", "yea",
    "that's me", "spot on", "nailed it", "all good",
})

# Ranking → weight distribution
# Rank 1 gets the most weight, rank 5 gets the least
_RANK_WEIGHTS = {1: 0.35, 2: 0.25, 3: 0.20, 4: 0.12, 5: 0.08}

# Each ranked category maps to scoring dimensions
_CATEGORY_DIMENSIONS = {
    "A": ["interest_overlap", "personality_match", "lifestyle_signals"],
    "B": ["attachment_style", "love_language_fit", "emotional_fit"],
    "C": ["conflict_style", "communication_style"],
    "D": ["bazi_compatibility"],
    "E": ["values_alignment", "relationship_history"],
}


def _ranking_to_weights(ranking: list[str]) -> dict[str, float]:
    """Convert a ranked list of categories (e.g. ['C','A','D','B','E']) to dimension weights.

    Each category gets a weight based on its rank position, then that weight is
    distributed evenly among the category's dimensions.
    """
    weights: dict[str, float] = {}
    for rank_pos, category in enumerate(ranking, 1):
        category_weight = _RANK_WEIGHTS[rank_pos]
        dims = _CATEGORY_DIMENSIONS[category]
        per_dim = round(category_weight / len(dims), 4)
        for dim in dims:
            weights[dim] = per_dim

    # Normalize to exactly 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}
    return weights


def _parse_ranking(text: str) -> list[str] | None:
    """Parse a ranking response into an ordered list of category letters.

    Accepts formats like:
    - "C, A, D, B, E"
    - "CADBE"
    - "3 1 4 2 5" (positional: A=3rd, B=1st, etc.)
    - "C A D B E"
    """
    cleaned = text.strip().upper()

    # Try letter-based: extract A-E letters in order
    letters = [ch for ch in cleaned if ch in "ABCDE"]
    if len(letters) == 5 and len(set(letters)) == 5:
        return letters

    # Try number-based: "3 1 4 2 5" means A is rank 3, B is rank 1, etc.
    nums = re.findall(r"[1-5]", cleaned)
    if len(nums) == 5 and len(set(nums)) == 5:
        categories = list("ABCDE")
        ranked = sorted(zip(categories, [int(n) for n in nums]), key=lambda x: x[1])
        return [cat for cat, _ in ranked]

    return None


@dataclass
class ProfilingState:
    profile_id: UUID
    messages: list[dict] = field(default_factory=list)
    coverage: dict[str, float] = field(default_factory=dict)
    questions_asked: int = 0
    max_questions: int = TARGET_QUESTION_COUNT  # soft target, not a hard cap
    awaiting_confirmation: bool = False
    awaiting_ranking: bool = False
    pending_traits: dict | None = None
    pending_narrative: str | None = None


@dataclass
class ProfilingTurn:
    reply: str
    is_complete: bool
    awaiting_confirmation: bool = False
    awaiting_ranking: bool = False
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

        # Handle ranking response
        if state.awaiting_ranking:
            return self._handle_ranking(state, user_reply)

        # Handle confirmation response
        if state.awaiting_confirmation:
            return self._handle_confirmation(state, user_reply)

        # Assess coverage periodically
        if state.questions_asked % COVERAGE_CHECK_INTERVAL == 0 or state.questions_asked >= state.max_questions - 1:
            state.coverage = assess_coverage(state.messages)

        # Finalize only when essentials are covered (or hard safety cap hit).
        # The target question count is a soft signal for pacing — not a stop.
        missing = _missing_essentials(state.coverage)
        should_finalize = (
            (_all_covered(state.coverage) and state.questions_asked >= 5)
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
            traits = InferredTraits(**state.pending_traits)

            # Always ask ranking so the user explicitly controls their priorities
            return self._ask_ranking(state)

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

    def _ask_ranking(self, state: ProfilingState) -> ProfilingTurn:
        """Ask the user to rank what matters most."""
        state.awaiting_ranking = True
        state.messages.append({"role": "assistant", "content": RANKING_QUESTION})

        return ProfilingTurn(
            reply=RANKING_QUESTION,
            is_complete=False,
            awaiting_ranking=True,
            coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
        )

    def _handle_ranking(self, state: ProfilingState, user_reply: str) -> ProfilingTurn:
        """Parse ranking response and finalize."""
        ranking = _parse_ranking(user_reply)

        if ranking is None:
            retry = (
                "Hmm, I didn't catch that. Just give me the letters in order "
                "from most to least important — like CADBE or C, A, D, B, E"
            )
            state.messages.append({"role": "assistant", "content": retry})
            return ProfilingTurn(
                reply=retry,
                is_complete=False,
                awaiting_ranking=True,
                coverage={dim: 1.0 for dim in TRAIT_DIMENSIONS},
            )

        weights = _ranking_to_weights(ranking)
        traits = InferredTraits(**state.pending_traits)
        traits = traits.model_copy(update={"dimension_weights": weights})

        state.pending_traits = traits.model_dump()
        state.awaiting_ranking = False

        return self._finalize(state, traits, state.pending_narrative)

    def _finalize(self, state: ProfilingState, traits: InferredTraits, narrative: str) -> ProfilingTurn:
        """Confirm and finalize after user approval."""
        closing = (
            "Locked in. Your alter ego is live and ready to find your person. "
            "Just a few quick basics and we're done..."
        )
        state.messages.append({"role": "assistant", "content": closing})
        state.awaiting_confirmation = False
        state.awaiting_ranking = False
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
