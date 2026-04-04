"""Bootstrap a test session in adaptive_profiling state and send the opening message.

The deployed Vercel webhook handles all subsequent replies.
After the conversation completes, check Supabase for results.
"""

from kandal.core.supabase import get_supabase
from kandal.profiling.engine import ProfilingEngine, OPENING_MESSAGE
from kandal.sms.service import send_sms
from uuid import UUID

PHONE = "+17807102780"


def main():
    client = get_supabase()

    # Clean up any existing session/profile for this phone
    client.table("onboarding_sessions").delete().eq("phone", PHONE).execute()
    old_profiles = client.table("profiles").select("id").eq("phone", PHONE).execute()
    for p in old_profiles.data:
        client.table("profiling_conversations").delete().eq("profile_id", p["id"]).execute()
        client.table("preferences").delete().eq("profile_id", p["id"]).execute()
    client.table("profiles").delete().eq("phone", PHONE).execute()

    # Create profile
    profile_resp = client.table("profiles").insert({
        "phone": PHONE,
        "is_active": False,
    }).execute()
    profile_id = profile_resp.data[0]["id"]
    print(f"Created profile: {profile_id}")

    # Start profiling engine
    engine = ProfilingEngine()
    state, opening = engine.start(UUID(profile_id))

    # Save conversation to DB
    conv_resp = client.table("profiling_conversations").insert({
        "profile_id": profile_id,
        "messages": state.messages,
        "coverage": state.coverage,
        "status": "in_progress",
    }).execute()
    conv_id = conv_resp.data[0]["id"]
    print(f"Created conversation: {conv_id}")

    # Create onboarding session in adaptive_profiling state
    session_resp = client.table("onboarding_sessions").insert({
        "phone": PHONE,
        "state": "adaptive_profiling",
        "profile_id": profile_id,
        "conversation_id": conv_id,
        "answers": [],
        "collected_basics": {},
    }).execute()
    print(f"Created session: {session_resp.data[0]['id']}")

    # Send the opening message
    send_sms(PHONE, opening)
    print(f"\nSent opening message to {PHONE}")
    print("Reply via SMS — the Vercel webhook handles the rest.")
    print(f"\nAfter you're done, check Supabase:")
    print(f"  - profiling_conversations (id = {conv_id})")
    print(f"  - profiles (id = {profile_id})")
    print(f"  - preferences (profile_id = {profile_id})")


if __name__ == "__main__":
    main()
