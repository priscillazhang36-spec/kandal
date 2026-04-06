"""Interactive matching demo — answer questions, see your matches."""

from itertools import combinations
from uuid import uuid4

from kandal.models.preferences import Preferences
from kandal.models.profile import Profile
from kandal.questionnaire import QUESTIONS, infer_traits
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
        attachment_style=kw.get("attachment_style"),
        love_language_giving=kw.get("love_language_giving", []),
        love_language_receiving=kw.get("love_language_receiving", []),
        conflict_style=kw.get("conflict_style"),
        relationship_history=kw.get("relationship_history"),
    )
    return profile, prefs


# --- NPC profiles ---

NPCS = [
    make("Maya", age=29, gender="female",
         interests=["yoga", "cooking", "reading", "travel"],
         personality=["introvert", "empathetic"],
         values=["family", "growth"],
         communication_style="balanced",
         lifestyle=["early_bird", "active"],
         attachment_style="secure",
         love_language_giving=["quality_time", "words_of_affirmation", "acts_of_service", "physical_touch", "gifts"],
         love_language_receiving=["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"],
         conflict_style="collaborative",
         relationship_history="long_term"),

    make("Jordan", age=31, gender="male",
         interests=["music", "hiking", "cooking", "film"],
         personality=["extrovert", "creative"],
         values=["family", "adventure"],
         communication_style="texter",
         lifestyle=["social", "active", "traveler"],
         attachment_style="anxious",
         love_language_giving=["words_of_affirmation", "gifts", "quality_time", "physical_touch", "acts_of_service"],
         love_language_receiving=["physical_touch", "words_of_affirmation", "quality_time", "acts_of_service", "gifts"],
         conflict_style="talk_immediately",
         relationship_history="long_term"),

    make("Sage", age=27, gender="nonbinary",
         interests=["coding", "gaming", "climbing", "music"],
         personality=["introvert", "analytical"],
         values=["career", "independence"],
         communication_style="texter",
         lifestyle=["night_owl", "active"],
         attachment_style="avoidant",
         love_language_giving=["acts_of_service", "quality_time", "gifts", "words_of_affirmation", "physical_touch"],
         love_language_receiving=["quality_time", "acts_of_service", "words_of_affirmation", "physical_touch", "gifts"],
         conflict_style="need_space",
         relationship_history="mostly_casual"),

    make("Leo", age=33, gender="male",
         interests=["cooking", "travel", "photography", "hiking"],
         personality=["extrovert", "empathetic", "creative"],
         values=["family", "spirituality"],
         communication_style="in_person",
         lifestyle=["early_bird", "social", "traveler"],
         attachment_style="secure",
         love_language_giving=["physical_touch", "quality_time", "acts_of_service", "words_of_affirmation", "gifts"],
         love_language_receiving=["acts_of_service", "physical_touch", "quality_time", "words_of_affirmation", "gifts"],
         conflict_style="collaborative",
         relationship_history="long_term"),

    make("Priya", age=26, gender="female",
         interests=["art", "travel", "yoga", "reading"],
         personality=["introvert", "creative", "empathetic"],
         values=["growth", "spirituality"],
         communication_style="caller",
         lifestyle=["early_bird", "homebody"],
         attachment_style="anxious",
         love_language_giving=["gifts", "words_of_affirmation", "acts_of_service", "quality_time", "physical_touch"],
         love_language_receiving=["words_of_affirmation", "gifts", "quality_time", "physical_touch", "acts_of_service"],
         conflict_style="collaborative",
         relationship_history="recently_out_of_ltr"),

    make("Alex", age=30, gender="male",
         interests=["gaming", "coding", "film", "music"],
         personality=["introvert", "analytical"],
         values=["career", "independence"],
         communication_style="texter",
         lifestyle=["night_owl", "homebody"],
         attachment_style="disorganized",
         love_language_giving=["quality_time", "physical_touch", "words_of_affirmation", "acts_of_service", "gifts"],
         love_language_receiving=["quality_time", "physical_touch", "words_of_affirmation", "acts_of_service", "gifts"],
         conflict_style="avoidant",
         relationship_history="limited_experience"),
]

LABELS = ["A", "B", "C", "D"]


