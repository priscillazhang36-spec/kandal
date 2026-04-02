"""Batch matching entry point. Run via: python -m kandal.scripts.match"""

from itertools import combinations

from kandal.core.supabase import get_supabase
from kandal.models.preferences import Preferences
from kandal.models.profile import Profile
from kandal.scoring import compute_verdict, passes_dealbreakers, score_compatibility


def run_batch():
    client = get_supabase()

    profiles_resp = client.table("profiles").select("*").eq("is_active", True).execute()
    prefs_resp = client.table("preferences").select("*").execute()

    profiles = {p["id"]: Profile(**p) for p in profiles_resp.data}
    prefs = {p["profile_id"]: Preferences(**p) for p in prefs_resp.data}

    # Only users with both a profile and preferences
    user_ids = [uid for uid in profiles if uid in prefs]

    matches_to_insert = []

    for id_a, id_b in combinations(sorted(str(uid) for uid in user_ids), 2):
        pa, pb = profiles[id_a], profiles[id_b]
        pref_a, pref_b = prefs[id_a], prefs[id_b]

        # Stage 1: Dealbreakers
        if not passes_dealbreakers(pa, pref_a, pb, pref_b):
            continue

        # Stage 2: Score
        result = score_compatibility(pa, pref_a, pb, pref_b)

        # Stage 3: Verdict
        verdict = compute_verdict(result, pref_a.selectivity, pref_b.selectivity)

        if verdict == "match":
            matches_to_insert.append(
                {
                    "profile_a_id": str(id_a),
                    "profile_b_id": str(id_b),
                    "score": result.total_score,
                    "breakdown": {d.dimension: d.score for d in result.breakdown},
                    "verdict": verdict,
                }
            )

    if matches_to_insert:
        client.table("matches").upsert(
            matches_to_insert, on_conflict="profile_a_id,profile_b_id"
        ).execute()

    print(f"Processed {len(user_ids)} users, found {len(matches_to_insert)} matches.")
    return {"users_processed": len(user_ids), "matches_found": len(matches_to_insert)}


if __name__ == "__main__":
    run_batch()
