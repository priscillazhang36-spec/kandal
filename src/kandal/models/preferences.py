from uuid import UUID

from pydantic import BaseModel


class Preferences(BaseModel):
    id: UUID
    profile_id: UUID
    min_age: int = 18
    max_age: int = 99
    max_distance_km: int = 50
    gender_preferences: list[str] = []
    relationship_types: list[str] = ["long_term"]
    interests: list[str] = []
    personality: list[str] = []
    partner_personality: list[str] = []
    values: list[str] = []
    communication_style: str = "balanced"
    lifestyle: list[str] = []
    selectivity: str = "balanced"
    cultural_preferences: list[str] = []
    # Tier 2 — inferred from questionnaire
    attachment_style: str | None = None
    love_language_giving: list[str] = []
    love_language_receiving: list[str] = []
    conflict_style: str | None = None
    relationship_history: str | None = None
    # Spark MCQ results — categorical first-date signals
    humor_style: str | None = None
    conversational_texture: str | None = None
    energy_pace: str | None = None
    ambition_shape: str | None = None
    visual_type: str | None = None        # appearance bucket (classic/artsy/athletic/no_strong_type) v4.1
    visual_preference: str | None = None  # freeform appearance preference, v4.1
    # Lifestyle basics (00010) — load-side parity with prod schema. Used by dealbreakers (v4.2).
    relationship_intent: str | None = None       # casual / dating / serious / marriage_track
    has_kids: str | None = None                  # yes / no
    wants_kids: str | None = None                # yes / no / maybe / open
    relationship_structure: str | None = None    # monogamous / enm / poly / open
    religion: str | None = None                  # free text
    religion_importance: str | None = None       # not_important / somewhat / very
    drinks: str | None = None                    # never / socially / regularly
    smokes: str | None = None                    # never / socially / regularly
    cannabis: str | None = None                  # never / socially / regularly
    # Paired tolerance (v4.2) — what the user accepts FROM A PARTNER
    partner_wants_kids: str | None = None        # yes / no / open
    partner_substances_max: str | None = None    # never / socially / regularly / open
