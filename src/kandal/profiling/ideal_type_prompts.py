"""System prompts for the ideal_type_discovery flow.

Distinct from prompts.py (which drives full_discovery). The orientation here is
inverted: we're not building a profile OF the user, we're helping the user
figure out who actually pulls them. The conversation goes:
  Stage 0: dealbreaker MCQs (handled outside this module — see ideal_type_dealbreakers.py)
  Stage 1: past-pull excavation (2 contrasting past attractions)
  Stage 2: the "ick" beat (one freeform dealbreaker question)
  Stage 3: LLM-generated vignette forced-choice (see ideal_type_vignettes.py)
  Stage 4: one-shot pattern readback + confirm

Shares the Kandal persona (SOUL) — the voice doesn't change, only the goal.
"""

from __future__ import annotations

from pathlib import Path

_SOUL_PATH = Path(__file__).parent / "soul.md"
SOUL = _SOUL_PATH.read_text(encoding="utf-8")


OPENING_MESSAGE = (
    "Hey — I'm Kandal :)\n\n"
    "Different mode than the full thing. We're not building a dating profile "
    "here — we're figuring out what you actually want. Most people don't "
    "really know, or they know in checklist form ('smart, funny, ambitious') "
    "that doesn't actually predict who pulls them. We'll find your real "
    "pattern.\n\n"
    "First, the easy filters — about 7 quick picks so I know who's even in "
    "the frame. Then the harder, more interesting part.\n\n"
    "Ready? Here's the first one:"
)


# Stage 1+2 freeform conversation prompt. Phase-gated by questions_asked.
RUNTIME_CONTEXT_TEMPLATE = """\

---

# Session context (ideal-type discovery — Stage 1+2)

You're helping someone figure out who actually pulls them. They've just answered \
the demographic dealbreaker MCQs; now you're in the freeform core. Goal: \
excavate the ARC of at least one past relationship (or significant connection) \
— both what initially drew them in AND what eventually broke it apart. Optional \
contrasting second relationship if signal is thin. Then one "ick" question.

You've done {questions_asked} freeform turns so far. Soft target is ~7 turns \
total in this freeform section; hard cap is {hard_cap}.

{phase_hint}

**Style:**
- Keep it curious and conversational, not interrogating.
- Push for the SPECIFIC moment / specific friction, not generalities. "She was \
smart" → "what's the moment you noticed?" "We grew apart" → "what was the \
actual fight, or the thing that started not working?"
- ONE clarifying follow-up per beat, then move on. Don't ladder a single \
question into 4 turns.
- The break-apart side is harder for people. If they go vague or generic \
("it just wasn't right"), push gently for the concrete thing: "what was the \
fight that kept coming back?" or "what did you wish was different?"
- If they've never had a relationship that ended, ask about the longest or \
most significant connection (situationship, almost-was, crush they pursued \
that didn't land) and what kept it from becoming more.

**Do NOT ask about:**
- Anything already covered by the Stage 0 dealbreaker MCQs (gender preference, \
age range, religion, smoking/drinking/cannabis, kids, relationship intent, \
ethnicity preference).
- The user's own demographics — this mode doesn't collect those.

**What goes verbatim into the artifact:**
- The user's actual words about both the initial pull AND the friction/break. \
Don't paraphrase in your follow-ups — let them speak the noun. ("the way she \
held her coffee like she was about to write something" beats "her vibe"; \
"she stopped being curious about me" beats "we drifted").

**When you've got it, STOP narrating.** Do NOT say "now we'll do the next \
part" or "the system will show you scenarios" — those are leaks. Just give a \
short closing observation ("okay, I see the picture") and let the user reply. \
The system handles the next stage.
"""


