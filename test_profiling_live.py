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

    # Insert a stub profile row up front so memory writes during the conversation
    # (seed_from_onboarding on finalize) don't hit FK violations.
    try:
        get_supabase().table("profiles").insert({
            "id": str(profile_id),
            "name": "Test User",
            "age": 25,
            "gender": "female",
            "is_active": False,
        }).execute()
    except Exception as e:
        print(f"(stub profile insert failed, continuing: {e})")

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
        if turn.traits and turn.traits.emotional_giving:
            profile_data["emotional_giving"] = turn.traits.emotional_giving
        if turn.traits and turn.traits.emotional_needs:
            profile_data["emotional_needs"] = turn.traits.emotional_needs

        profile_data["is_active"] = True
        client.table("profiles").update(profile_data).eq("id", str(profile_id)).execute()
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

        # Generate and store embeddings
        if turn.narrative:
            try:
                from kandal.profiling.embeddings import embed_narrative
                embedding = embed_narrative(turn.narrative)
                client.table("profiles").update({
                    "narrative_embedding": embedding,
                    "embedding_version": 1,
                }).eq("id", str(profile_id)).execute()
                print(f"  narrative_embedding ✓ ({len(embedding)} dims)")
            except Exception as e:
                print(f"  narrative_embedding skipped: {e}")

        if turn.traits and (turn.traits.emotional_giving or turn.traits.emotional_needs):
            try:
                from kandal.profiling.embeddings import embed_emotional_dynamics
                giving_emb, needs_emb = embed_emotional_dynamics(
                    turn.traits.emotional_giving, turn.traits.emotional_needs
                )
                emb_update = {}
                if giving_emb:
                    emb_update["emotional_giving_embedding"] = giving_emb
                if needs_emb:
                    emb_update["emotional_needs_embedding"] = needs_emb
                if emb_update:
                    client.table("profiles").update(emb_update).eq(
                        "id", str(profile_id)
                    ).execute()
                    print(f"  emotional_embeddings ✓")
            except Exception as e:
                print(f"  emotional_embeddings skipped: {e}")

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
