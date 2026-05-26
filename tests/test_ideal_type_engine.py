"""Unit tests for IdealTypeEngine state transitions.

Mocks the Anthropic client and the vignette generator + extractor so tests
don't depend on real LLM calls. Verifies the deterministic stage transitions
(dealbreakers → freeform → vignettes → awaiting_confirmation → complete) and
that the engine respects parser failures, hard cap, coverage check, and
correction flow.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from kandal.profiling import ideal_type_engine as ite
from kandal.profiling.ideal_type_engine import (
    IDEAL_TYPE_HARD_CAP,
    IdealTypeEngine,
    IdealTypeState,
)
from kandal.profiling.ideal_type_prompts import format_readback


# --- helpers ---


def _walk_dealbreakers(engine: IdealTypeEngine, state: IdealTypeState) -> None:
    """Run through the dealbreaker MCQ loop. Stops at celebrity_picks stage
    (the next stage after dealbreakers — caller must mock the generator if
    it wants to advance further).
    """
    answers = [
        "A",  # gender_preference -> ['male']
        "B",  # age 25-30
        "A",  # ethnicity_preference -> ['any']
        "A",  # religion_preference -> ['any']
        "A",  # relationship_intent -> long_term
        "C",  # partner_wants_kids -> open
        "A",  # partner_smokes_max -> none
        "B",  # partner_drinks_max -> social
        "A",  # partner_cannabis_max -> none
        "B",  # visual_importance -> secondary
    ]
    for ans in answers:
        engine.next_turn(state, ans)


def _walk_celebrities(engine: IdealTypeEngine, state: IdealTypeState) -> None:
    """After dealbreakers, walk through whatever celebrity pairs are loaded
    in state with simple 'A' picks. Leaves state at freeform stage.
    """
    while state.stage == "celebrity_picks":
        engine.next_turn(state, "A")


def _mock_anthropic_reply(text: str) -> MagicMock:
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    return m


# --- Stage 0: dealbreakers ---


def test_start_returns_opening_and_dealbreakers_stage():
    engine = IdealTypeEngine()
    state, opening = engine.start(uuid4())
    assert state.stage == "dealbreakers"
    assert state.dealbreaker_index == 0
    assert "Kandal" in opening
    assert state.messages == [{"role": "assistant", "content": opening}]


def test_dealbreaker_loop_accumulates_answers():
    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    turn = engine.next_turn(state, "B")  # gender_preference B → ['female']
    assert state.dealbreaker_answers["gender_preference"] == ["female"]
    assert turn.stage == "dealbreakers"
    assert "age range" in turn.reply.lower()


def test_invalid_dealbreaker_letter_reprompts():
    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    turn = engine.next_turn(state, "🤷")  # nothing parseable
    # Reprompt — same question, no advance.
    assert state.dealbreaker_index == 0
    assert "Didn't quite catch" in turn.reply
    assert state.dealbreaker_answers == {}


@patch.object(ite, "generate_celebrity_pairs")
def test_dealbreaker_completion_transitions_to_celebrity_picks(mock_celeb_gen):
    mock_celeb_gen.return_value = [
        {"axis": "classic_vs_soft",
         "a": {"name": "A1", "descriptor": "..."},
         "b": {"name": "B1", "descriptor": "..."}},
        {"axis": "warm_vs_intense",
         "a": {"name": "A2", "descriptor": "..."},
         "b": {"name": "B2", "descriptor": "..."}},
    ]
    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    assert state.stage == "celebrity_picks"
    assert state.celebrity_pair_index == 0
    assert len(state.celebrity_pairs) == 2
    assert mock_celeb_gen.called
    assert state.dealbreaker_answers.get("visual_importance") == "secondary"


@patch.object(ite, "generate_celebrity_pairs")
def test_celebrity_picks_accumulate_and_transition_to_freeform(mock_celeb_gen):
    mock_celeb_gen.return_value = [
        {"axis": "classic_vs_soft",
         "a": {"name": "Henry", "descriptor": "sharp, classic"},
         "b": {"name": "Tim", "descriptor": "soft, distinctive"}},
        {"axis": "warm_vs_intense",
         "a": {"name": "Pedro", "descriptor": "warm, grounded"},
         "b": {"name": "Cillian", "descriptor": "intense, magnetic"}},
    ]
    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    assert state.stage == "celebrity_picks"

    # First pick: B with reasoning.
    engine.next_turn(state, "B because Tim's vibe lands more")
    assert len(state.celebrity_choices) == 1
    assert state.celebrity_choices[0]["picked"] == "b"
    assert state.celebrity_choices[0]["user_reply"].startswith("B because")
    assert state.stage == "celebrity_picks"

    # Second pick: A.
    engine.next_turn(state, "A")
    assert len(state.celebrity_choices) == 2
    assert state.celebrity_choices[1]["picked"] == "a"
    # Now transitioned to freeform.
    assert state.stage == "freeform"
    assert state.questions_asked == 1


@patch.object(ite, "generate_celebrity_pairs")
def test_celebrity_generator_failure_skips_to_freeform(mock_celeb_gen):
    """If the generator throws, the engine should skip the stage and go to
    freeform — losing the visual signal is better than killing the session.
    """
    mock_celeb_gen.side_effect = RuntimeError("LLM unavailable")
    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    assert state.stage == "freeform"
    assert state.celebrity_pairs == []
    assert state.celebrity_choices == []


def test_neither_parser_recognizes_common_phrases():
    """parse_pick falls back to 'neither' when the user doesn't pick A or B."""
    from kandal.profiling.ideal_type_celebrities import parse_pick
    assert parse_pick("A") == "a"
    assert parse_pick("B because he's hotter") == "b"
    assert parse_pick("neither honestly") == "neither"
    assert parse_pick("either is fine") == "neither"
    assert parse_pick("idk both look the same") == "neither"


