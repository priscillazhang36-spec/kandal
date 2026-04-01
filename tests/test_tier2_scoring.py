from kandal.scoring.engine import (
    _score_attachment_style,
    _score_conflict_style,
    _score_love_language_fit,
    _score_relationship_history,
)
from kandal.models.preferences import Preferences
from uuid import uuid4

LANGS = ["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"]


def _prefs(**kw):
    return Preferences(id=uuid4(), profile_id=uuid4(), **kw)


# --- Attachment ---

def test_attachment_secure_secure():
    assert _score_attachment_style(_prefs(attachment_style="secure"), _prefs(attachment_style="secure")) == 1.0


def test_attachment_anxious_avoidant():
    assert _score_attachment_style(_prefs(attachment_style="anxious"), _prefs(attachment_style="avoidant")) == 0.0


def test_attachment_none_returns_neutral():
    assert _score_attachment_style(_prefs(attachment_style=None), _prefs(attachment_style="secure")) == 0.5


def test_attachment_matrix_symmetric():
    for a in ("secure", "anxious", "avoidant", "disorganized"):
        for b in ("secure", "anxious", "avoidant", "disorganized"):
            s1 = _score_attachment_style(_prefs(attachment_style=a), _prefs(attachment_style=b))
            s2 = _score_attachment_style(_prefs(attachment_style=b), _prefs(attachment_style=a))
            assert s1 == s2, f"Asymmetry: {a}+{b}={s1}, {b}+{a}={s2}"


# --- Conflict ---

def test_conflict_collaborative_collaborative():
    assert _score_conflict_style(_prefs(conflict_style="collaborative"), _prefs(conflict_style="collaborative")) == 1.0


def test_conflict_avoidant_talk_immediately():
    assert _score_conflict_style(_prefs(conflict_style="avoidant"), _prefs(conflict_style="talk_immediately")) == 0.1


def test_conflict_none_returns_neutral():
    assert _score_conflict_style(_prefs(conflict_style=None), _prefs(conflict_style="collaborative")) == 0.5


# --- Love language ---

def test_love_language_perfect_match():
    """A gives what B wants and vice versa."""
    a = _prefs(love_language_giving=LANGS, love_language_receiving=LANGS)
    b = _prefs(love_language_giving=LANGS, love_language_receiving=LANGS)
    assert _score_love_language_fit(a, b) == 1.0


def test_love_language_mismatch():
    """A's top giving is B's bottom receiving."""
    a = _prefs(
        love_language_giving=["gifts", "physical_touch", "acts_of_service", "quality_time", "words_of_affirmation"],
        love_language_receiving=["gifts", "physical_touch", "acts_of_service", "quality_time", "words_of_affirmation"],
    )
    b = _prefs(
        love_language_giving=["words_of_affirmation", "quality_time", "acts_of_service", "physical_touch", "gifts"],
        love_language_receiving=["words_of_affirmation", "quality_time", "acts_of_service", "physical_touch", "gifts"],
    )
    score = _score_love_language_fit(a, b)
    assert score == 0.10  # both directions: top giving is last in receiving


def test_love_language_empty_returns_neutral():
    assert _score_love_language_fit(_prefs(), _prefs(love_language_giving=LANGS, love_language_receiving=LANGS)) == 0.5


# --- Relationship history ---

def test_relationship_history_same():
    assert _score_relationship_history(_prefs(relationship_history="long_term"), _prefs(relationship_history="long_term")) == 1.0


def test_relationship_history_opposite():
    score = _score_relationship_history(_prefs(relationship_history="long_term"), _prefs(relationship_history="limited_experience"))
    assert score == 0.0


def test_relationship_history_one_step():
    score = _score_relationship_history(_prefs(relationship_history="long_term"), _prefs(relationship_history="mostly_casual"))
    assert abs(score - 2 / 3) < 0.001


def test_relationship_history_none_returns_neutral():
    assert _score_relationship_history(_prefs(relationship_history=None), _prefs(relationship_history="long_term")) == 0.5
