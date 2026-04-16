import pytest

from kandal.questionnaire.inference import infer_traits
from kandal.questionnaire.questions import QUESTIONS


# New 4-question set:
# Q1: partner cancels → attachment (A=secure, B=anxious, C=avoidant, D=disorganized) + conflict
# Q2: after argument → love_giving (A=WoA, B=QT, C=AoS, D=gifts) + conflict
# Q3: felt loved → love_receiving (A=WoA, B=QT, C=AoS, D=physical_touch)
# Q4: history → (A=long_term, B=mostly_casual, C=recently_out, D=limited)


def test_infer_secure_attachment():
    """Q1=A gives secure attachment."""
    answers = [0, 0, 0, 0]
    traits = infer_traits(answers)
    assert traits.attachment_style == "secure"


def test_infer_anxious_attachment():
    """Q1=B gives anxious attachment."""
    answers = [1, 0, 0, 0]
    traits = infer_traits(answers)
    assert traits.attachment_style == "anxious"


def test_infer_avoidant_attachment():
    """Q1=C gives avoidant attachment."""
    answers = [2, 0, 0, 0]
    traits = infer_traits(answers)
    assert traits.attachment_style == "avoidant"


def test_infer_disorganized_attachment():
    """Q1=D gives disorganized attachment."""
    answers = [3, 0, 0, 0]
    traits = infer_traits(answers)
    assert traits.attachment_style == "disorganized"


def test_infer_love_language_giving():
    """Q2=B gives quality_time as top giving language."""
    answers = [0, 1, 0, 0]
    traits = infer_traits(answers)
    assert traits.love_language_giving[0] == "quality_time"


def test_infer_love_language_receiving():
    """Q3=D gives physical_touch as top receiving language."""
    answers = [0, 0, 3, 0]
    traits = infer_traits(answers)
    assert traits.love_language_receiving[0] == "physical_touch"


def test_infer_conflict_collaborative():
    """Q1=A (collaborative) + Q2=B (collaborative) gives collaborative conflict."""
    answers = [0, 1, 0, 0]
    traits = infer_traits(answers)
    assert traits.conflict_style == "collaborative"


def test_infer_history_direct():
    """Q4=C gives recently_out_of_ltr."""
    answers = [0, 0, 0, 2]
    traits = infer_traits(answers)
    assert traits.relationship_history == "recently_out_of_ltr"


def test_love_language_ranking_complete():
    """Ranked list always contains all 5 love languages."""
    answers = [0, 0, 0, 0]
    traits = infer_traits(answers)
    assert len(traits.love_language_giving) == 5
    assert len(traits.love_language_receiving) == 5
    assert set(traits.love_language_giving) == {
        "words_of_affirmation", "quality_time", "physical_touch",
        "acts_of_service", "gifts",
    }


def test_wrong_answer_count():
    with pytest.raises(ValueError, match=f"Expected {len(QUESTIONS)}"):
        infer_traits([0, 0, 0])


def test_answer_out_of_range():
    with pytest.raises(ValueError, match="out of range"):
        infer_traits([0, 0, 0, 5])
