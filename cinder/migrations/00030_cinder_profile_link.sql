-- Bridge cinder_profiles to the main profiles / ideal_types tables.
-- A cinder woman who also completed ideal_type_discovery has an ideal_types row
-- keyed by profiles.id. This nullable column stores that profiles.id so the
-- matcher can pull her deep profile (pull_pattern / break_pattern / partner_traits
-- / icks). Most cinder rows leave it NULL.

ALTER TABLE cinder_profiles ADD COLUMN profile_id UUID;

NOTIFY pgrst, 'reload schema';
