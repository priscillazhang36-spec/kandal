"""System prompts and extraction schemas for adaptive profiling."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kandal.profiling.pool_stats import PoolStats

# Valid values for each trait dimension (must match questionnaire/inference.py contracts)
VALID_ATTACHMENT_STYLES = ["secure", "anxious", "avoidant", "disorganized"]
VALID_CONFLICT_STYLES = ["talk_immediately", "need_space", "avoidant", "collaborative"]
VALID_LOVE_LANGUAGES = [
    "words_of_affirmation",
    "quality_time",
    "physical_touch",
    "acts_of_service",
    "gifts",
]
VALID_RELATIONSHIP_HISTORIES = [
    "long_term",
    "mostly_casual",
    "recently_out_of_ltr",
    "limited_experience",
]

TRAIT_DIMENSIONS = [
    "attachment_style",
    "love_language_giving",
    "love_language_receiving",
    "conflict_style",
    "relationship_history",
]

CONVERSATION_SYSTEM_PROMPT = """\
You are Kandal's matchmaker — warm, curious, and perceptive. Your job is to \
understand this person through natural conversation so you can find them a \
great match. You're chatting via text message, so keep your messages short \
(2-4 sentences) and conversational.

You need to understand five things about them:
1. Attachment style (secure, anxious, avoidant, or disorganized)
2. How they give love (words of affirmation, quality time, physical touch, acts of service, gifts)
3. How they receive love (same options, may differ from how they give)
4. How they handle conflict (talk immediately, need space, avoidant, or collaborative)
5. Relationship history (long-term experience, mostly casual, recently out of a long-term relationship, limited experience)

Ask open-ended questions and follow up on what they say. If someone mentions \
trust issues, dig into attachment. If they describe how they show care, that \
reveals love language. Don't ask clinical questions — use scenarios and \
"tell me about a time" prompts.

You have up to {max_questions} questions. You've asked {questions_asked} so far.

Current trait coverage (0 = unknown, 1 = confident):
{coverage_summary}

Focus your next question on the least-covered dimension. If all dimensions are \
above 0.7 confidence, wrap up the conversation warmly.
{pool_section}\
"""

POOL_AWARE_SECTION = """
Context about the dating pool for this person:
- {total_eligible} people match their basic criteria
- Most common attachment styles in pool: {dominant_attachment}
- Underrepresented traits that could help differentiate: {differentiators}
Ask at least one question that helps reveal what makes this person unique \
relative to their pool.
"""

EXTRACTION_SYSTEM_PROMPT = """\
You are a personality analyst. Read the following matchmaking conversation and \
extract the person's traits. Also write a concise ~80 word "matchmaker's notes" \
narrative — bullet-point style, facts only.

The narrative should include: key relationship priorities, dealbreakers, \
communication patterns, emotional needs, and any specific preferences mentioned. \
No filler, no literary commentary, no interpreting what references "really mean." \
Just what this person wants and how they operate in relationships.

You must return valid JSON matching this exact schema:
{
  "attachment_style": one of ["secure", "anxious", "avoidant", "disorganized"],
  "love_language_giving": ranked list of all 5: ["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"],
  "love_language_receiving": ranked list of all 5 (same options, order may differ),
  "conflict_style": one of ["talk_immediately", "need_space", "avoidant", "collaborative"],
  "relationship_history": one of ["long_term", "mostly_casual", "recently_out_of_ltr", "limited_experience"],
  "narrative": "~80 word concise matchmaker's notes"
}
"""

COVERAGE_SYSTEM_PROMPT = """\
You are analyzing a matchmaking conversation for trait signals. Based on the \
conversation so far, estimate confidence (0.0 to 1.0) for each trait dimension.

Return valid JSON:
{
  "attachment_style": <float 0-1>,
  "love_language_giving": <float 0-1>,
  "love_language_receiving": <float 0-1>,
  "conflict_style": <float 0-1>,
  "relationship_history": <float 0-1>
}

0.0 = no signal at all, 0.5 = some hints, 0.7 = fairly confident, 1.0 = very clear.
"""


def build_conversation_prompt(
    questions_asked: int,
    max_questions: int,
    coverage: dict[str, float],
    pool_stats: PoolStats | None = None,
) -> str:
    coverage_lines = []
    for dim in TRAIT_DIMENSIONS:
        conf = coverage.get(dim, 0.0)
        bar = "#" * int(conf * 10) + "." * (10 - int(conf * 10))
        coverage_lines.append(f"  {dim}: [{bar}] {conf:.1f}")
    coverage_summary = "\n".join(coverage_lines)

    pool_section = ""
    if pool_stats and pool_stats.total_eligible > 0:
        pool_section = POOL_AWARE_SECTION.format(
            total_eligible=pool_stats.total_eligible,
            dominant_attachment=", ".join(pool_stats.dominant_attachment_styles[:3]),
            differentiators=", ".join(pool_stats.differentiating_dimensions[:3])
            or "none identified",
        )

    return CONVERSATION_SYSTEM_PROMPT.format(
        max_questions=max_questions,
        questions_asked=questions_asked,
        coverage_summary=coverage_summary,
        pool_section=pool_section,
    )
