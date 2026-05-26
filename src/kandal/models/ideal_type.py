"""Pydantic models for the ideal_type_discovery artifact.

Mirrors the `ideal_types` Supabase table. The artifact is the output of the
`ideal_type_discovery` onboarding mode — a clarity exercise. It does not feed
matching directly (no preferences row written), but it can later be used as
context if the user opts into full_discovery.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PastPull(BaseModel):
    """A single past relationship arc the user narrated in Stage 1.

    Captures BOTH ends: what initially drew them in (pull) AND what eventually
    broke it apart or what creates friction (break). The break side is as
    important as the pull side — it surfaces the negative pattern that keeps
    not working.
    """

    description: str | None = None              # paraphrased ~30 word context
    what_brought_together: str | None = None    # initial pull paraphrase
    what_broke_apart: str | None = None         # break / friction paraphrase
    brought_quote: str | None = None            # 20-50 word verbatim on the pull
    broke_quote: str | None = None              # 20-50 word verbatim on the break


class VignettePair(BaseModel):
    """A single LLM-generated forced-choice pair shown to the user in Stage 3."""

    axis: str                            # the dimension the pair contrasts (e.g. 'creative_vs_service')
    a: dict                              # {name, sketch}
    b: dict                              # {name, sketch}


class VignetteChoice(BaseModel):
    """User's response to one vignette pair."""

    pair_index: int
    picked: str                          # 'a' or 'b'
    tipped_reason: str | None = None     # paraphrased ~25 word note on why
    tipped_quote: str | None = None      # 20-50 word verbatim slice


class IdealType(BaseModel):
    """The full artifact row, matching the ideal_types table."""

    id: UUID | None = None
    profile_id: UUID

    # Stage 4 synthesized artifact
    pull_pattern: str | None = None       # positive: what kind of person draws them in
    break_pattern: str | None = None      # negative: what tends to create friction / end things
    pull_pattern_quote: str | None = None
    partner_traits: list[str] = Field(default_factory=list)

    # Stage 0 demographic dealbreakers (partner-facing)
    gender_preference: list[str] = Field(default_factory=list)
    age_min: int | None = None
    age_max: int | None = None
    ethnicity_preference: list[str] = Field(default_factory=list)
    religion_preference: list[str] = Field(default_factory=list)
    relationship_intent: str | None = None
    partner_wants_kids: str | None = None
    partner_smokes_max: str | None = None
    partner_drinks_max: str | None = None
    partner_cannabis_max: str | None = None
    visual_type: str | None = None         # legacy — no longer collected; superseded by celebrity_choices
    visual_importance: str | None = None   # high | secondary | low | open
    celebrity_choices: list[dict] = Field(default_factory=list)

    # Raw inputs
    past_pulls: list[PastPull] = Field(default_factory=list)
    icks: list[str] = Field(default_factory=list)

    # Vignette stage
    vignettes: list[VignettePair] = Field(default_factory=list)
    vignette_choices: list[VignetteChoice] = Field(default_factory=list)

    created_at: datetime | None = None
    updated_at: datetime | None = None
