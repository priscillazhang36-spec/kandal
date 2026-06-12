from uuid import uuid4

from kandal.models.cinder import CinderProfile
from kandal.scoring.cinder_baseline import passes_baseline
from kandal.scoring.cinder_prefs import (
    _parse_age_range,
    parse_preferences,
    render_prefs,
    stated_age_range,
)


def _cp(**kw):
    return CinderProfile(id=uuid4(), gender=kw.pop("gender", "woman"), **kw)


# ---------- parser ----------

def test_parse_preferences_priority_order():
    p = _cp(
        preferences="Qualities, Education level, Smoking",
        preference1="Emotionally intelligent, Ambitious",
        preference2="Postgrad",
        preference3="Non smoker",
    )
    parsed = parse_preferences(p)
    assert [pp.rank for pp in parsed] == [1, 2, 3]
    assert parsed[0].field_label == "Qualities"
    assert parsed[0].values == ["Emotionally intelligent", "Ambitious"]
    assert parsed[1].values == ["Postgrad"]
    assert parsed[2].values == ["Non smoker"]


def test_parse_preferences_empty():
    assert parse_preferences(_cp()) == []


def test_parse_preferences_skips_missing_value_slot():
    p = _cp(preferences="Age, Smoking", preference1="22 to 33")  # no preference2
    parsed = parse_preferences(p)
    assert len(parsed) == 1
    assert parsed[0].field_label == "Age"


def test_parse_age_range():
    assert _parse_age_range("22 to 33") == (22, 33)
    assert _parse_age_range("25-32") == (25, 32)
    assert _parse_age_range("33 to 22") == (22, 33)  # normalized
    assert _parse_age_range("nope") is None


def test_stated_age_range_only_when_listed():
    with_age = _cp(preferences="Age, Smoking", preference1="25 to 33", preference2="Non smoker")
    assert stated_age_range(with_age) == (25, 33)
    without_age = _cp(preferences="Smoking", preference1="Non smoker")
    assert stated_age_range(without_age) is None


def test_render_prefs():
    p = _cp(preferences="Age", preference1="25 to 33")
    assert render_prefs(parse_preferences(p)) == "Priority 1 — Age: 25 to 33"
    assert render_prefs([]) == "(none stated)"


# ---------- baseline gate ----------

def test_baseline_age_hard_cut_from_stated_range():
    woman = _cp(age=30, preferences="Age", preference1="25 to 33",
                relationship_intent="Relationship")
    in_range = _cp(gender="man", age=32, relationship_intent="Relationship")
    out_range = _cp(gender="man", age=40, relationship_intent="Relationship")
    assert passes_baseline(woman, in_range)[0] is True
    assert passes_baseline(woman, out_range)[0] is False


def test_baseline_age_default_window_when_unstated():
    woman = _cp(age=30, relationship_intent="Relationship")  # no Age pref -> +/-12
    assert passes_baseline(woman, _cp(gender="man", age=41, relationship_intent="Relationship"))[0] is True
    assert passes_baseline(woman, _cp(gender="man", age=43, relationship_intent="Relationship"))[0] is False


def test_baseline_friendship_only_excluded():
    woman = _cp(age=30, relationship_intent="Relationship")
    friend = _cp(gender="man", age=30, relationship_intent="Friendship")
    assert passes_baseline(woman, friend)[0] is False
    dater = _cp(gender="man", age=30, relationship_intent="Friendship, Relationship")
    assert passes_baseline(woman, dater)[0] is True


def test_baseline_kids_conflict():
    woman = _cp(age=30, relationship_intent="Relationship", wants_kids="wants_kids")
    no_kids = _cp(gender="man", age=30, relationship_intent="Relationship", wants_kids="do_not_want_kids")
    assert passes_baseline(woman, no_kids)[0] is False
    open_kids = _cp(gender="man", age=30, relationship_intent="Relationship", wants_kids="open_to_kids")
    assert passes_baseline(woman, open_kids)[0] is True


def test_baseline_blank_intent_passes():
    # Missing intent on a side should not hard-fail (can't evaluate).
    woman = _cp(age=30, relationship_intent="Relationship")
    man = _cp(gender="man", age=30)  # no relationship_intent
    assert passes_baseline(woman, man)[0] is True


# ---- substance dealbreakers ----

def test_substance_cannabis_dealbreaker():
    # She wants Cannabis "Never" (ceiling 1); he uses socially (2) -> fail.
    woman = _cp(age=30, relationship_intent="Relationship",
                preferences="Age, Cannabis", preference1="25 to 35", preference2="Never")
    user = _cp(gender="man", age=31, relationship_intent="Relationship")
    no_cannabis = _cp(gender="man", age=31, relationship_intent="Relationship", cannabis_score=1)
    socially = _cp(gender="man", age=31, relationship_intent="Relationship", cannabis_score=2)
    assert passes_baseline(woman, no_cannabis)[0] is True
    ok, audit = passes_baseline(woman, socially)
    assert ok is False and audit["substances_ok"] is False


def test_substance_socially_allows_up_to_social():
    # "Socially" tolerates up to 2, not 3.
    woman = _cp(age=30, relationship_intent="Relationship",
                preferences="Cannabis", preference1="Socially")
    assert passes_baseline(woman, _cp(gender="man", age=30, relationship_intent="Relationship", cannabis_score=2))[0] is True
    assert passes_baseline(woman, _cp(gender="man", age=30, relationship_intent="Relationship", cannabis_score=3))[0] is False


def test_substance_drinking_and_smoking():
    woman = _cp(age=30, relationship_intent="Relationship",
                preferences="Drinking, Smoking", preference1="Not at all", preference2="Non smoker")
    light = _cp(gender="man", age=30, relationship_intent="Relationship", alcohol_score=1, smoking_score=1)
    drinker = _cp(gender="man", age=30, relationship_intent="Relationship", alcohol_score=3, smoking_score=1)
    smoker = _cp(gender="man", age=30, relationship_intent="Relationship", alcohol_score=1, smoking_score=2)
    assert passes_baseline(woman, light)[0] is True
    assert passes_baseline(woman, drinker)[0] is False
    assert passes_baseline(woman, smoker)[0] is False


def test_substance_bilateral_and_unknown_skips():
    # His Smoking "Non smoker" pref applies to her usage too.
    man = _cp(gender="man", age=30, relationship_intent="Relationship",
              preferences="Smoking", preference1="Non smoker")
    smoker_woman = _cp(age=30, relationship_intent="Relationship", smoking_score=2)
    assert passes_baseline(smoker_woman, man)[0] is False
    # Unknown (None) usage on the target -> can't evaluate -> pass.
    unknown_woman = _cp(age=30, relationship_intent="Relationship")  # smoking_score None
    assert passes_baseline(unknown_woman, man)[0] is True
