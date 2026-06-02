"""Walk through the ideal_type_discovery flow end-to-end against real Claude
and Supabase. Time the conversation — target is <10 minutes.

Usage: python test_ideal_type_live.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from uuid import uuid4

from kandal.core.supabase import get_supabase
from kandal.profiling.ideal_type_engine import IdealTypeEngine


def main():
    profile_id = uuid4()
    client = get_supabase()

    # Stub profile so the FK on ideal_types.profile_id holds.
    try:
        client.table("profiles").insert({
            "id": str(profile_id),
            "is_active": False,
        }).execute()
    except Exception as e:
        print(f"(stub profile insert failed, continuing: {e})")

    engine = IdealTypeEngine()
    state, opening = engine.start(profile_id)

    # Insert the ideal_types row up front so updates can flow into it.
    try:
        row = client.table("ideal_types").insert({
            "profile_id": str(profile_id),
            "messages": state.messages,
            "stage": state.stage,
        }).execute()
        row_id = row.data[0]["id"]
        print(f"(ideal_types row id: {row_id})")
    except Exception as e:
        print(f"(ideal_types row insert failed: {e})")
        row_id = None

    print(f"\nKandal: {opening}\n")
    started_at = time.time()

    while True:
        reply = input("You: ").strip()
        if not reply:
            continue
        turn = engine.next_turn(state, reply)
        print(f"\nKandal: {turn.reply}\n")
        if turn.is_complete:
            break

    elapsed = time.time() - started_at
    print(f"\n--- Conversation took {elapsed/60:.1f} min ({elapsed:.0f}s) ---")

    # Save the artifact + raw inputs to the ideal_types row.
    if row_id:
        try:
            artifact = turn.artifact or {}
            update = {
                "messages": state.messages,
                "stage": state.stage,
                "name": state.name,
                "vignettes": state.vignettes,
                "celebrity_choices": state.celebrity_choices,
                "vignette_choices": artifact.get("vignette_choices") or [],
                "past_pulls": artifact.get("past_pulls") or [],
                "icks": artifact.get("icks") or [],
                "pull_pattern": artifact.get("pull_pattern"),
                "break_pattern": artifact.get("break_pattern"),
                "pull_pattern_quote": artifact.get("pull_pattern_quote"),
                "partner_traits": artifact.get("partner_traits") or [],
            }
            answers = state.dealbreaker_answers
            for col in (
                "gender_preference", "ethnicity_preference", "religion_preference",
                "relationship_intent", "partner_wants_kids", "partner_smokes_max",
                "partner_drinks_max", "partner_cannabis_max",
                "visual_importance",
            ):
                if col in answers:
                    update[col] = answers[col]
            if "age_min" in answers:
                update["age_min"] = answers["age_min"]
            if "age_max" in answers:
                update["age_max"] = answers["age_max"]

            client.table("ideal_types").update(update).eq("id", row_id).execute()
            print("  ideal_types ✓")

            if state.name:
                client.table("profiles").update({"name": state.name}).eq(
                    "id", str(profile_id)
                ).execute()
                print("  profiles.name ✓")

            stored = client.table("ideal_types").select("*").eq("id", row_id).execute()
            print("\n--- STORED ---")
            print(stored.data[0])
        except Exception as e:
            print(f"\nError saving artifact: {e}")


if __name__ == "__main__":
    main()
