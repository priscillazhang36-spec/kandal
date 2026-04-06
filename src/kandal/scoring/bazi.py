"""Chinese Bazi (Four Pillars of Destiny) computation and compatibility scoring.

Pure functions — no DB or API calls. Takes birth date/time, returns pillars
and element-based compatibility scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# ---------- Constants ----------

HEAVENLY_STEMS = ["jia", "yi", "bing", "ding", "wu", "ji", "geng", "xin", "ren", "gui"]
EARTHLY_BRANCHES = ["zi", "chou", "yin", "mao", "chen", "si", "wu_branch", "wei", "shen", "you", "xu", "hai"]

# Each stem maps to an element (pairs: 0-1 wood, 2-3 fire, 4-5 earth, 6-7 metal, 8-9 water)
STEM_ELEMENTS = {
    0: "wood", 1: "wood",
    2: "fire", 3: "fire",
    4: "earth", 5: "earth",
    6: "metal", 7: "metal",
    8: "water", 9: "water",
}

# Each branch's primary element
BRANCH_ELEMENTS = {
    0: "water",   # zi
    1: "earth",   # chou
    2: "wood",    # yin
    3: "wood",    # mao
    4: "earth",   # chen
    5: "fire",    # si
    6: "fire",    # wu_branch
    7: "earth",   # wei
    8: "metal",   # shen
    9: "metal",   # you
    10: "earth",  # xu
    11: "water",  # hai
}

# Generating (sheng) cycle: wood -> fire -> earth -> metal -> water -> wood
GENERATING = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}

# Controlling (ke) cycle: wood -> earth -> water -> fire -> metal -> wood
CONTROLLING = {
    "wood": "earth",
    "earth": "water",
    "water": "fire",
    "fire": "metal",
    "metal": "wood",
}

# Six Harmonies (六合) — branch index pairs that harmonize
SIX_HARMONIES = frozenset({
    (0, 1),    # zi-chou
    (2, 11),   # yin-hai
    (3, 10),   # mao-xu
    (4, 9),    # chen-you
    (5, 8),    # si-shen
    (6, 7),    # wu-wei
})

# Three Harmonies (三合) — branch trios forming elemental frames
THREE_HARMONIES = [
    frozenset({0, 4, 8}),    # water frame: zi-chen-shen
    frozenset({1, 5, 9}),    # metal frame: chou-si-you
    frozenset({2, 6, 10}),   # fire frame: yin-wu-xu
    frozenset({3, 7, 11}),   # wood frame: mao-wei-hai
]

# Six Clashes (六冲) — branch index pairs that clash
SIX_CLASHES = frozenset({
    (0, 6),    # zi-wu
    (1, 7),    # chou-wei
    (2, 8),    # yin-shen
    (3, 9),    # mao-you
    (4, 10),   # chen-xu
    (5, 11),   # si-hai
})

# Month stem offset by year stem (for computing month pillar stem)
# If year stem is X, month 1 (yin month) stem starts at MONTH_STEM_START[X % 5]
MONTH_STEM_START = {0: 2, 1: 4, 2: 6, 3: 8, 4: 0}  # jia/ji->bing, yi/geng->wu, ...

# Hour stem offset by day stem
# If day stem is X, zi hour stem starts at HOUR_STEM_START[X % 5]
HOUR_STEM_START = {0: 0, 1: 2, 2: 4, 3: 6, 4: 8}  # jia/ji->jia, yi/geng->bing, ...

# Approximate solar term start dates (month, day) for each Chinese month boundary
# Chinese month 1 starts at Start of Spring (~Feb 4)
SOLAR_TERM_STARTS = [
    (2, 4),   # month 1: Start of Spring
    (3, 6),   # month 2: Awakening of Insects
    (4, 5),   # month 3: Clear and Bright
    (5, 6),   # month 4: Start of Summer
    (6, 6),   # month 5: Grain in Ear
    (7, 7),   # month 6: Slight Heat
    (8, 8),   # month 7: Start of Autumn
    (9, 8),   # month 8: White Dew
    (10, 8),  # month 9: Cold Dew
    (11, 7),  # month 10: Start of Winter
    (12, 7),  # month 11: Heavy Snow
    (1, 6),   # month 12: Slight Cold (next year's Jan)
]

# Hour branch mapping: hour of day (0-23) -> branch index
# Each Chinese hour spans 2 hours: zi=23-01, chou=01-03, ..., hai=21-23
HOUR_TO_BRANCH = {
    23: 0, 0: 0,    # zi
    1: 1, 2: 1,     # chou
    3: 2, 4: 2,     # yin
    5: 3, 6: 3,     # mao
    7: 4, 8: 4,     # chen
    9: 5, 10: 5,    # si
    11: 6, 12: 6,   # wu
    13: 7, 14: 7,   # wei
    15: 8, 16: 8,   # shen
    17: 9, 18: 9,   # you
    19: 10, 20: 10, # xu
    21: 11, 22: 11, # hai
}


# ---------- Data structures ----------

@dataclass(frozen=True)
class Pillar:
    stem: int    # 0-9
    branch: int  # 0-11


@dataclass(frozen=True)
class FourPillars:
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar | None  # None if birth time unknown


@dataclass(frozen=True)
class BaziProfile:
    pillars: FourPillars
    day_master: str  # element: "wood", "fire", "earth", "metal", "water"


# ---------- Pillar computation ----------

def _chinese_month(birth_date: date) -> int:
    """Return Chinese solar month (1-12) for a Gregorian date."""
    md = (birth_date.month, birth_date.day)
    # Walk backwards through solar terms to find which month we're in
    for i in range(11, -1, -1):
        term_month, term_day = SOLAR_TERM_STARTS[i]
        if i == 11:
            # Month 12 starts in Jan of the same year
            if md >= (term_month, term_day) and birth_date.month == 1:
                return 12
        elif md >= (term_month, term_day):
            return i + 1
    # Before Start of Spring (Feb 4) — still in previous year's month 12
    return 12


def _chinese_year(birth_date: date) -> int:
    """Return Chinese year number. Before Start of Spring, it's the previous year."""
    if (birth_date.month, birth_date.day) < (2, 4):
        return birth_date.year - 1
    return birth_date.year