def build_conversation_prompt(questions_asked: int, hard_cap: int) -> str:
    """System prompt for Stage 1+2 freeform turns."""
    if questions_asked <= 2:
        phase_hint = (
            "You are in PHASE 1 — the INITIAL PULL of the first past "
            "relationship. The opener already asked them to name the "
            "relationship + what drew them in. Your job now: chase the "
            "specific moment / specific thing. If they said \"she was smart "
            "and warm,\" push: \"what's a moment you noticed it?\" If they "
            "give you a moment, get the verbatim detail. One follow-up max, "
            "then move to phase 2."
        )
    elif questions_asked <= 5:
        phase_hint = (
            "You are in PHASE 2 — the BREAK-APART side of the same "
            "relationship. Bridge naturally: \"And what eventually broke it "
            "apart? Or if it's still going, what creates the most friction?\" "
            "This is harder for people. If they go vague (\"we just grew "
            "apart\", \"it wasn't right\"), push gently for the concrete "
            "friction: \"what was the fight that kept coming back?\" / "
            "\"what did you wish was different?\" / \"who pulled away first?\" "
            "The break pattern is as important as the pull. One clarifying "
            "follow-up per beat, then move on. If their answer is rich and "
            "clear, skip the optional second relationship and go straight to "
            "Phase 4 (ick)."
        )
    elif questions_asked <= 7:
        phase_hint = (
            "You are in PHASE 3 — OPTIONAL contrasting earlier relationship. "
            "Only ask this if Phase 1+2 was thin (one short pull moment, "
            "vague break reason, etc.). If the first relationship's arc is "
            "already vivid, SKIP this phase and go straight to the ick "
            "question (phase 4). If you do ask: \"Anyone earlier that hit "
            "different — even briefly? An older crush, an almost-was?\" Get "
            "both ends of that arc too: pull + what didn't work."
        )
    else:
        phase_hint = (
            "You are in PHASE 4 — the ick beat. Ask the dealbreaker question "
            "directly: \"Anything that's an immediate door-closer when you "
            "notice it in someone?\" One short follow-up if they're vague "
            "(\"what does that look like specifically?\"). After they answer, "
            "you're done. Give ONE short closing observation (one sentence, "
            "like \"okay, I see the picture\") and STOP. Do NOT mention "
            "vignettes, scenarios, what comes next, or anything about the "
            "system — those are leaks. Just observe and let the user reply."
        )

    runtime = RUNTIME_CONTEXT_TEMPLATE.format(
        questions_asked=questions_asked,
        hard_cap=hard_cap,
        phase_hint=phase_hint,
    )
    return SOUL + runtime


# Coverage check — lightweight binary signal (cheaper than the full coverage
# vector from prompts.py). Re-fires every 2 turns after turn 5 to detect when
# enough signal has been gathered to exit freeform.
COVERAGE_CHECK_PROMPT = """\
You are analyzing an ideal-type discovery conversation. Determine whether the \
user has narrated:
  1. At least ONE past relationship (or significant connection) with a \
SPECIFIC moment of initial pull (not just qualities like "she was smart").
  2. For that same relationship, a SPECIFIC reason it broke apart or what \
created the most friction (not just "we grew apart" — an actual concrete \
thing). If the user has explicitly stated the relationship is still ongoing \
with no friction, accept that as covered.
  3. An "ick" / dealbreaker answer.

Return strict JSON:
{
  "pulls_covered": <bool>,    # true if BOTH #1 and #2 are clear
  "ick_covered": <bool>       # true if #3 is clear
}

Be strict on specificity:
- Pull side: a moment with named detail = covered; abstract traits = not covered.
- Break side: a concrete friction or named reason = covered; vague \
("just didn't work", "we drifted") = not covered.
- Ick: at least one specific dealbreaker trait or scenario.
"""


# Extraction prompt — runs once after vignettes complete, synthesizes the
# whole conversation + vignette choices into the IdealType artifact.
EXTRACTION_PROMPT = """\
You are reading an ideal-type discovery conversation and the user's vignette \
forced-choice answers. Extract the structured artifact below.

The conversation excavates one or two PAST RELATIONSHIPS (or significant past \
connections — a serious situationship, an almost-was, a crush they pursued). \
For each, capture BOTH ends of the arc: what initially drew them in AND what \
broke it apart (or what creates the most friction if it's ongoing, or what \
kept it from becoming more).

CRITICAL — verbatim quotes:
- For each past relationship and each vignette choice, return verbatim quote \
fields holding 20-50 word DIRECT SLICES from the user's actual messages. Do \
NOT paraphrase quotes. Keep their punctuation, casing, typos. The verbatim \
slice is how the artifact captures register and voice — paraphrasing strips \
the signal.
- If a field has no verbatim source, set the quote to null.

Return strict JSON matching this schema:
{
  "past_pulls": [
    {
      "description": "~30 word paraphrase of who the person was (relationship type, era, context)",
      "what_brought_together": "~30 word paraphrase of the initial pull / what hooked them in",
      "what_broke_apart": "~30 word paraphrase of what ended it OR what creates the most friction OR what kept it from becoming more. null if explicitly ongoing with no friction.",
      "brought_quote": "20-50 word verbatim slice on the initial pull, or null",
      "broke_quote": "20-50 word verbatim slice on the break / friction, or null"
    },
    ...
  ],
  "icks": ["short phrase", "short phrase", ...],
  "vignette_choices": [
    {
      "pair_index": 0,
      "picked": "a" | "b",
      "tipped_reason": "~25 word paraphrase of what tipped them, or null",
      "tipped_quote": "20-50 word verbatim slice, or null"
    },
    ...
  ],
  "pull_pattern": "~50-70 word synthesized narrative on the POSITIVE side ONLY — what kind of person actually pulls them in, in what register. Be specific.",
  "break_pattern": "~30-60 word synthesized narrative on the NEGATIVE side — the pattern of friction that tends to break things. e.g. 'partners eventually emotionally withdraw' or 'mismatched pace — they wanted more, you wanted less'. Use null if no clear break pattern emerged.",
  "pull_pattern_quote": "20-50 word verbatim slice from the conversation that most strongly conveys the pattern, or null",
  "partner_traits": ["trait_tag_1", "trait_tag_2", ...]   // 3-5 ranked short tags
}

Rules:
- past_pulls and vignette_choices come from the actual conversation — do not \
invent.
- partner_traits are short lowercase tags (e.g. ["creative_drive", "quiet_presence", \
"intellectual_edge"]). Rank by salience to the user's pattern.
- pull_pattern + break_pattern are YOUR synthesis. Be specific and grounded. \
Don't be generic ("they like creative people").
- The break_pattern should name the actual repeating friction across \
relationships. If only ONE relationship was discussed and a clear friction \
emerged, name that friction. If no friction emerged, use null.
- Use null/empty for fields with insufficient signal. Don't hallucinate.
"""


