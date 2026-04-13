"""Rescue abandoned profiling conversations by extracting traits from partial data."""

import logging
from datetime import datetime, timedelta, timezone

import sentry_sdk

from kandal.core.supabase import get_supabase
from kandal.profiling.extractor import extract_traits
from kandal.profiling.embeddings import embed_narrative, store_narrative_and_embedding

logger = logging.getLogger(__name__)

STALE_MINUTES = 30


def rescue_stale_conversations() -> dict:
    """Find in_progress conversations idle for 30+ min, extract traits, save."""
    client = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)).isoformat()

    stale = (
        client.table("profiling_conversations")
        .select("*")
        .eq("status", "in_progress")
        .lt("updated_at", cutoff)
        .execute()
    )

    rescued = 0
    skipped = 0

    for conv in stale.data:
        messages = conv.get("messages", [])
        user_messages = [m for m in messages if m["role"] == "user"]

        if not user_messages:
            client.table("profiling_conversations").update({
                "status": "abandoned",
            }).eq("id", conv["id"]).execute()
            skipped += 1
            continue

        try:
            traits, narrative, _ = extract_traits(messages)

            client.table("profiling_conversations").update({
                "status": "rescued",
                "extracted_traits": traits.model_dump(),
                "narrative": narrative,
            }).eq("id", conv["id"]).execute()

            profile_id = conv["profile_id"]

            client.table("profiles").update({
                "narrative": narrative,
            }).eq("id", profile_id).execute()

            prefs_data = {
                "profile_id": profile_id,
                "attachment_style": traits.attachment_style,
                "love_language_giving": traits.love_language_giving,
                "love_language_receiving": traits.love_language_receiving,
                "conflict_style": traits.conflict_style,
                "relationship_history": traits.relationship_history,
            }
            if traits.interests:
                prefs_data["interests"] = traits.interests
            if traits.personality:
                prefs_data["personality"] = traits.personality
            if traits.partner_personality:
                prefs_data["partner_personality"] = traits.partner_personality
            if traits.values:
                prefs_data["values"] = traits.values
            if traits.partner_values:
                prefs_data["partner_values"] = traits.partner_values
            if traits.lifestyle:
                prefs_data["lifestyle"] = traits.lifestyle
            for field in (
                "age_min", "age_max", "max_distance_km", "relationship_intent",
                "has_kids", "wants_kids", "relationship_structure",
                "religion", "religion_importance", "drinks", "smokes", "cannabis",
            ):
                val = getattr(traits, field, None)
                if val is not None:
                    prefs_data[field] = val
            client.table("preferences").upsert(
                prefs_data, on_conflict="profile_id"
            ).execute()

            try:
                embedding = embed_narrative(narrative)
                store_narrative_and_embedding(profile_id, narrative, embedding)
            except Exception as e:
                logger.warning("Embedding failed for %s: %s", profile_id, e)

            rescued += 1
            logger.info("Rescued conversation %s for profile %s", conv["id"], profile_id)

        except Exception as e:
            logger.error("Failed to rescue conversation %s: %s", conv["id"], e)
            sentry_sdk.set_context("rescue", {"conversation_id": conv["id"]})
            sentry_sdk.capture_exception(e)
            client.table("profiling_conversations").update({
                "status": "rescue_failed",
            }).eq("id", conv["id"]).execute()

    return {"rescued": rescued, "skipped": skipped}
