"""Adaptive profiling conversation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

import anthropic

from kandal.core.config import get_settings
from kandal.profiling.extractor import assess_coverage, extract_traits
from kandal.profiling.pool_stats import PoolStats
from kandal.profiling.prompts import TRAIT_DIMENSIONS, build_conversation_prompt
from kandal.questionnaire.inference import InferredTraits

logger = logging.getLogger(__name__)

COVERAGE_THRESHOLD = 0.7
DEFAULT_MAX_QUESTIONS = 10
# Assess coverage every N turns to reduce LLM calls
COVERAGE_CHECK_INTERVAL = 2

OPENING_MESSAGE = (
    "Hey! I'm your matchmaker. I'd love to get to know you so I can find "
    "someone great for you. Let's start with this: What does a really great "
    "relationship look like to you?"
)


@dataclass
class ProfilingState:
    profile_id: UUID
    messages: list[dict] = field(default_factory=list)
    coverage: dict[str, float] = field(default_factory=dict)
    questions_asked: int = 0
    max_questions: int = DEFAULT_MAX_QUESTIONS


@dataclass
class ProfilingTurn:
    reply: str
    is_complete: bool
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
        """Process user reply, return next question or completion.

        This is synchronous — acceptable for SMS (Twilio 15s timeout)
        since each Claude call takes ~1-3s.
        """
        # Append user message
        state.messages.append({"role": "user", "content": user_reply})

        # Assess coverage periodically
        if state.questions_asked % COVERAGE_CHECK_INTERVAL == 0 or state.questions_asked >= state.max_questions - 1:
            state.coverage = assess_coverage(state.messages)

        # Check if we should finalize
        should_finalize = (
            _all_covered(state.coverage) and state.questions_asked >= 3
        ) or state.questions_asked >= state.max_questions

        if should_finalize:
            return self._finalize(state)

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
            max_tokens=300,
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

    def _finalize(self, state: ProfilingState) -> ProfilingTurn:
        """Extract traits and narrative from the completed conversation."""
        traits, narrative = extract_traits(state.messages)

        closing = (
            "Thanks for sharing all of that with me! I feel like I have a "
            "really good sense of who you are. Let me work on finding your "
            "matches. But first, a few quick basics..."
        )

        state.messages.append({"role": "assistant", "content": closing})
        state.coverage = {dim: 1.0 for dim in TRAIT_DIMENSIONS}

        return ProfilingTurn(
            reply=closing,
            is_complete=True,
            traits=traits,
            narrative=narrative,
            coverage=state.coverage,
        )
