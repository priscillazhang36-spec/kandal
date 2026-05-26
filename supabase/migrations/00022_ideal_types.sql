-- Ideal-type artifact table. Output of the ideal_type_discovery onboarding
-- mode — a clarity exercise that helps the user understand what they're
-- actually looking for. Does NOT make the user matchable (no preferences row,
-- no profiles.is_active flip). User can re-run later and edit fields.
--
-- Holds: Stage 0 demographic dealbreakers (gender, age, religion, etc.),
-- Stage 1+2 raw past-pull and ick inputs, Stage 3 LLM-generated vignette
-- pairs and the user's choices, and the Stage 4 synthesized pattern artifact
-- (pull_pattern + verbatim quote + ranked partner traits). Also stores the
-- session state (messages, stage, sub_state) so the conversation can resume.

CREATE TABLE ideal_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,

    -- Stage 4 synthesized artifact
    pull_pattern TEXT,
    pull_pattern_quote TEXT,
    partner_traits TEXT[] NOT NULL DEFAULT '{}',

    -- Stage 0 demographic dealbreakers (partner-facing)
    gender_preference TEXT[] NOT NULL DEFAULT '{}',
    age_min INT,
    age_max INT,
    ethnicity_preference TEXT[] NOT NULL DEFAULT '{}',
    religion_preference TEXT[] NOT NULL DEFAULT '{}',
    relationship_intent TEXT,
    partner_wants_kids TEXT,
    partner_smokes_max TEXT,
    partner_drinks_max TEXT,
    partner_cannabis_max TEXT,

    -- Stage 1+2 raw inputs (preserved for re-extraction / debugging)
    past_pulls JSONB NOT NULL DEFAULT '[]',
    icks TEXT[] NOT NULL DEFAULT '{}',

    -- Stage 3 vignettes (LLM-generated pairs + user choices)
    vignettes JSONB NOT NULL DEFAULT '[]',
    vignette_choices JSONB NOT NULL DEFAULT '[]',

    -- Session state — drives resumability inside the engine
    messages JSONB NOT NULL DEFAULT '[]',
    stage TEXT NOT NULL DEFAULT 'dealbreakers',
    sub_state JSONB NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ideal_types_profile ON ideal_types(profile_id);

NOTIFY pgrst, 'reload schema';
