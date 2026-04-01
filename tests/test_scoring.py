from kandal.scoring.engine import DIMENSION_WEIGHTS, score_compatibility

LANGS = ["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"]


def test_perfect_overlap(make_user):
    """All dimensions match perfectly — including Tier 2."""
    shared = dict(
        interests=["hiking", "cooking", "music"],
        personality=["introvert", "creative"],
        values=["family", "career"],
        communication_style="texter",
        lifestyle=["early_bird", "active"],
        attachment_style="secure",
        love_language_giving=LANGS,
        love_language_receiving=LANGS,
        conflict_style="collaborative",
        relationship_history="long_term",
    )
    pa, pref_a = make_user(**shared)
    pb, pref_b = make_user(**shared)
    result = score_compatibility(pa, pref_a, pb, pref_b)
    assert result.total_score == 1.0


def test_zero_overlap(make_user):
    """All dimensions at worst-case mismatch."""
    pa, pref_a = make_user(
        interests=["hiking"], personality=["introvert"],
        values=["family"], communication_style="texter", lifestyle=["early_bird"],
        attachment_style="anxious",
        love_language_giving=["gifts", "physical_touch", "acts_of_service", "quality_time", "words_of_affirmation"],
        love_language_receiving=["gifts", "physical_touch", "acts_of_service", "quality_time", "words_of_affirmation"],
        conflict_style="talk_immediately",
        relationship_history="long_term",
    )
    pb, pref_b = make_user(
        interests=["gaming"], personality=["extrovert"],
        values=["adventure"], communication_style="caller", lifestyle=["night_owl"],
        attachment_style="avoidant",
        love_language_giving=["words_of_affirmation", "quality_time", "acts_of_service", "physical_touch", "gifts"],
        love_language_receiving=["words_of_affirmation", "quality_time", "acts_of_service", "physical_touch", "gifts"],
        conflict_style="avoidant",
        relationship_history="limited_experience",
    )
    result = score_compatibility(pa, pref_a, pb, pref_b)
    # Tier 1 all 0.0, attachment 0.0, conflict 0.1, love_lang low, history 0.0
    assert result.total_score < 0.05


def test_partial_overlap(make_user):
    pa, pref_a = make_user(interests=["a", "b", "c", "d"])
    pb, pref_b = make_user(interests=["a", "b", "e", "f"])
    result = score_compatibility(pa, pref_a, pb, pref_b)
    interest_dim = next(d for d in result.breakdown if d.dimension == "interest_overlap")
    assert abs(interest_dim.score - 2 / 6) < 0.001


def test_empty_profiles(make_user):
    """No data at all — everything returns neutral 0.5, except comm_style (both balanced = 1.0)."""
    pa, pref_a = make_user()
    pb, pref_b = make_user()
    result = score_compatibility(pa, pref_a, pb, pref_b)
    # Jaccard dims (0.18+0.12+0.12+0.08=0.50) * 0.5 = 0.25
    # comm_style: 0.05 * 1.0 = 0.05
    # Tier 2 all None (0.18+0.12+0.10+0.05=0.45) * 0.5 = 0.225
    # Total: 0.25 + 0.05 + 0.225 = 0.525
    assert abs(result.total_score - 0.525) < 0.001


def test_communication_balanced_wildcard(make_user):
    pa, pref_a = make_user(communication_style="balanced")
    pb, pref_b = make_user(communication_style="texter")
    result = score_compatibility(pa, pref_a, pb, pref_b)
    comm_dim = next(d for d in result.breakdown if d.dimension == "communication_style")
    assert comm_dim.score == 0.5


def test_weights_sum_to_one():
    total = sum(m["weight"] for m in DIMENSION_WEIGHTS.values())
    assert abs(total - 1.0) < 0.0001


def test_scoring_is_symmetric(make_user):
    pa, pref_a = make_user(
        interests=["hiking", "cooking"], personality=["introvert"],
        values=["family"], communication_style="texter", lifestyle=["early_bird"],
        attachment_style="secure", conflict_style="collaborative",
        relationship_history="long_term",
        love_language_giving=["quality_time", "words_of_affirmation", "physical_touch", "acts_of_service", "gifts"],
        love_language_receiving=["physical_touch", "quality_time", "words_of_affirmation", "acts_of_service", "gifts"],
    )
    pb, pref_b = make_user(
        interests=["cooking", "gaming"], personality=["extrovert", "introvert"],
        values=["career", "family"], communication_style="balanced", lifestyle=["active"],
        attachment_style="anxious", conflict_style="talk_immediately",
        relationship_history="mostly_casual",
        love_language_giving=["acts_of_service", "quality_time", "words_of_affirmation", "physical_touch", "gifts"],
        love_language_receiving=["quality_time", "acts_of_service", "words_of_affirmation", "physical_touch", "gifts"],
    )
    r1 = score_compatibility(pa, pref_a, pb, pref_b)
    r2 = score_compatibility(pb, pref_b, pa, pref_a)
    assert r1.total_score == r2.total_score
