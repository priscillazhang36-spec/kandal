from kandal.scoring.dealbreakers import passes_dealbreakers


def test_passes_basic(make_user):
    pa, pref_a = make_user(age=28, gender="female", gender_preferences=["male"])
    pb, pref_b = make_user(age=30, gender="male", gender_preferences=["female"])
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True


def test_fails_age_too_old(make_user):
    pa, pref_a = make_user(age=28, gender="female", gender_preferences=["male"], max_age=35)
    pb, pref_b = make_user(age=40, gender="male", gender_preferences=["female"])
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_fails_gender_mismatch(make_user):
    pa, pref_a = make_user(age=28, gender="female", gender_preferences=["male"])
    pb, pref_b = make_user(age=30, gender="male", gender_preferences=["male"])
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_fails_distance(make_user):
    # NYC to LA is ~3,940 km
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        lat=40.7, lng=-74.0, max_distance_km=50,
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        lat=34.0, lng=-118.2, max_distance_km=50,
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_fails_relationship_type(make_user):
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        relationship_types=["long_term"],
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        relationship_types=["casual"],
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_passes_no_location(make_user):
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"], lat=None, lng=None,
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"], lat=34.0, lng=-118.2,
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True


def test_bidirectional_age(make_user):
    """A accepts B's age, but B does NOT accept A's age."""
    pa, pref_a = make_user(
        age=22, gender="female", gender_preferences=["male"], min_age=20, max_age=40,
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"], min_age=25, max_age=35,
    )
    # B wants 25-35, A is 22 → fail
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


# v4.2 — lifestyle dealbreaker checks (paired + symmetric)


def _het_pair(make_user, **overrides_a):
    """Helper: matched het pair, layered with custom overrides on user A."""
    a_kw = dict(age=28, gender="female", gender_preferences=["male"])
    a_kw.update(overrides_a)
    pa, pref_a = make_user(**a_kw)
    pb, pref_b = make_user(age=30, gender="male", gender_preferences=["female"])
    return pa, pref_a, pb, pref_b


def test_fails_relationship_intent_gap(make_user):
    """Casual on one side + marriage_track on the other = hard fail."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        relationship_intent="casual",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        relationship_intent="marriage_track",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_passes_relationship_intent_adjacent(make_user):
    """Dating + serious is one rung apart — should pass."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        relationship_intent="dating",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        relationship_intent="serious",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True


def test_fails_relationship_structure_mismatch(make_user):
    """Monogamous + poly without an 'open' wildcard fails."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        relationship_structure="monogamous",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        relationship_structure="poly",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_passes_relationship_structure_open_wildcard(make_user):
    """'open' (figuring it out) on one side flexes to anything on the other."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        relationship_structure="open",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        relationship_structure="monogamous",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True


def test_fails_religion_gap(make_user):
    """'very' importance + 'not_important' = gap of 2 = fail."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        religion_importance="very",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        religion_importance="not_important",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_fails_wants_kids_explicit_mismatch(make_user):
    """yes/no on wants_kids = fail; maybe/open passes."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"], wants_kids="yes",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"], wants_kids="no",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_passes_wants_kids_one_side_maybe(make_user):
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"], wants_kids="yes",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"], wants_kids="maybe",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True


def test_fails_partner_wants_kids_no_vs_existing_kids(make_user):
    """A wants partner without kids; B already has kids → fail."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        partner_wants_kids="no",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        has_kids="yes", wants_kids="no",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_fails_partner_substances_max_never_vs_regular_drinker(make_user):
    """A is sober & expects partner-never; B drinks regularly → fail."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        drinks="never", partner_substances_max="never",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        drinks="regularly",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_fails_religion_mismatch_when_both_very_important(make_user):
    """Both 'very' on religion importance + different religions = fail."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        religion="muslim", religion_importance="very",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        religion="hindu", religion_importance="very",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is False


def test_passes_religion_mismatch_when_one_side_somewhat(make_user):
    """If only one side is 'very' (other is 'somewhat'), religion match not required."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        religion="muslim", religion_importance="very",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        religion="hindu", religion_importance="somewhat",
    )
    # gap of 1 — religion-importance check passes; religion-match doesn't fire
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True


def test_passes_religion_match_both_very(make_user):
    """Same religion + both very = passes."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        religion="catholic", religion_importance="very",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        religion="catholic", religion_importance="very",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True


def test_passes_partner_substances_max_open(make_user):
    """A's tolerance 'open' bypasses substance check."""
    pa, pref_a = make_user(
        age=28, gender="female", gender_preferences=["male"],
        partner_substances_max="open",
    )
    pb, pref_b = make_user(
        age=30, gender="male", gender_preferences=["female"],
        drinks="regularly", smokes="regularly",
    )
    assert passes_dealbreakers(pa, pref_a, pb, pref_b) is True