# --- Stage 1+2: freeform ---


@patch.object(ite, "generate_celebrity_pairs")
@patch.object(ite, "_get_client")
def test_freeform_advances_questions_asked(mock_get_client, mock_celeb_gen):
    mock_celeb_gen.return_value = [
        {"axis": "x", "a": {"name": "A", "descriptor": "..."},
         "b": {"name": "B", "descriptor": "..."}},
        {"axis": "y", "a": {"name": "C", "descriptor": "..."},
         "b": {"name": "D", "descriptor": "..."}},
    ]
    mock_get_client.return_value.messages.create.return_value = _mock_anthropic_reply(
        "Cool — tell me more about the moment."
    )
    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    _walk_celebrities(engine, state)
    assert state.stage == "freeform"
    assert state.questions_asked == 1

    engine.next_turn(state, "I felt drawn to her when she made a deadpan joke.")
    assert state.questions_asked == 2
    assert state.stage == "freeform"


@patch.object(ite, "extract_ideal_type")
@patch.object(ite, "generate_vignettes")
@patch.object(ite, "generate_celebrity_pairs")
@patch.object(ite, "_get_client")
def test_hits_hard_cap_forces_vignette_stage(
    mock_get_client, mock_celeb_gen, mock_vignettes, mock_extract
):
    """When questions_asked reaches hard cap, engine exits freeform regardless of coverage."""
    mock_celeb_gen.return_value = [
        {"axis": "x", "a": {"name": "A", "descriptor": "..."},
         "b": {"name": "B", "descriptor": "..."}},
        {"axis": "y", "a": {"name": "C", "descriptor": "..."},
         "b": {"name": "D", "descriptor": "..."}},
    ]
    mock_get_client.return_value.messages.create.return_value = _mock_anthropic_reply(
        "Tell me more."
    )
    mock_extract.return_value = {"past_pulls": [], "icks": []}
    mock_vignettes.return_value = [
        {"axis": "x", "a": {"name": "A", "sketch": "..."},
         "b": {"name": "B", "sketch": "..."}},
        {"axis": "y", "a": {"name": "C", "sketch": "..."},
         "b": {"name": "D", "sketch": "..."}},
    ]

    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    _walk_celebrities(engine, state)
    state.last_coverage_check_turn = IDEAL_TYPE_HARD_CAP  # skip coverage path
    state.questions_asked = IDEAL_TYPE_HARD_CAP

    turn = engine.next_turn(state, "yet another reply")
    assert state.stage == "vignettes"
    assert turn.stage == "vignettes"
    assert mock_vignettes.called
    assert state.vignettes


