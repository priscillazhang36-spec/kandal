-- Add high/medium-impact basic info: age range, distance, intent, kids,
-- relationship structure, religion, substances. All optional (nullable).
ALTER TABLE preferences ADD COLUMN age_min INT;
ALTER TABLE preferences ADD COLUMN age_max INT;
ALTER TABLE preferences ADD COLUMN max_distance_km INT;
ALTER TABLE preferences ADD COLUMN relationship_intent TEXT;
ALTER TABLE preferences ADD COLUMN has_kids TEXT;
ALTER TABLE preferences ADD COLUMN wants_kids TEXT;
ALTER TABLE preferences ADD COLUMN relationship_structure TEXT;
ALTER TABLE preferences ADD COLUMN religion TEXT;
ALTER TABLE preferences ADD COLUMN religion_importance TEXT;
ALTER TABLE preferences ADD COLUMN drinks TEXT;
ALTER TABLE preferences ADD COLUMN smokes TEXT;
ALTER TABLE preferences ADD COLUMN cannabis TEXT;

NOTIFY pgrst, 'reload schema';