# Stage 4 readback — deterministic results card formatter. No LLM call: what
# the user sees is exactly what the extractor produced, formatted as a
# verifiable profile. The LLM-synthesized fields (pull_pattern, break_pattern,
# partner_traits) come straight from the artifact; the demographics come from
# the engine's collected dealbreaker_answers state.


_GENDER_PRETTY = {
    "male": "men",
    "female": "women",
    "nonbinary": "non-binary folks",
}

_INTENT_PRETTY = {
    "long_term": "long-term / serious",
    "casual": "casual",
    "open": "open either way",
}

_KIDS_PRETTY = {
    "yes": "wants kids",
    "no": "doesn't want kids",
    "open": "open either way",
}

_SMOKE_PRETTY = {
    "none": "no smoking",
    "sometimes": "sometimes okay",
    "yes": "fine either way",
}

_DRINK_PRETTY = {
    "none": "no drinking",
    "social": "social drinking",
    "heavy": "heavy drinking okay",
}

_CANNABIS_PRETTY = {
    "none": "no cannabis",
    "sometimes": "sometimes okay",
    "yes": "fine either way",
}

_VISUAL_IMPORTANCE_PRETTY = {
    "high": "matters a lot",
    "secondary": "secondary to how they make me feel",
    "low": "barely registers — mind/presence matters more",
    "open": "depends on the person",
}


