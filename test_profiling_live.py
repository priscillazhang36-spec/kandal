"""Chat with the adaptive profiler, then store to Supabase and verify."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from uuid import uuid4

from kandal.core.supabase import get_supabase
from kandal.profiling.engine import ProfilingEngine


def main():
    profile_id = uuid4()
    engine = ProfilingEngine()
    state, opening = engine.start(profile_id)

    print(f"\nKandal: {opening}\n")

    while True:
        reply = input("You: ").strip()
        if not reply:
            continue
        turn = engine.next_turn(state, reply)
        print(f"\nKandal: {turn.reply}\n")

        if turn.is_complete:
            break
        # awaiting_confirmation — keep looping so user can confirm or correct

    # Store to Supabase
    try:
        client = get_supabase()
        print("\nSaving to Supabase...")

        profile_data = {
            "id": str(profile_id),
            "name": "Test User",
            "age": 25,
            "gender": "female",
            "is_active": True,
            "narrative": turn.narrative,
        }
        if turn.traits and turn.traits.birth_date:
            profile_data["birth_date"] = turn.traits.birth_date
        if turn.traits and turn.traits.birth_time_approx:
            profile_data["birth_time_approx"] = turn.traits.birth_time_approx
        if turn.traits and turn.traits.birth_city:
            profile_data["birth_city"] = turn.traits.birth_city

        client.table("profiles").insert(profile_data).execute()
        print("  profiles ✓")

        prefs_data = {
            "profile_id": str(profile_id),
            "attachment_style": turn.traits.attachment_style,
            "love_language_giving": turn.traits.love_language_giving,
            "love_language_receiving": turn.traits.love_language_receiving,
            "conflict_style": turn.traits.conflict_style,
            "relationship_history": turn.traits.relationship_history,
        }
        if turn.traits.gender_preference:
            prefs_data["gender_preferences"] = turn.traits.gender_preference
        if turn.traits.cultural_preferences:
            prefs_data["cultural_preferences"] = turn.traits.cultural_preferences
        if turn.traits.dimension_weights:
            prefs_data["dimension_weights"] = turn.traits.dimension_weights

        client.table("preferences").insert(prefs_data).execute()
        print("  preferences ✓")

        # Generate and store narrative embedding
        if turn.narrative:
            from kandal.profiling.embeddings import embed_narrative
            embedding = embed_narrative(turn.narrative)
            client.table("profiles").update({
                "narrative_embedding": embedding,
                "embedding_version": 1,
            }).eq("id", str(profile_id)).execute()
            print(f"  narrative_embedding ✓ ({len(embedding)} dims)")

        client.table("profiling_conversations").insert({
            "profile_id": str(profile_id),
            "messages": state.messages,
            "extracted_traits": turn.traits.model_dump() if turn.traits else None,
            "narrative": turn.narrative,
            "coverage": state.coverage,
            "status": "complete",
        }).execute()
        print("  profiling_conversations ✓")

        # Read back and verify
        print("\n--- STORED IN SUPABASE ---")
        profile = client.table("profiles").select("*").eq("id", str(profile_id)).execute()
        prefs = client.table("preferences").select("*").eq("profile_id", str(profile_id)).execute()
        conv = client.table("profiling_conversations").select("*").eq("profile_id", str(profile_id)).execute()
        print(f"\nProfile:     {profile.data[0]}")
        print(f"\nPreferences: {prefs.data[0]}")
        print(f"\nConversation: {conv.data[0]}")
    except Exception as e:
        print(f"\nError saving to Supabase: {e}")


if __name__ == "__main__":
    main()