@patch.object(ite, "extract_ideal_type")
@patch.object(ite, "generate_vignettes")
@patch.object(ite, "generate_celebrity_pairs")
@patch.object(ite, "_get_client")
def test_coverage_check_refires_after_first_false_result(
    mock_get_client, mock_celeb_gen, mock_vignettes, mock_extract
):
    """The coverage check must re-fire on later turns if the first check
    returned false — otherwise the engine gets stuck looping LLM turns past
    the point of complete signal (the bug that hid Stage 3 in live testing).
    """
    # First coverage check at turn 5 returns false. Engine should call the
    # LLM for a freeform turn. Then at turn 7 (2 turns later) it should
    # re-fire — this time returning true → exit to vignettes.
    coverage_responses = iter([
        '{"pulls_covered": false, "ick_covered": false}',   # turn 5
        '{"pulls_covered": true, "ick_covered": true}',     # turn 7
    ])
    freeform_responses = iter([
        "Tell me more about the break.",  # turn 5 LLM reply
        "Got it.",                         # turn 6 LLM reply
    ])

    def messages_create(**kwargs):
        # COVERAGE_CHECK_PROMPT has the word "pulls_covered" in the system
        # prompt — use it to disambiguate from the freeform LLM call.
        if "pulls_covered" in kwargs.get("system", ""):
            return _mock_anthropic_reply(next(coverage_responses))
        return _mock_anthropic_reply(next(freeform_responses))

    mock_get_client.return_value.messages.create.side_effect = messages_create
    mock_extract.return_value = {"past_pulls": [], "icks": []}
    mock_celeb_gen.return_value = [
        {"axis": "x", "a": {"name": "A", "descriptor": "..."},
         "b": {"name": "B", "descriptor": "..."}},
        {"axis": "y", "a": {"name": "C", "descriptor": "..."},
         "b": {"name": "D", "descriptor": "..."}},
    ]
    mock_vignettes.return_value = [
        {"axis": "x", "a": {"name": "A", "sketch": "..."},
         "b": {"name": "B", "sketch": "..."}},
        {"axis": "y", "a": {"name": "C", "sketch": "..."},
         "b": {"name": "D", "sketch": "..."}},
    ]

    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    _walk_celebrities(engine, state)
    state.questions_asked = ite.COVERAGE_CHECK_MIN_TURN  # 5

    # Turn 5: coverage returns false, LLM freeform fires, advance to 6.
    engine.next_turn(state, "user reply at turn 5")
    assert state.stage == "freeform"
    assert state.questions_asked == 6
    assert state.last_coverage_check_turn == 5

    # Turn 6: coverage shouldn't re-fire yet (6 - 5 < 2), advance to 7.
    engine.next_turn(state, "user reply at turn 6")
    assert state.stage == "freeform"
    assert state.questions_asked == 7
    assert state.last_coverage_check_turn == 5

    # Turn 7: coverage re-fires (7 - 5 >= 2), returns true → vignettes.
    turn = engine.next_turn(state, "user reply at turn 7")
    assert state.stage == "vignettes"
    assert turn.stage == "vignettes"


@patch.object(ite, "extract_ideal_type")
@patch.object(ite, "generate_vignettes")
@patch.object(ite, "generate_celebrity_pairs")
@patch.object(ite, "_get_client")
def test_coverage_check_exits_freeform_when_both_covered(
    mock_get_client, mock_celeb_gen, mock_vignettes, mock_extract
):
    """If the coverage check returns both covered=true, exit freeform."""
    mock_celeb_gen.return_value = [
        {"axis": "x", "a": {"name": "A", "descriptor": "..."},
         "b": {"name": "B", "descriptor": "..."}},
        {"axis": "y", "a": {"name": "C", "descriptor": "..."},
         "b": {"name": "D", "descriptor": "..."}},
    ]
    mock_client = MagicMock()
    # First call (the LLM freeform call before coverage check fires) doesn't
    # happen because coverage runs FIRST when questions_asked >= COVERAGE_CHECK_TURN.
    mock_client.messages.create.return_value = _mock_anthropic_reply(
        '{"pulls_covered": true, "ick_covered": true}'
    )
    mock_get_client.return_value = mock_client
    mock_extract.return_value = {"past_pulls": [], "icks": []}
    mock_vignettes.return_value = [
        {"axis": "x", "a": {"name": "A", "sketch": "..."},
         "b": {"name": "B", "sketch": "..."}},
        {"axis": "y", "a": {"name": "C", "sketch": "..."},
         "b": {"name": "D", "sketch": "..."}},
    ]

    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    _walk_celebrities(engine, state)
    state.questions_asked = ite.COVERAGE_CHECK_MIN_TURN  # trigger coverage check

    turn = engine.next_turn(state, "her smirk was the moment")
    assert state.stage == "vignettes"
    assert turn.stage == "vignettes"


