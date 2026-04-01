"""Quick demo — runs the matching pipeline on fake profiles, no DB needed."""

from itertools import combinations
from uuid import uuid4

from kandal.models.preferences import Preferences
from kandal.models.profile import Profile
from kandal.scoring import compute_verdict, passes_dealbreakers, score_compatibility


def make(name, **kw):
    pid = uuid4()
    profile = Profile(
        id=pid, name=name,
        age=kw.get("age", 28),
        gender=kw.get("gender", "female"),
        location_lat=kw.get("lat", 40.7),
        location_lng=kw.get("lng", -74.0),
        city=kw.get("city", "NYC"),
    )
    prefs = Preferences(
        id=uuid4(), profile_id=pid,
        min_age=kw.get("min_age", 22),
        max_age=kw.get("max_age", 40),
        max_distance_km=kw.get("max_distance_km", 100),
        gender_preferences=kw.get("gender_preferences", ["male", "female", "nonbinary"]),
        relationship_types=kw.get("relationship_types", ["long_term"]),
        interests=kw.get("interests", []),
        personality=kw.get("personality", []),
        values=kw.get("values", []),
        communication_style=kw.get("communication_style", "balanced"),
        lifestyle=kw.get("lifestyle", []),
        selectivity=kw.get("selectivity", "balanced"),
    )
    return profile, prefs


users = [
    make("Alice", age=27, gender="female",
         interests=["hiking", "cooking", "music", "travel"],
         personality=["introvert", "creative"],
         values=["family", "career"],
         communication_style="texter",
         lifestyle=["early_bird", "active"]),

    make("Bob", age=30, gender="male",
         interests=["hiking", "cooking", "gaming"],
         personality=["introvert", "analytical"],
         values=["family", "adventure"],
         communication_style="texter",
         lifestyle=["early_bird", "active", "traveler"]),

    make("Carol", age=25, gender="female",
         interests=["gaming", "anime", "coding"],
         personality=["extrovert", "analytical"],
         values=["career", "adventure"],
         communication_style="caller",
         lifestyle=["night_owl", "homebody"]),

    make("Dan", age=32, gender="male",
         interests=["music", "travel", "photography"],
         personality=["extrovert", "creative"],
         values=["spirituality", "adventure"],
         communication_style="in_person",
         lifestyle=["night_owl", "social", "traveler"]),

    make("Eve", age=26, gender="nonbinary",
         interests=["hiking", "cooking", "coding", "music"],
         personality=["introvert", "creative", "analytical"],
         values=["family", "career"],
         communication_style="balanced",
         lifestyle=["early_bird", "active"],
         selectivity="picky"),
]

print("=" * 60)
print("KANDAL MATCHING DEMO")
print("=" * 60)

print("\nProfiles:")
for p, pr in users:
    print(f"  {p.name} ({p.age}/{p.gender}) — interests: {pr.interests}")

print("\n" + "-" * 60)
print("Running 3-stage pipeline...\n")

for (pa, pref_a), (pb, pref_b) in combinations(users, 2):
    # Stage 1
    if not passes_dealbreakers(pa, pref_a, pb, pref_b):
        print(f"  {pa.name} + {pb.name}: FILTERED (dealbreaker)")
        continue

    # Stage 2
    result = score_compatibility(pa, pref_a, pb, pref_b)

    # Stage 3
    verdict = compute_verdict(result, pref_a.selectivity, pref_b.selectivity)

    icon = "MATCH" if verdict == "match" else "no match"
    print(f"  {pa.name} + {pb.name}: {result.total_score:.2f} -> {icon}")

    if verdict == "match":
        for d in result.breakdown:
            bar = "#" * int(d.score * 20)
            print(f"    {d.dimension:<22} {d.score:.2f}  {bar}")
        print()
