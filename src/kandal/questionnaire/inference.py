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
    # Basic info extracted from conversation (optional)
    name: str | None = None
    gender: str | None = None
    current_city: str | None = None
    # Extended fields from adaptive profiling (optional for backward compat)
    gender_preference: list[str] | None = None
    cultural_preferences: list[str] | None = None
    birth_date: str | None = None          # ISO format "YYYY-MM-DD"
    birth_time_approx: str | None = None   # "HH:00-HH:00" 3hr window
    birth_city: str | None = None
    dimension_weights: dict[str, float] | None = None  # personalized scoring priorities
    # Emotional dynamics — the core long-term matching signal
    emotional_giving: str | None = None    # how this person makes partners feel
    emotional_needs: str | None = None     # what they need to feel from a partner
    # Spark signals — what creates the initial hit on a first date
    taste_fingerprint: str | None = None   # 3 things they'd recommend, any category
    current_obsession: str | None = None   # what they're in right now
    two_hour_topic: str | None = None      # what they could talk about for hours
    contradiction_hook: str | None = None  # "I'm a [ ] who also [ ]"
    past_attraction: str | None = None     # what pulled them in last time — real not stated
    favorite_places: list[dict] | None = None  # [{"name","type","neighborhood","note"}]
    # Spark MCQ results — categorical first-date signals
    humor_style: str | None = None
    conversational_texture: str | None = None
    energy_pace: str | None = None
    ambition_shape: str | None = None
    # Tier 1 tag lists — extracted from conversation
    interests: list[str] | None = None
    personality: list[str] | None = None
    partner_personality: list[str] | None = None
    values: list[str] | None = None
    partner_values: list[str] | None = None
    lifestyle: list[str] | None = None
    # Lifestyle basics — dealbreaker-grade filters
    age_min: int | None = None
    age_max: int | None = None
    max_distance_km: int | None = None
    relationship_intent: str | None = None        # casual / dating / serious / marriage_track
    has_kids: str | None = None                   # yes / no
    wants_kids: str | None = None                 # yes / no / maybe / open
    relationship_structure: str | None = None     # monogamous / enm / poly / open
    religion: str | None = None                   # free text
    religion_importance: str | None = None        # not_important / somewhat / very
    drinks: str | None = None                     # never / socially / regularly
    smokes: str | None = None                     # never / socially / regularly
    cannabis: str | None = None                   # never / socially / regularly


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
