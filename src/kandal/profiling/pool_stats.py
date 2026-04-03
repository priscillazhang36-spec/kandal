"""Compute aggregate pool statistics for pool-aware profiling."""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from pydantic import BaseModel

from kandal.core.supabase import get_supabase
from kandal.profiling.prompts import TRAIT_DIMENSIONS


class PoolStats(BaseModel):
    total_eligible: int = 0
    dominant_attachment_styles: list[str] = []
    differentiating_dimensions: list[str] = []


def get_pool_stats(
    profile_id: UUID,
    gender: str,
    age: int,
    gender_preferences: list[str],
    min_age: int = 18,
    max_age: int = 99,
) -> PoolStats:
    """Query aggregate stats about users matching this person's dealbreaker criteria.

    Intentionally lightweight — runs a few simple queries, no heavy joins.
    Used to inform the profiler's question selection, not for scoring.
    """
    client = get_supabase()

    # Count eligible profiles (mutual gender + age overlap)
    query = (
        client.table("profiles")
        .select("id", count="exact")
        .eq("is_active", True)
        .neq("id", str(profile_id))
        .gte("age", min_age)
        .lte("age", max_age)
    )
    if gender_preferences:
        query = query.in_("gender", gender_preferences)
    count_resp = query.execute()
    total_eligible = count_resp.count or 0

    if total_eligible == 0:
        return PoolStats()

    # Get trait distributions from preferences of eligible users
    eligible_ids = [r["id"] for r in count_resp.data] if count_resp.data else []
    if not eligible_ids:
        return PoolStats(total_eligible=total_eligible)

    # Sample up to 500 for trait distribution (avoid loading entire pool)
    sample_ids = eligible_ids[:500]
    prefs_resp = (
        client.table("preferences")
        .select("attachment_style, conflict_style")
        .in_("profile_id", sample_ids)
        .execute()
    )

    attachment_counts: Counter[str] = Counter()
    conflict_counts: Counter[str] = Counter()
    for row in prefs_resp.data:
        if row.get("attachment_style"):
            attachment_counts[row["attachment_style"]] += 1
        if row.get("conflict_style"):
            conflict_counts[row["conflict_style"]] += 1

    dominant_attachment = [s for s, _ in attachment_counts.most_common(3)]

    # Find underrepresented dimensions (those with least data or most uniform)
    dimension_variance = {}
    for dim_name, counts in [
        ("attachment_style", attachment_counts),
        ("conflict_style", conflict_counts),
    ]:
        if counts:
            total = sum(counts.values())
            max_share = max(counts.values()) / total
            dimension_variance[dim_name] = 1.0 - max_share  # lower = more uniform = less differentiating
        else:
            dimension_variance[dim_name] = 0.0

    # Dimensions with low variance are less useful for differentiation;
    # high-variance ones are where this person's answer matters most
    differentiators = sorted(dimension_variance, key=dimension_variance.get, reverse=True)

    return PoolStats(
        total_eligible=total_eligible,
        dominant_attachment_styles=dominant_attachment,
        differentiating_dimensions=differentiators,
    )
