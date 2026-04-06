-- Emotional dynamics: how users make partners feel and what they need to feel
ALTER TABLE profiles ADD COLUMN emotional_giving TEXT;
ALTER TABLE profiles ADD COLUMN emotional_needs TEXT;
ALTER TABLE profiles ADD COLUMN emotional_giving_embedding vector(512);
ALTER TABLE profiles ADD COLUMN emotional_needs_embedding vector(512);

NOTIFY pgrst, 'reload schema';