# --- Stage 3: vignettes ---


@patch.object(ite, "extract_ideal_type")
@patch.object(ite, "generate_vignettes")
@patch.object(ite, "generate_celebrity_pairs")
@patch.object(ite, "_get_client")
def test_vignette_loop_advances_and_finalizes(
    mock_get_client, mock_celeb_gen, mock_vignettes, mock_extract
):
    mock_celeb_gen.return_value = [
        {"axis": "x", "a": {"name": "A", "descriptor": "..."},
         "b": {"name": "B", "descriptor": "..."}},
        {"axis": "y", "a": {"name": "C", "descriptor": "..."},
         "b": {"name": "D", "descriptor": "..."}},
    ]
    mock_get_client.return_value.messages.create.return_value = _mock_anthropic_reply(
        "Got it — that's your pattern."  # used by both freeform turns and readback
    )
    pairs = [
        {"axis": "creative_vs_service", "a": {"name": "Mia", "sketch": "..."},
         "b": {"name": "Liv", "sketch": "..."}},
        {"axis": "in_motion_vs_settled", "a": {"name": "Sam", "sketch": "..."},
         "b": {"name": "Jo", "sketch": "..."}},
    ]
    mock_vignettes.return_value = pairs
    # First call (preliminary) AND second call (final) both return same shape.
    mock_extract.return_value = {
        "past_pulls": [],
        "icks": [],
        "pull_pattern": "synthesis",
        "break_pattern": None,
        "pull_pattern_quote": None,
        "partner_traits": ["trait1"],
        "vignette_choices": [],
    }

    engine = IdealTypeEngine()
    state, _ = engine.start(uuid4())
    _walk_dealbreakers(engine, state)
    _walk_celebrities(engine, state)
    state.questions_asked = IDEAL_TYPE_HARD_CAP
    state.last_coverage_check_turn = IDEAL_TYPE_HARD_CAP
    engine.next_turn(state, "go")  # hits hard cap → into vignettes
    assert state.stage == "vignettes"
    assert len(state.vignettes) == 2

    # First vignette reply.
    engine.next_turn(state, "A — she sounds more alive")
    assert state.vignette_index == 1
    assert state.stage == "vignettes"

    # Second vignette reply → triggers readback.
    turn = engine.next_turn(state, "B — quieter pulls me more")
    assert state.stage == "awaiting_confirmation"
    assert turn.artifact is not None
    assert turn.artifact["pull_pattern"] == "synthesis"


# --- Stage 4: readback / confirm ---


@patch.object(ite, "extract_ideal_type")
@patch.object(ite, "_get_client")
def test_readback_yes_finalizes(mock_get_client, mock_extract):
    mock_get_client.return_value.messages.create.return_value = _mock_anthropic_reply(
        "(readback narration)"
    )
    mock_extract.return_value = {
        "past_pulls": [],
        "icks": [],
        "pull_pattern": "synthesis",
        "break_pattern": None,
        "pull_pattern_quote": None,
        "partner_traits": [],
        "vignette_choices": [],
    }

    engine = IdealTypeEngine()
    state = IdealTypeState(
        profile_id=uuid4(),
        stage="awaiting_confirmation",
        pending_artifact={"pull_pattern": "synthesis"},
    )

    turn = engine.next_turn(state, "yes")
    assert turn.is_complete
    assert state.stage == "complete"
    assert "locked in" in turn.reply.lower()


# --- Deterministic readback formatter ---