def _julian_day_number(d: date) -> int:
    """Compute Julian Day Number for a Gregorian date."""
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


# Reference: Jan 7, 1924 is a 甲子 (jiazi) day — stem=0, branch=0
_REF_DATE = date(1924, 1, 7)
_REF_JDN = _julian_day_number(_REF_DATE)


def compute_four_pillars(birth_date: date, birth_hour: int | None = None) -> FourPillars:
    """Compute the Four Pillars from a Gregorian date and optional hour (0-23)."""
    cyear = _chinese_year(birth_date)

    # Year pillar
    year_stem = (cyear - 4) % 10
    year_branch = (cyear - 4) % 12

    # Month pillar
    # Month 1 (tiger month) -> branch 2 (yin), month 2 -> branch 3 (mao), ...
    # month 11 -> branch 0 (zi), month 12 -> branch 1 (chou)
    cmonth = _chinese_month(birth_date)
    month_branch = (cmonth + 1) % 12
    month_stem_start = MONTH_STEM_START[year_stem % 5]
    month_stem = (month_stem_start + cmonth - 1) % 10

    # Day pillar
    jdn = _julian_day_number(birth_date)
    days_since_ref = jdn - _REF_JDN
    day_stem = days_since_ref % 10
    day_branch = days_since_ref % 12

    # Hour pillar (optional)
    hour_pillar = None
    if birth_hour is not None:
        hour_branch = HOUR_TO_BRANCH.get(birth_hour % 24, 0)
        hour_stem_start = HOUR_STEM_START[day_stem % 5]
        hour_stem = (hour_stem_start + hour_branch) % 10
        hour_pillar = Pillar(stem=hour_stem, branch=hour_branch)

    return FourPillars(
        year=Pillar(stem=year_stem, branch=year_branch),
        month=Pillar(stem=month_stem, branch=month_branch),
        day=Pillar(stem=day_stem, branch=day_branch),
        hour=hour_pillar,
    )


def get_day_master(pillars: FourPillars) -> str:
    """Return the element of the day stem (the Day Master)."""
    return STEM_ELEMENTS[pillars.day.stem]


