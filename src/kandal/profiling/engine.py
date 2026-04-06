"""Adaptive profiling conversation engine."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from uuid import UUID

import anthropic

from kandal.core.config import get_settings
from kandal.profiling.extractor import assess_coverage, extract_traits
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
DEFAULT_MAX_QUESTIONS = 14
# Assess coverage every N turns to reduce LLM calls
COVERAGE_CHECK_INTERVAL = 2

OPENING_MESSAGE = (
    "Hey! I'm going to be your dating alter ego — think of me as a version "
    "of you that knows exactly what you want and goes out to find it. But "
    "first, I need to really get you.\n\n"
    "So tell me — what does an amazing relationship look like in your world?"
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
    "B": ["attachment_style", "love_language_fit"],
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
    max_questions: int = DEFAULT_MAX_QUESTIONS
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

        # Check if we should finalize
        should_finalize = (
            _all_covered(state.coverage) and state.questions_asked >= 5
        ) or state.questions_asked >= state.max_questions

        if should_finalize:
            return self._prepare_summary(state)

        # Generate next question
        system_prompt = build_conversation_prompt(
            questions_asked=state.questions_asked,
            max_questions=state.max_questions,
            coverage=state.coverage,
            pool_stats=self.pool_stats,
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
        traits, narrative = extract_traits(state.messages)
        summary = self._generate_summary(traits, narrative)

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

            # If conversation already gave us weights, finalize directly
            if traits.dimension_weights:
                return self._finalize(state, traits, state.pending_narrative)

            # Otherwise, ask for ranking
            return self._ask_ranking(state)

        # User wants corrections — re-extract with correction context
        traits, narrative = extract_traits(state.messages)
        summary = self._generate_summary(traits, narrative)

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

        return ProfilingTurn(
            reply=closing,
            is_complete=True,
            traits=traits,
            narrative=narrative,
            coverage=state.coverage,
        )

    def _generate_summary(self, traits: InferredTraits, narrative: str) -> str:
        """Use Claude to generate a human-readable summary for confirmation."""
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": build_summary_prompt(traits, narrative),
            }],
        )
        return response.content[0].text
