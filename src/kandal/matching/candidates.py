"""SQL-based candidate generation with dealbreaker filtering and ANN ranking.

Replaces the O(n^2) pair enumeration with a per-user query that pushes
dealbreaker checks into PostgreSQL and uses pgvector for ranking.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from kandal.core.supabase import get_supabase

# SQL for candidate generation with all dealbreakers checked in the DB.
# Uses earthdistance for spatial filtering and pgvector for ANN ranking.
# Falls back to random ordering when embeddings are missing.
_CANDIDATES_SQL = """\
SELECT
    c.id AS candidate_id,
    CASE
        WHEN p.narrative_embedding IS NOT NULL AND c.narrative_embedding IS NOT NULL
        THEN 1 - (p.narrative_embedding <=> c.narrative_embedding)
        ELSE NULL
    END AS embedding_sim,
    CASE
        WHEN p.location_lat IS NOT NULL AND p.location_lng IS NOT NULL
             AND c.location_lat IS NOT NULL AND c.location_lng IS NOT NULL
        THEN earth_distance(
            ll_to_earth(p.location_lat, p.location_lng),
            ll_to_earth(c.location_lat, c.location_lng)
        ) / 1000.0
        ELSE NULL
    END AS distance_km
FROM profiles p
JOIN preferences up ON up.profile_id = p.id
JOIN profiles c ON c.id != p.id AND c.is_active = TRUE
JOIN preferences cp ON cp.profile_id = c.id
WHERE p.id = :user_id
  -- Forward dealbreakers (user accepts candidate)
  AND (up.gender_preferences = '{}' OR c.gender = ANY(up.gender_preferences))
  AND c.age BETWEEN up.min_age AND up.max_age
  -- Reverse dealbreakers (candidate accepts user)
  AND (cp.gender_preferences = '{}' OR p.gender = ANY(cp.gender_preferences))
  AND p.age BETWEEN cp.min_age AND cp.max_age
  -- Relationship type overlap (array intersection)
  AND up.relationship_types && cp.relationship_types
  -- Distance filter (skip if either lacks coordinates)
  AND (
      p.location_lat IS NULL OR p.location_lng IS NULL
      OR c.location_lat IS NULL OR c.location_lng IS NULL
      OR earth_distance(
          ll_to_earth(p.location_lat, p.location_lng),
          ll_to_earth(c.location_lat, c.location_lng)
      ) <= LEAST(up.max_distance_km, cp.max_distance_km) * 1000
  )
ORDER BY
    CASE
        WHEN p.narrative_embedding IS NOT NULL AND c.narrative_embedding IS NOT NULL
        THEN p.narrative_embedding <=> c.narrative_embedding
        ELSE random()
    END
LIMIT :candidate_limit;
"""


class CandidatePair(BaseModel):
    candidate_id: UUID
    embedding_sim: float | None = None
    distance_km: float | None = None


class CandidateGenerator:
    """Generate candidate matches using DB-level filtering + ANN ranking."""

    def get_candidates(
        self, profile_id: UUID, limit: int = 200
    ) -> list[CandidatePair]:
        """Return top candidates for a user, with all dealbreakers checked in SQL."""
        client = get_supabase()

        resp = client.rpc(
            "get_candidates",
            {"p_user_id": str(profile_id), "p_limit": limit},
        ).execute()

        return [CandidatePair(**row) for row in resp.data]