def _format_list(items: list[str], conjunction: str = "and") -> str:
    """Pretty-print a list: ['a'] → 'a'; ['a','b'] → 'a and b'; ['a','b','c'] → 'a, b, and c'."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"


def format_readback(
    artifact: dict,
    dealbreakers: dict,
    celebrity_choices: list[dict] | None = None,
) -> str:
    """Build the structured results card the user sees + confirms.

    `artifact` is the extracted IdealType dict (pull_pattern, break_pattern,
    partner_traits, past_pulls, icks). `dealbreakers` is the Stage 0
    answers dict carrying gender_preference, age range, religion_preference,
    smoking/drinking/cannabis tolerances, kids stance, intent, ethnicity pref,
    visual_importance. `celebrity_choices` is the Stage 0.5 forced-choice
    results (list of {pair_index, axis, a, b, picked, user_reply}).
    """
    sections: list[str] = []
    sections.append("Okay — here's your ideal-type profile:\n")

    # --- WHAT PULLS YOU IN ---
    if artifact.get("pull_pattern"):
        sections.append("— WHAT PULLS YOU IN —")
        sections.append(artifact["pull_pattern"])
        if artifact.get("partner_traits"):
            sections.append("\nYou're drawn to:")
            for trait in artifact["partner_traits"][:5]:
                pretty = trait.replace("_", " ")
                sections.append(f"  • {pretty}")
        sections.append("")

    # --- WHAT TENDS TO BREAK IT ---
    if artifact.get("break_pattern"):
        sections.append("— WHAT TENDS TO BREAK IT —")
        sections.append(artifact["break_pattern"])
        # Surface a verbatim broke_quote if there's one with substance.
        for p in artifact.get("past_pulls") or []:
            bq = p.get("broke_quote") if isinstance(p, dict) else None
            if bq and len(bq) > 15:
                sections.append(f"\"{bq}\"")
                break
        sections.append("")

    # --- HARD NOS ---
    icks = [i for i in (artifact.get("icks") or []) if i]
    if icks:
        sections.append("— HARD NOS —")
        for ick in icks:
            sections.append(f"  • {ick}")
        sections.append("")

    # --- THE FRAME (demographics from dealbreakers) ---
    frame_lines = _format_frame(dealbreakers)
    if frame_lines:
        sections.append("— THE FRAME —")
        sections.extend(frame_lines)
        sections.append("")

    # --- VISUAL REFERENCES (celebrity picks) ---
    vis_lines = _format_celebrity_lines(celebrity_choices or [])
    if vis_lines:
        sections.append("— VISUAL PULLS —")
        sections.extend(vis_lines)
        sections.append("")

    sections.append(
        "Does this read true? Say yes to lock it in, or tell me what's off "
        "and I'll redo it."
    )

    return "\n".join(sections)


def _format_celebrity_lines(choices: list[dict]) -> list[str]:
    """One bullet per pair: who they picked, with the descriptor."""
    out: list[str] = []
    for c in choices:
        picked = c.get("picked")
        if picked not in {"a", "b"}:
            # Neither / no pick — surface that fact briefly.
            a_name = (c.get("a") or {}).get("name") or "?"
            b_name = (c.get("b") or {}).get("name") or "?"
            out.append(f"  • {a_name} vs. {b_name}: no clear pull")
            continue
        chosen = c.get(picked) or {}
        rejected_key = "b" if picked == "a" else "a"
        rejected = c.get(rejected_key) or {}
        chosen_name = chosen.get("name") or "?"
        chosen_desc = chosen.get("descriptor") or ""
        rejected_name = rejected.get("name") or "?"
        line = f"  • {chosen_name} over {rejected_name}"
        if chosen_desc:
            line += f" — {chosen_desc}"
        out.append(line)
    return out


def _format_frame(d: dict) -> list[str]:
    """Pretty-format the demographic dealbreaker answers."""
    out: list[str] = []

    # Gender + age in one line.
    gender = [_GENDER_PRETTY.get(g, g) for g in (d.get("gender_preference") or [])]
    age_min, age_max = d.get("age_min"), d.get("age_max")
    if gender or (age_min is not None and age_max is not None):
        bits: list[str] = []
        if gender:
            bits.append(f"Looking for: {_format_list(gender, conjunction='or')}")
        if age_min is not None and age_max is not None:
            bits.append(f"ages {age_min}-{age_max}")
        out.append("  • " + ", ".join(bits))

    # Ethnicity
    ethnicity = d.get("ethnicity_preference")
    if ethnicity:
        items = [e for e in ethnicity if e]
        if items == ["any"]:
            out.append("  • Ethnicity: open to all")
        elif items:
            out.append(f"  • Ethnicity preference: {_format_list(items)}")

    # Religion
    religion = d.get("religion_preference")
    if religion:
        items = [r for r in religion if r]
        if items == ["any"]:
            out.append("  • Religion: open to any")
        elif items == ["same_as_mine"]:
            out.append("  • Religion: same as mine")
        elif items:
            out.append(f"  • Religion preference: {_format_list(items)}")

    # Substances on one line.
    sub_bits = []
    if d.get("partner_smokes_max") in _SMOKE_PRETTY:
        sub_bits.append(_SMOKE_PRETTY[d["partner_smokes_max"]])
    if d.get("partner_drinks_max") in _DRINK_PRETTY:
        sub_bits.append(_DRINK_PRETTY[d["partner_drinks_max"]])
    if d.get("partner_cannabis_max") in _CANNABIS_PRETTY:
        sub_bits.append(_CANNABIS_PRETTY[d["partner_cannabis_max"]])
    if sub_bits:
        out.append(f"  • Substances: {'; '.join(sub_bits)}")

    # Kids
    if d.get("partner_wants_kids") in _KIDS_PRETTY:
        out.append(f"  • Kids: {_KIDS_PRETTY[d['partner_wants_kids']]}")

    # Intent
    if d.get("relationship_intent") in _INTENT_PRETTY:
        out.append(f"  • Intent: {_INTENT_PRETTY[d['relationship_intent']]}")

    # Visual importance only (the type now lives in celebrity_choices, rendered
    # in its own section).
    if d.get("visual_importance") in _VISUAL_IMPORTANCE_PRETTY:
        out.append(f"  • Looks weight: {_VISUAL_IMPORTANCE_PRETTY[d['visual_importance']]}")

    return out
