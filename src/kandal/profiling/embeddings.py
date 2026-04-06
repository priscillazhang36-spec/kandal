"""Narrative embedding via Voyage AI."""

from __future__ import annotations

import logging
from uuid import UUID

import voyageai

from kandal.core.config import get_settings
from kandal.core.supabase import get_supabase

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "voyage-3-lite"
EMBEDDING_DIM = 512


def _get_client() -> voyageai.Client:
    settings = get_settings()
    return voyageai.Client(api_key=settings.voyageai_api_key)


def embed_narrative(narrative: str) -> list[float]:
    """Generate embedding for a matchmaker narrative. Returns 1024-dim vector."""
    client = _get_client()
    result = client.embed([narrative], model=EMBEDDING_MODEL)
    return result.embeddings[0]


def embed_emotional_dynamics(
    giving: str | None, needs: str | None
) -> tuple[list[float] | None, list[float] | None]:
    """Generate embeddings for emotional giving and needs descriptions.

    Returns (giving_embedding, needs_embedding). Either may be None if input is None.
    """
    texts_to_embed = []
    giving_idx = needs_idx = None

    if giving:
        giving_idx = len(texts_to_embed)
        texts_to_embed.append(giving)
    if needs:
        needs_idx = len(texts_to_embed)
        texts_to_embed.append(needs)

    if not texts_to_embed:
        return None, None

    client = _get_client()
    result = client.embed(texts_to_embed, model=EMBEDDING_MODEL)

    giving_emb = result.embeddings[giving_idx] if giving_idx is not None else None
    needs_emb = result.embeddings[needs_idx] if needs_idx is not None else None
    return giving_emb, needs_emb


def store_narrative_and_embedding(
    profile_id: UUID, narrative: str, embedding: list[float]
) -> None:
    """Write narrative + embedding to profiles table and update versioning."""
    client = get_supabase()

    # Get current profile_version so embedding_version matches
    resp = (
        client.table("profiles")
        .select("profile_version")
        .eq("id", str(profile_id))
        .execute()
    )
    version = resp.data[0]["profile_version"] if resp.data else 1

    client.table("profiles").update(
        {
            "narrative": narrative,
            "narrative_embedding": embedding,
            "embedding_version": version,
        }
    ).eq("id", str(profile_id)).execute()
