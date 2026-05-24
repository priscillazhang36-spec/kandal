"""Interactive terminal driver for the onboarding conversation.

Usage:
    python -m kandal.scripts.onboard_test           # writes to test_profiles
    python -m kandal.scripts.onboard_test --no-save # in-memory only

Runs the full ProfilingEngine flow in your terminal — freeform → confirm →
spark MCQs → long-term MCQs → basics MCQs → finalize. By default upserts
the resulting row to `test_profiles` + `test_preferences` so you can
inspect it and run the judge against it.

Requires: ANTHROPIC_API_KEY in env. Supabase env vars required for --save.

At the end, prints the extracted traits + spark_voice JSONB so you can see
exactly what the v4 moment-elicitation flow captured.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from uuid import UUID, uuid4

from kandal.profiling.engine import ProfilingEngine


def _print_kandal(text: str) -> None:
    print(f"\n\033[36mKandal:\033[0m {text}\n")


def _read_user() -> str:
    try:
        return input("\033[33mYou:\033[0m ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[interrupted]")
        sys.exit(0)


def _compute_age(birth_date: str | None) -> int | None:
    if not birth_date:
        return None
    try:
        bd = date.fromisoformat(birth_date)
        today = date.today()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except Exception:
        return None


def _persist_to_test_tables(profile_id: UUID, traits, narrative: str | None) -> None:
    """Upsert the freshly-onboarded profile + prefs to the test schema."""
    try:
        from kandal.core.supabase import get_supabase
        client = get_supabase()
    except Exception as e:
        print(f"\n[!] supabase client unavailable, skipping persist: {e}")
        return

    age = _compute_age(traits.birth_date)
    profile_row = {
        "id": str(profile_id),
        "name": traits.name or "TestUser",
        "age": age or 30,
        "gender": traits.gender or "nonbinary",
        "city": traits.current_city,
        "narrative": narrative,
        "birth_date": traits.birth_date,
        "birth_time_approx": traits.birth_time_approx,
        "birth_city": traits.birth_city,
        "emotional_giving": traits.emotional_giving,
        "emotional_needs": traits.emotional_needs,
        "taste_fingerprint": traits.taste_fingerprint,
        "current_obsession": traits.current_obsession,
        "two_hour_topic": traits.two_hour_topic,
        "contradiction_hook": traits.contradiction_hook,
        "past_attraction": traits.past_attraction,
        "favorite_places": traits.favorite_places,
        "spark_voice": traits.spark_voice or {},
    }
    profile_row = {k: v for k, v in profile_row.items() if v is not None}

    try:
        client.table("test_profiles").upsert(profile_row, on_conflict="id").execute()
        print(f"\n[OK] wrote test_profiles row id={profile_id}")
    except Exception as e:
        msg = str(e)
        if "spark_voice" in msg:
            print(f"\n[!] test_profiles write failed — looks like migration "
                  f"00018 hasn't been applied (spark_voice column missing).\n"
                  f"    Run: supabase db push\n"
                  f"    Error: {e}")
        else:
            print(f"\n[!] test_profiles write failed: {e}")
        return

    prefs_row = {
        "profile_id": str(profile_id),
        "min_age": traits.age_min or 25,
        "max_age": traits.age_max or 45,
        "max_distance_km": traits.max_distance_km or 50,
        "gender_preferences": traits.gender_preference or [],
        "attachment_style": traits.attachment_style,
        "love_language_giving": traits.love_language_giving or [],
        "love_language_receiving": traits.love_language_receiving or [],
        "conflict_style": traits.conflict_style,
        "relationship_history": traits.relationship_history,
        "energy_pace": traits.energy_pace,
        "ambition_shape": traits.ambition_shape,
        "visual_type": traits.visual_type,
        "visual_preference": traits.visual_preference,
        # v4.2 lifestyle basics + paired tolerance (now wired into dealbreakers)
        "relationship_intent": traits.relationship_intent,
        "has_kids": traits.has_kids,
        "wants_kids": traits.wants_kids,
        "relationship_structure": traits.relationship_structure,
        "religion": traits.religion,
        "religion_importance": traits.religion_importance,
        "drinks": traits.drinks,
        "smokes": traits.smokes,
        "cannabis": traits.cannabis,
        "partner_wants_kids": traits.partner_wants_kids,
        "partner_substances_max": traits.partner_substances_max,
        "interests": traits.interests or [],
        "personality": traits.personality or [],
        "partner_personality": traits.partner_personality or [],
        "values": traits.values or [],
        "partner_values": traits.partner_values or [],
        "lifestyle": traits.lifestyle or [],
        "cultural_preferences": traits.cultural_preferences or [],
    }
    prefs_row = {k: v for k, v in prefs_row.items() if v is not None}

    try:
        client.table("test_preferences").upsert(prefs_row, on_conflict="profile_id").execute()
        print(f"[OK] wrote test_preferences row profile_id={profile_id}")
    except Exception as e:
        print(f"[!] test_preferences write failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-save", action="store_true",
                        help="don't persist to test_profiles/test_preferences")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    profile_id = uuid4()
    print(f"[onboarding session — profile_id={profile_id}]")

    engine = ProfilingEngine()
    state, opening = engine.start(profile_id)
    _print_kandal(opening)

    while True:
        reply = _read_user()
        if not reply:
            continue
        if reply.lower() in {"/quit", "/exit"}:
            print("[exiting early]")
            break

        turn = engine.next_turn(state, reply)
        _print_kandal(turn.reply)

        if turn.is_complete:
            print("\n=== ONBOARDING COMPLETE ===\n")
            traits_obj = turn.traits
            traits = traits_obj.model_dump() if traits_obj else {}
            spark_voice = traits.get("spark_voice") or {}

            print("--- spark_voice (verbatim slices the judge will see) ---")
            print(json.dumps(spark_voice, indent=2))

            print("\n--- key extracted fields ---")
            for k in (
                "taste_fingerprint", "current_obsession", "two_hour_topic",
                "contradiction_hook", "past_attraction", "favorite_places",
                "emotional_giving", "emotional_needs",
                "visual_preference",  # v4.1: appearance freeform
                "energy_pace", "ambition_shape", "visual_type",
                "humor_style", "conversational_texture",  # should be None in v4
            ):
                v = traits.get(k)
                if v is not None:
                    print(f"  {k}: {v}")

            print("\n--- narrative ---")
            print(turn.narrative or "(none)")

            if not args.no_save and traits_obj is not None:
                _persist_to_test_tables(profile_id, traits_obj, turn.narrative)
            break


if __name__ == "__main__":
    main()
