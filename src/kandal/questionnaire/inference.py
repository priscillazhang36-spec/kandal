"""Inference engine: scenario answers → personality traits."""

from pydantic import BaseModel

from kandal.questionnaire.questions import QUESTIONS

ALL_LOVE_LANGUAGES = [
    "words_of_affirmation",
    "quality_time",
    "physical_touch",
    "acts_of_service",
    "gifts",
]

# Tie-breaking priority (first = preferred on tie)
_ATTACHMENT_PRIORITY = ["secure", "anxious", "avoidant", "disorganized"]
_CONFLICT_PRIORITY = ["collaborative", "talk_immediately", "need_space", "avoidant"]
_HISTORY_PRIORITY = [
    "long_term",
    "mostly_casual",
    "recently_out_of_ltr",
    "limited_experience",
]


class InferredTraits(BaseModel):
    attachment_style: str
    love_language_giving: list[str]
    love_language_receiving: list[str]
    conflict_style: str
    relationship_history: str


def _argmax_with_priority(counts: dict[str, int], priority: list[str]) -> str:
    """Return the key with the highest count, breaking ties by priority order."""
    best_val = -1
    best_key = priority[0]
    for key in priority:
        if counts.get(key, 0) > best_val:
            best_val = counts.get(key, 0)
            best_key = key
    return best_key


def _ranked_love_languages(counts: dict[str, int]) -> list[str]:
    """Sort love languages by signal count (desc), then by default order for ties."""
    return sorted(
        ALL_LOVE_LANGUAGES,
        key=lambda lang: (-counts.get(lang, 0), ALL_LOVE_LANGUAGES.index(lang)),
    )


def infer_traits(answers: list[int]) -> InferredTraits:
    """Pure function. Takes 10 answer indices (0-3), returns inferred traits."""
    if len(answers) != len(QUESTIONS):
        raise ValueError(f"Expected {len(QUESTIONS)} answers, got {len(answers)}")

    accumulators: dict[str, dict[str, int]] = {
        "attachment": {},
        "conflict": {},
        "love_giving": {},
        "love_receiving": {},
        "history": {},
    }

    for question, answer_idx in zip(QUESTIONS, answers):
        if not (0 <= answer_idx < len(question["options"])):
            raise ValueError(f"Answer {answer_idx} out of range for question {question['id']}")

        signals = question["options"][answer_idx]["signals"]
        for signal_key, weight in signals.items():
            dimension, value = signal_key.split(":", 1)
            if dimension not in accumulators:
                accumulators[dimension] = {}
            accumulators[dimension][value] = accumulators[dimension].get(value, 0) + weight

    return InferredTraits(
        attachment_style=_argmax_with_priority(
            accumulators["attachment"], _ATTACHMENT_PRIORITY
        ),
        love_language_giving=_ranked_love_languages(accumulators["love_giving"]),
        love_language_receiving=_ranked_love_languages(accumulators["love_receiving"]),
        conflict_style=_argmax_with_priority(
            accumulators["conflict"], _CONFLICT_PRIORITY
        ),
        relationship_history=_argmax_with_priority(
            accumulators["history"], _HISTORY_PRIORITY
        ),
    )
