-- Spark signals: what creates the initial hit between two people.
-- Freeform text collected during onboarding (taste, obsessions, past attraction,
-- contradictions), plus structured favorite places for date booking.
-- Scenario MCQ results go on preferences alongside the existing categorical traits.

-- Freeform signals on profiles
ALTER TABLE profiles ADD COLUMN taste_fingerprint TEXT;
ALTER TABLE profiles ADD COLUMN current_obsession TEXT;
ALTER TABLE profiles ADD COLUMN two_hour_topic TEXT;
ALTER TABLE profiles ADD COLUMN contradiction_hook TEXT;
ALTER TABLE profiles ADD COLUMN past_attraction TEXT;

-- Structured favorite places — powers both spark matching and later date booking.
-- Shape: [{"name": "...", "type": "...", "neighborhood": "...", "note": "..."}]
-- Only "name" is required; the rest are best-effort.
ALTER TABLE profiles ADD COLUMN favorite_places JSONB;

-- Scenario MCQ results — categorical spark traits
ALTER TABLE preferences ADD COLUMN humor_style TEXT;
ALTER TABLE preferences ADD COLUMN conversational_texture TEXT;
ALTER TABLE preferences ADD COLUMN energy_pace TEXT;
ALTER TABLE preferences ADD COLUMN ambition_shape TEXT;

NOTIFY pgrst, 'reload schema';
