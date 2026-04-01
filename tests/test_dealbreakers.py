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
