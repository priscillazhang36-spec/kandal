"""Ingest a Cinder-sheet TSV (women's or men's tab) into cinder_profiles.

Usage:
    python -m kandal.scripts.ingest_cinder data/cinder/women_seed.tsv women
    python -m kandal.scripts.ingest_cinder data/cinder/men_seed.tsv   men

The TSV column order must match the corresponding tab's column order in the
source Google Sheet. Empty cells become NULL. Numeric columns are coerced.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from kandal.core.supabase import get_supabase

WOMEN_COLUMNS = [
    "age", "first_name", "last_name", "gender", "photo_url",
    "relationship_intent", "ethnicity", "politics", "religion", "occupation",
    "income_range", "mbti", "qualities", "hobbies", "attractiveness",
    "intelligence", "social_energy", "height", "body_type", "education_level",
    "has_kids", "wants_kids", "activity_score", "alcohol_score",
    "smoking_score", "cannabis_score", "preferences", "preference1",
    "preference2", "preference3", "preference_profile",
]

MEN_COLUMNS = [
    "age", "first_name", "last_name", "photo_url", "relationship_intent",
    "ethnicity", "politics", "religion", "occupation", "income_range", "mbti",
    "extroversion", "agreeableness", "conscientiousness", "neuroticism",
    "openness", "qualities", "hobbies", "attractiveness", "intelligence",
    "social_energy", "height", "body_type", "education_level", "has_kids",
    "wants_kids", "activity_score", "alcohol_score", "smoking_score",
    "cannabis_score", "preferences_updated_at", "preferences", "preference1",
    "preference2", "preference3", "may_invite", "may_response", "april_invite",
    "april_response",
]

INT_COLUMNS = {
    "age", "attractiveness", "intelligence", "height", "activity_score",
    "alcohol_score", "smoking_score", "cannabis_score", "extroversion",
    "agreeableness", "conscientiousness", "neuroticism", "openness",
}


def parse_row(raw: list[str], columns: list[str], default_gender: str) -> dict:
    padded = raw + [""] * (len(columns) - len(raw))
    out: dict = {}
    for col, val in zip(columns, padded):
        val = val.strip()
        if not val:
            out[col] = None
        elif col in INT_COLUMNS:
            out[col] = int(val)
        else:
            out[col] = val
    if "gender" not in out or out.get("gender") is None:
        out["gender"] = default_gender
    return out


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in {"women", "men"}:
        print(__doc__)
        sys.exit(1)
    tsv_path = Path(sys.argv[1])
    tab = sys.argv[2]
    columns = WOMEN_COLUMNS if tab == "women" else MEN_COLUMNS
    default_gender = "woman" if tab == "women" else "man"

    with tsv_path.open(newline="") as f:
        rows = [
            parse_row(row, columns, default_gender)
            for row in csv.reader(f, delimiter="\t")
            if any(cell.strip() for cell in row)
        ]

    print(f"Parsed {len(rows)} rows from {tsv_path}")
    sb = get_supabase()
    resp = sb.table("cinder_profiles").insert(rows).execute()
    print(f"Inserted {len(resp.data)} rows into cinder_profiles")


if __name__ == "__main__":
    main()
