-- Add birth info to profiles for Bazi compatibility scoring
ALTER TABLE profiles ADD COLUMN birth_date DATE;
ALTER TABLE profiles ADD COLUMN birth_time_approx TEXT;
ALTER TABLE profiles ADD COLUMN birth_city TEXT;

-- Add cultural preferences and personalized scoring weights to preferences
ALTER TABLE preferences ADD COLUMN cultural_preferences TEXT[] DEFAULT '{}';
ALTER TABLE preferences ADD COLUMN dimension_weights JSONB;
