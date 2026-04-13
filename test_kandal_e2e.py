"""End-to-end smoke test for Kandal memory + chat + 3-stage matching.

Subcommands:
  seed       Insert two complete fake profiles (with seeded memories) for testing.
  memories   Print all kandal_memories for a phone.
  chat       Interactive REPL with a profile's Kandal (uses chat_turn).
  match      Run the 3-stage match script and print summary.
  cleanup    Delete the seeded fake profiles and their data.

Usage:
  python test_kandal_e2e.py seed
  python test_kandal_e2e.py chat +15550000001
  python test_kandal_e2e.py memories +15550000001
  python test_kandal_e2e.py match
  python test_kandal_e2e.py cleanup
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import json
from uuid import UUID, uuid4

from kandal.core.supabase import get_supabase

# Two seeded test users — distinct preferences so matching has signal to chew on.
SEED_USERS = [
    {
        "phone": "+15550000001",
        "profile": {
            "name": "Maya",
            "age": 29,
            "gender": "female",
            "city": "San Francisco",
            "location_lat": 37.7749,
            "location_lng": -122.4194,
            "is_active": True,
            "narrative": (
                "Maya, 29, SF. Designer at a small startup. Hikes most weekends, cooks "
                "elaborate dinners on Sundays. Anxious-leaning attachment, knows it, "
                "working on it. Wants someone steady who can match her emotional intensity "
                "without getting overwhelmed. Out of a 4-year LTR a year ago. Values "
                "growth, honesty, humor. Doesn't want kids."
            ),
            "emotional_giving": "Maya makes you feel completely seen. She remembers the small things and shows up hard when it matters.",
            "emotional_needs": "She needs a partner who's emotionally present and won't shut down when things get heavy. Reassurance during conflict.",
        },
        "preferences": {
            "min_age": 28, "max_age": 38, "max_distance_km": 50,
            "gender_preferences": ["male"],
            "attachment_style": "anxious",
            "conflict_style": "talk_immediately",
            "relationship_history": "recently_out_of_ltr",
            "love_language_giving": ["acts_of_service", "quality_time", "words_of_affirmation", "physical_touch", "gifts"],
            "love_language_receiving": ["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"],
            "interests": ["hiking", "cooking", "design", "reading"],
            "values": ["growth", "honesty", "humor"],
            "personality": ["empathetic", "creative", "intense"],
            "partner_personality": ["grounded", "emotionally_available", "curious"],
            "lifestyle": ["active", "homebody"],
        },
    },
    {
        "phone": "+15550000002",
        "profile": {
            "name": "Ben",
            "age": 32,
            "gender": "male",
            "city": "San Francisco",
            "location_lat": 37.7749,
            "location_lng": -122.4194,
            "is_active": True,
            "narrative": (
                "Ben, 32, SF. Backend engineer. Ex-college runner, still trains most "
                "mornings. Reads philosophy, cooks badly but enthusiastically. Secure "
                "attachment. Long history of healthy relationships, last one ended "
                "amicably 18 months ago. Wants a partner he can build a life with — "
                "thoughtful, ambitious, doesn't take herself too seriously."
            ),
            "emotional_giving": "Ben is calm and steady. He shows love through consistency and just being there — not flashy, but you feel it.",
            "emotional_needs": "He needs a partner who'll communicate openly when something's wrong. Doesn't do guessing games.",
        },
        "preferences": {
            "min_age": 26, "max_age": 34, "max_distance_km": 50,
            "gender_preferences": ["female"],
            "attachment_style": "secure",
            "conflict_style": "talk_immediately",
            "relationship_history": "long_term",
            "love_language_giving": ["quality_time", "acts_of_service", "physical_touch", "words_of_affirmation", "gifts"],
            "love_language_receiving": ["quality_time", "physical_touch", "words_of_affirmation", "acts_of_service", "gifts"],
            "interests": ["running", "reading", "cooking", "philosophy"],
            "values": ["honesty", "ambition", "growth"],
            "personality": ["grounded", "curious", "ambitious"],
            "partner_personality": ["intense", "creative", "honest"],
            "lifestyle": ["active", "early_bird"],
        },
    },
]


def cmd_seed():
    from kandal.profiling.memory import seed_from_onboarding
    client = get_supabase()
    for u in SEED_USERS:
        # Skip if already exists
        existing = client.table("profiles").select("id").eq("phone", u["phone"]).execute()
        if existing.data:
            print(f"  {u['phone']}: already exists (id={existing.data[0]['id']}) — skipping insert")
            profile_id = existing.data[0]["id"]
        else:
            profile_data = {"phone": u["phone"], **u["profile"]}
            resp = client.table("profiles").insert(profile_data).execute()
            profile_id = resp.data[0]["id"]
            prefs = {"profile_id": profile_id, **u["preferences"]}
            client.table("preferences").insert(prefs).execute()
            print(f"  {u['phone']}: created profile {profile_id}")

        # Seed memories from the trait dict
        traits = {**u["profile"], **u["preferences"]}
        n = seed_from_onboarding(UUID(profile_id), traits, u["profile"]["narrative"])
        print(f"    seeded {n} memories")


def cmd_memories(phone: str):
    client = get_supabase()
    p = client.table("profiles").select("id, name").eq("phone", phone).execute()
    if not p.data:
        print(f"no profile with phone {phone}")
        return
    profile_id = p.data[0]["id"]
    print(f"\n{p.data[0]['name']} ({profile_id})\n")
    rows = (
        client.table("kandal_memories")
        .select("kind, content, salience, created_at, recall_count")
        .eq("profile_id", profile_id)
        .order("salience", desc=True)
        .execute()
    )
    for r in rows.data or []:
        print(f"  [{r['kind']:10s} sal={r['salience']:.2f} recalls={r['recall_count']}] {r['content']}")
    print(f"\n  total: {len(rows.data or [])}")


def cmd_chat(phone: str):
    from kandal.profiling.chat import chat_turn
    client = get_supabase()
    p = client.table("profiles").select("id, name").eq("phone", phone).execute()
    if not p.data:
        print(f"no profile with phone {phone}")
        return
    profile_id = UUID(p.data[0]["id"])
    print(f"\nChatting as {p.data[0]['name']}. Ctrl-C to exit.\n")
    while True:
        try:
            msg = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not msg:
            continue
        result = chat_turn(profile_id, msg)
        print(f"\nKandal: {result.reply}")
        if result.memories_written:
            print(f"  (+{result.memories_written} new memories)")
        print()


def cmd_match():
    from kandal.scripts.match import run_batch
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = run_batch()
    print("\n--- summary ---")
    print(json.dumps(summary, indent=2))

    # Print any new matches with LLM verdicts
    client = get_supabase()
    rows = (
        client.table("matches")
        .select("profile_a_id, profile_b_id, llm_score, llm_summary, llm_reasons, llm_concerns, coarse_score")
        .not_.is_("llm_score", "null")
        .order("llm_score", desc=True)
        .limit(10)
        .execute()
    )
    print(f"\n--- top {len(rows.data or [])} LLM-judged matches ---")
    for r in rows.data or []:
        print(f"\n  {r['profile_a_id'][:8]} ↔ {r['profile_b_id'][:8]}")
        print(f"    LLM: {r['llm_score']:.2f}  coarse: {r['coarse_score']:.2f}")
        print(f"    {r['llm_summary']}")
        for reason in r.get("llm_reasons") or []:
            print(f"    + {reason}")
        for concern in r.get("llm_concerns") or []:
            print(f"    - {concern}")


def cmd_cleanup():
    client = get_supabase()
    for u in SEED_USERS:
        p = client.table("profiles").select("id").eq("phone", u["phone"]).execute()
        if not p.data:
            continue
        pid = p.data[0]["id"]
        # Cascading FKs handle preferences/memories/chats/conversations
        client.table("matches").delete().or_(
            f"profile_a_id.eq.{pid},profile_b_id.eq.{pid}"
        ).execute()
        client.table("profiles").delete().eq("id", pid).execute()
        print(f"  deleted {u['phone']} ({pid})")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    handlers = {
        "seed": cmd_seed,
        "memories": cmd_memories,
        "chat": cmd_chat,
        "match": cmd_match,
        "cleanup": cmd_cleanup,
    }
    if cmd not in handlers:
        print(f"unknown command: {cmd}\n")
        print(__doc__)
        sys.exit(1)
    handlers[cmd](*args)


if __name__ == "__main__":
    main()