def compute_bazi_profile(birth_date: date, birth_hour: int | None = None) -> BaziProfile:
    """Compute Four Pillars and Day Master from birth date/time."""
    pillars = compute_four_pillars(birth_date, birth_hour)
    return BaziProfile(pillars=pillars, day_master=get_day_master(pillars))


# ---------- Compatibility scoring ----------

def _element_relationship_score(elem_a: str, elem_b: str) -> float:
    """Score the relationship between two elements (Day Masters)."""
    if elem_a == elem_b:
        return 0.7  # same element — familiar but may lack growth
    if GENERATING[elem_a] == elem_b:
        return 0.9  # A generates B — nurturing, supportive
    if GENERATING[elem_b] == elem_a:
        return 0.85  # B generates A — receiving support
    if CONTROLLING[elem_a] == elem_b:
        return 0.35  # A controls B — can feel dominating
    if CONTROLLING[elem_b] == elem_a:
        return 0.3   # B controls A — can feel constrained
    return 0.5  # shouldn't happen with 5 elements, but safe default


def _is_harmony(branch_a: int, branch_b: int) -> bool:
    """Check if two branches form a Six Harmony pair."""
    pair = (min(branch_a, branch_b), max(branch_a, branch_b))
    return pair in SIX_HARMONIES


def _is_clash(branch_a: int, branch_b: int) -> bool:
    """Check if two branches form a Six Clash pair."""
    pair = (min(branch_a, branch_b), max(branch_a, branch_b))
    return pair in SIX_CLASHES


def _share_three_harmony(branch_a: int, branch_b: int) -> bool:
    """Check if two branches belong to the same Three Harmony trio."""
    return any(branch_a in trio and branch_b in trio for trio in THREE_HARMONIES)


def _branch_harmony_score(pillars_a: FourPillars, pillars_b: FourPillars) -> float:
    """Score branch harmonies between all comparable pillar pairs. Returns 0-1."""
    pairs_a = [pillars_a.year, pillars_a.month, pillars_a.day]
    pairs_b = [pillars_b.year, pillars_b.month, pillars_b.day]
    if pillars_a.hour and pillars_b.hour:
        pairs_a.append(pillars_a.hour)
        pairs_b.append(pillars_b.hour)

    harmony_points = 0.0
    comparisons = 0
    for pa in pairs_a:
        for pb in pairs_b:
            comparisons += 1
            if _is_harmony(pa.branch, pb.branch):
                harmony_points += 1.0
            elif _share_three_harmony(pa.branch, pb.branch):
                harmony_points += 0.5

    if comparisons == 0:
        return 0.5
    # Normalize: even 2-3 harmonies across 9-16 pairs is very good
    return min(1.0, harmony_points / (comparisons * 0.2))


def _branch_clash_score(pillars_a: FourPillars, pillars_b: FourPillars) -> float:
    """Penalty score for branch clashes. Returns 0-1 (1 = no clashes)."""
    pairs_a = [pillars_a.year, pillars_a.month, pillars_a.day]
    pairs_b = [pillars_b.year, pillars_b.month, pillars_b.day]
    if pillars_a.hour and pillars_b.hour:
        pairs_a.append(pillars_a.hour)
        pairs_b.append(pillars_b.hour)

    clash_count = 0
    comparisons = 0
    for pa in pairs_a:
        for pb in pairs_b:
            comparisons += 1
            if _is_clash(pa.branch, pb.branch):
                clash_count += 1

    if comparisons == 0:
        return 0.5
    # Each clash is significant; 2+ clashes is very bad
    return max(0.0, 1.0 - clash_count * 0.3)


def score_bazi_compatibility(bazi_a: BaziProfile, bazi_b: BaziProfile) -> float:
    """Score overall Bazi compatibility between two profiles. Returns 0.0-1.0.

    Components:
    - Day Master element relationship: 40% weight
    - Branch harmonies (六合, 三合): 35% weight
    - Branch clash penalty (六冲): 25% weight
    """
    element_score = _element_relationship_score(bazi_a.day_master, bazi_b.day_master)
    harmony_score = _branch_harmony_score(bazi_a.pillars, bazi_b.pillars)
    clash_score = _branch_clash_score(bazi_a.pillars, bazi_b.pillars)

    return round(
        element_score * 0.40 + harmony_score * 0.35 + clash_score * 0.25,
        4,
    )