def test_format_readback_renders_full_card():
    """Results card surfaces pull, break, traits, icks, and the demographics frame."""
    artifact = {
        "pull_pattern": "You're drawn to people whose minds cut through chaos — quiet, precise, decisive.",
        "break_pattern": "What tends to break it: partners eventually pull back emotionally.",
        "partner_traits": ["intellectual_edge", "quiet_presence", "decisiveness"],
        "icks": ["cheap", "loud energy"],
        "past_pulls": [{
            "broke_quote": "she stopped being curious about me",
        }],
    }
    dealbreakers = {
        "gender_preference": ["male"],
        "age_min": 28,
        "age_max": 38,
        "ethnicity_preference": ["any"],
        "religion_preference": ["any"],
        "partner_smokes_max": "none",
        "partner_drinks_max": "social",
        "partner_cannabis_max": "none",
        "partner_wants_kids": "open",
        "relationship_intent": "long_term",
        "visual_importance": "secondary",
    }
    celebrity_choices = [
        {
            "pair_index": 0,
            "axis": "classic_vs_soft",
            "a": {"name": "Henry Cavill", "descriptor": "sharp jaw, classic build"},
            "b": {"name": "Timothée Chalamet", "descriptor": "soft, distinctive"},
            "picked": "a",
            "user_reply": "A — sharper features pull me",
        },
        {
            "pair_index": 1,
            "axis": "warm_vs_intense",
            "a": {"name": "Pedro Pascal", "descriptor": "warm, grounded"},
            "b": {"name": "Cillian Murphy", "descriptor": "intense, magnetic"},
            "picked": "b",
            "user_reply": "B",
        },
    ]

    out = format_readback(artifact, dealbreakers, celebrity_choices)

    # Header
    assert "ideal-type profile" in out
    # Pull section
    assert "WHAT PULLS YOU IN" in out
    assert "minds cut through chaos" in out
    assert "intellectual edge" in out
    assert "quiet presence" in out
    # Break section + verbatim quote
    assert "WHAT TENDS TO BREAK IT" in out
    assert "pull back emotionally" in out
    assert "she stopped being curious about me" in out
    # Icks
    assert "HARD NOS" in out
    assert "cheap" in out
    assert "loud energy" in out
    # Frame
    assert "THE FRAME" in out
    assert "men" in out
    assert "28-38" in out
    assert "no smoking" in out
    assert "social drinking" in out
    assert "no cannabis" in out
    assert "open either way" in out
    assert "long-term" in out
    # Visual importance
    assert "secondary" in out
    # Celebrity picks section
    assert "VISUAL PULLS" in out
    assert "Henry Cavill" in out
    assert "Cillian Murphy" in out
    assert "over Timothée" in out  # picked Cavill over Chalamet
    assert "over Pedro" in out      # picked Murphy over Pascal
    # Confirm prompt
    assert "Yes" in out or "yes" in out


def test_format_readback_skips_empty_sections():
    """If break_pattern, icks, or traits are empty, those sections shouldn't appear."""
    artifact = {
        "pull_pattern": "Just pull, no other signal.",
        "break_pattern": None,
        "partner_traits": [],
        "icks": [],
        "past_pulls": [],
    }
    dealbreakers = {"gender_preference": ["female"]}

    out = format_readback(artifact, dealbreakers)

    assert "WHAT PULLS YOU IN" in out
    assert "WHAT TENDS TO BREAK IT" not in out
    assert "HARD NOS" not in out
    assert "You're drawn to" not in out  # no traits → no bullet list
    # Frame still rendered (gender at least).
    assert "THE FRAME" in out
    assert "women" in out


@patch.object(ite, "extract_ideal_type")
@patch.object(ite, "_get_client")
def test_readback_correction_reextracts(mock_get_client, mock_extract):
    """A non-yes reply re-runs extraction and produces a new readback."""
    mock_get_client.return_value.messages.create.return_value = _mock_anthropic_reply(
        "(updated readback)"
    )
    new_artifact = {
        "past_pulls": [],
        "icks": [],
        "pull_pattern": "updated synthesis",
        "break_pattern": None,
        "pull_pattern_quote": None,
        "partner_traits": [],
        "vignette_choices": [],
    }
    mock_extract.return_value = new_artifact

    engine = IdealTypeEngine()
    state = IdealTypeState(
        profile_id=uuid4(),
        stage="awaiting_confirmation",
        pending_artifact={"pull_pattern": "old synthesis"},
    )

    turn = engine.next_turn(state, "no, you missed that I want quiet not loud")
    assert not turn.is_complete
    assert state.stage == "awaiting_confirmation"
    assert state.pending_artifact["pull_pattern"] == "updated synthesis"
    assert turn.artifact == new_artifact