def run_questionnaire() -> list[int]:
    """Ask 10 scenario questions, return list of answer indices."""
    answers = []
    for i, q in enumerate(QUESTIONS, 1):
        print(f"\n--- Question {i}/{len(QUESTIONS)} ---")
        print(q["text"])
        print()
        for j, opt in enumerate(q["options"]):
            print(f"  {LABELS[j]}) {opt['text']}")
        while True:
            choice = input("\nYour answer (A/B/C/D): ").strip().upper()
            if choice in LABELS[:len(q["options"])]:
                answers.append(LABELS.index(choice))
                break
            print("  Please enter A, B, C, or D.")
    return answers


def print_profile_card(name, profile, prefs):
    """Print a compact profile summary."""
    print(f"  {name} ({profile.age}/{profile.gender})")
    print(f"    Interests: {', '.join(prefs.interests)}")
    print(f"    Personality: {', '.join(prefs.personality)}")
    print(f"    Values: {', '.join(prefs.values)}")
    if prefs.attachment_style:
        print(f"    Attachment: {prefs.attachment_style} | Conflict: {prefs.conflict_style}")
        print(f"    Gives love via: {prefs.love_language_giving[0] if prefs.love_language_giving else '?'}")
        print(f"    Receives love via: {prefs.love_language_receiving[0] if prefs.love_language_receiving else '?'}")
    if prefs.relationship_history:
        print(f"    History: {prefs.relationship_history}")


def main():
    print("=" * 60)
    print("  KANDAL MATCHING DEMO")
    print("  Answer 10 questions. Meet your matches.")
    print("=" * 60)

    # --- Questionnaire ---
    answers = run_questionnaire()
    traits = infer_traits(answers)

    print("\n" + "=" * 60)
    print("  YOUR PROFILE")
    print("=" * 60)
    print(f"  Attachment style:    {traits.attachment_style}")
    print(f"  Conflict style:      {traits.conflict_style}")
    print(f"  Love language (give): {traits.love_language_giving[0]}")
    print(f"  Love language (recv): {traits.love_language_receiving[0]}")
    print(f"  Relationship history: {traits.relationship_history}")

    # Build the user's profile with inferred traits + some defaults
    you = make(
        "You", age=28, gender="nonbinary",
        interests=["hiking", "cooking", "music", "reading"],
        personality=["introvert", "creative"],
        values=["family", "growth"],
        communication_style="balanced",
        lifestyle=["early_bird", "active"],
        selectivity="balanced",
        attachment_style=traits.attachment_style,
        love_language_giving=traits.love_language_giving,
        love_language_receiving=traits.love_language_receiving,
        conflict_style=traits.conflict_style,
        relationship_history=traits.relationship_history,
    )

    # --- Show NPCs ---
    print("\n" + "=" * 60)
    print("  PEOPLE IN THE POOL")
    print("=" * 60)
    for p, pr in NPCS:
        print()
        print_profile_card(p.name, p, pr)

    # --- Run matching ---
    all_users = [you] + NPCS
    print("\n" + "=" * 60)
    print("  MATCHING RESULTS")
    print("=" * 60)

    your_matches = []
    for (pa, pref_a), (pb, pref_b) in combinations(all_users, 2):
        if not passes_dealbreakers(pa, pref_a, pb, pref_b):
            continue
        result_a = score_compatibility(pa, pref_a, pb, pref_b, perspective_weights=pref_a.dimension_weights)
        result_b = score_compatibility(pa, pref_a, pb, pref_b, perspective_weights=pref_b.dimension_weights)
        result = result_a  # use A's perspective for display
        verdict = compute_verdict(result_a, result_b, pref_a.selectivity, pref_b.selectivity)

        involves_you = pa.name == "You" or pb.name == "You"
        if involves_you:
            other = pb.name if pa.name == "You" else pa.name
            your_matches.append((other, result, verdict))

    # Sort your matches by score descending
    your_matches.sort(key=lambda x: x[1].total_score, reverse=True)

    if not your_matches:
        print("\n  No compatible matches found. Try different answers!")
    else:
        for other_name, result, verdict in your_matches:
            icon = "MATCH" if verdict == "match" else "no match"
            print(f"\n  You + {other_name}: {result.total_score:.2f} -> {icon}")
            for d in result.breakdown:
                bar = "#" * int(d.score * 20)
                print(f"    {d.dimension:<22} {d.score:.2f}  {bar}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
