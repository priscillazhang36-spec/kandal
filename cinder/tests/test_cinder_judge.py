from uuid import uuid4

from kandal.models.cinder import CinderProfile
from kandal.models.ideal_type import IdealType
from kandal.scoring.cinder_judge import _format_person_cinder


def _woman(**kw):
    return CinderProfile(id=uuid4(), gender="woman", first_name="Sarah", last_name="M", age=29, **kw)


def _ideal():
    return IdealType(
        profile_id=uuid4(),
        pull_pattern="grounded, quietly commanding masculine presence, never performed",
        pull_pattern_quote="strong jaw, deep voice energy",
        partner_traits=["quietly_commanding", "emotionally_grounded"],
        break_pattern="confidence that curdles into control",
        icks=["cocky put-you-in-your-place bro energy", "controlling/micromanaging"],
    )


def test_card_includes_ideal_type_block():
    card = _format_person_cinder("A", _woman(), is_woman=True, ideal_type=_ideal())
    assert "HER IDEAL TYPE" in card
    assert "quietly commanding masculine presence" in card  # pull_pattern
    assert "BREAK PATTERN" in card and "curdles into control" in card
    assert "ICKS" in card and "bro energy" in card
    assert "Quietly commanding" in card  # humanized partner_trait


def test_card_prefers_ideal_type_over_preference_profile():
    # When an ideal_type is present, the truncated preference_profile is not shown.
    w = _woman(preference_profile="OLD TRUNCATED TEXT")
    card = _format_person_cinder("A", w, is_woman=True, ideal_type=_ideal())
    assert "OLD TRUNCATED TEXT" not in card
    assert "HER IDEAL TYPE" in card


def test_card_falls_back_to_preference_profile_without_ideal_type():
    w = _woman(preference_profile="she likes grounded men")
    card = _format_person_cinder("A", w, is_woman=True, ideal_type=None)
    assert "HER IDEAL TYPE" not in card
    assert "she likes grounded men" in card


def test_man_card_never_gets_ideal_type():
    man = CinderProfile(id=uuid4(), gender="man", first_name="Kyle", last_name="W", age=32)
    card = _format_person_cinder("B", man, is_woman=False, ideal_type=_ideal())
    assert "HER IDEAL TYPE" not in card
