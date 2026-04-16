"""System prompts and extraction schemas for adaptive profiling."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

_SOUL_PATH = Path(__file__).parent / "soul.md"
SOUL = _SOUL_PATH.read_text(encoding="utf-8")

if TYPE_CHECKING:
    from kandal.profiling.pool_stats import PoolStats
    from kandal.questionnaire.inference import InferredTraits

# Valid values for each trait dimension (must match questionnaire/inference.py contracts)
VALID_ATTACHMENT_STYLES = ["secure", "anxious", "avoidant", "disorganized"]
VALID_CONFLICT_STYLES = ["talk_immediately", "need_space", "avoidant", "collaborative"]
VALID_LOVE_LANGUAGES = [
    "words_of_affirmation",
    "quality_time",
    "physical_touch",
    "acts_of_service",
    "gifts",
]
VALID_RELATIONSHIP_HISTORIES = [
    "long_term",
    "mostly_casual",
    "recently_out_of_ltr",
    "limited_experience",
]
VALID_GENDERS = ["male", "female", "nonbinary"]

# Spark-focused pillars — these are what the freeform conversation collects.
# Long-term compatibility signals (attachment, love languages, conflict style,
# history) and logistics (birthday, gender preference, kids, etc.) are collected
# *after* the conversation via deterministic MCQ loops — not chased here.
TRAIT_DIMENSIONS = [
    "spark_aliveness",      # current obsession + what they'd talk about for hours
    "spark_taste",          # 3 specific recs + favorite places in their city
    "spark_attraction",     # past attraction + contradiction hook
    "emotional_dynamics",   # how it feels to be loved by them + what they need back
    "partner_vibe",         # the kind of person they're looking for
]

RUNTIME_CONTEXT_TEMPLATE = """\

---

# Session context (this conversation)

You're aiming for roughly a 20-minute conversation (~{target} exchanges). You've \
done {questions_asked} so far. This is a soft target, not a hard limit — keep \
going if you need more signal, wrap sooner if you've already got it.

**Pacing signal: {pacing_label}** — {pacing_guidance}

If the user asks how much longer, give them an honest read using this signal — \
e.g. "we're maybe halfway" or "just a few more and I think I've got you." Don't \
announce that you're "wrapping up" or about to end — the system handles that.

{phase_hint}

Current coverage of what you're trying to learn (0 = haven't touched it, 1 = crystal clear):
{coverage_summary}

Focus on the least-covered area when nothing else is pulling you. But don't force it — \
if the conversation is going somewhere alive, follow it and circle back later.

**When to switch to scenario-based multiple choice (USE THIS AGGRESSIVELY):**

The abstract pillars you're collecting — *emotional dynamics* (how it feels to \
be loved by them, what they need to feel loved), *partner vibe* (what kind of \
person they want) — are hard to answer cold. If the user signals they can't \
articulate something, pivot to MCQ on the very next message:
  - "idk" / "I don't know" / "not sure" / "hard to say" / "hmm"
  - One-to-five word answers like "I guess so" / "yeah maybe" / "kinda"
  - Generic non-answers like "depends" / "it varies" / "all of them"
  - They literally ask you for examples or options
  - They repeat your question back at you

Format: 3-4 concrete options labeled A/B/C/D, plus an explicit "or tell me in \
your own words" out. People who can't answer abstractly can almost always pick \
from concrete scenarios. Reach for this PROACTIVELY on the abstract pillars — \
don't wait for them to get stuck twice. One short stuck-signal is enough.

**What NOT to ask about in freeform:** attachment style, love languages, \
conflict style, relationship history, birthday, location, gender preference, \
age range, kids, religion, substances. All of that is collected via structured \
MCQs after this conversation — if you ask about it here you're duplicating work \
and making the user fill out a form twice.

If even multiple-choice doesn't land, drop it and try a different angle later. \
Nobody likes feeling cornered.

If they only answered part of what you asked, fold the missed part into your next \
question naturally — don't call it out.
{pool_section}\
"""

POOL_AWARE_SECTION = """
Context about the dating pool for this person:
- {total_eligible} people match their basic criteria
- Most common attachment styles in pool: {dominant_attachment}
- Underrepresented traits that could help differentiate: {differentiators}
Ask at least one question that helps reveal what makes this person unique \
relative to their pool.
"""

EXTRACTION_SYSTEM_PROMPT = """\
You are a personality analyst. Read the following matchmaking conversation and \
extract what this person is actually like — the spark signals a first date would \
turn on. Also write a concise ~80 word "matchmaker's notes" narrative — bullet \
style, facts only.

CRITICAL: Only extract what the person EXPLICITLY said or clearly demonstrated. \
Do NOT infer, assume, or fill in gaps. If they never mentioned cultural \
preferences, use null — do NOT assume "open to everyone." The narrative should \
only contain information the person actually shared — no assumptions, no \
extrapolations, no "they seem like" guesses.

The narrative should capture: current obsessions, taste specifics, how they \
show up emotionally, what kind of person they're drawn to, and any distinctive \
details they mentioned. No filler, no literary commentary.

You must return valid JSON matching this exact schema:
{
  "name": their first name if they mentioned it, or null,
  "gender": one of ["male", "female", "nonbinary"] if clearly stated or obvious from context, or null,
  "current_city": the city they currently live in if mentioned, or null. This is different from birth_city.,
  "birth_date": "YYYY-MM-DD" ONLY if YEAR + MONTH + DAY were all explicitly shared. Usually null (birthday is collected via basics MCQ later).,
  "birth_time_approx": "HH:00-HH:00" 3hr window if shared, else null (usually null).,
  "birth_city": city name if shared, else null (usually null).,
  "gender_preference": list like ["male"] or ["female"] or ["male","female","nonbinary"] — ONLY if they explicitly stated who they're attracted to. Use null if never mentioned. Usually null (collected via basics MCQ later).,
  "cultural_preferences": list of any cultural/racial preferences they EXPLICITLY mentioned, or null if never discussed. Do NOT default to "open to everyone.",
  "emotional_giving": "~40 word description of how this person makes partners feel — their emotional strengths, how they show care, what being loved by them is like. Distill from what they said. Use null if not enough signal.",
  "emotional_needs": "~40 word description of what this person needs to feel from a partner to be their best self. Distill from what they explicitly said they need. Use null if not enough signal.",
  "taste_fingerprint": "~30 word snapshot of their taste — the specific things they'd recommend (restaurants, bands, books, shows, YouTube channels, whatever). Specifics only, no categories. Use null if they didn't name specific things.",
  "current_obsession": "~25 word note on what's firing in them right now — a rabbit hole, a project, a phase. What's taking up their brain. Use null if they didn't describe one.",
  "two_hour_topic": "~20 word note on what they could talk about for hours — a domain, a weird niche interest, a debate they'd pick up. Use null if not shared.",
  "contradiction_hook": "the 'I'm a [ ] who also [ ]' surprise — the thing a stranger wouldn't guess from their surface. ~20 words. Use null if nothing distinctive emerged.",
  "past_attraction": "~30 word note on what actually pulled them in last time — from a specific past relationship or crush, not a checklist. Use null if they didn't share.",
  "favorite_places": "list of 1-5 objects like [{\\"name\\": \\"...\\", \\"type\\": \\"cafe|restaurant|park|bar|bookstore|other\\", \\"neighborhood\\": \\"...\\" (optional), \\"note\\": \\"...\\" (optional, why they love it)}]. Use null if they didn't name specific spots.",
  "interests": list of hobby/interest tags based on what they EXPLICITLY mentioned — e.g. ["hiking", "cooking", "reading", "live_music", "travel", "gaming", "fitness"]. Short lowercase tags. Use null if none mentioned.,
  "personality": list of personality tags describing THIS PERSON based on what they DEMONSTRATED in conversation — e.g. ["introverted", "adventurous", "creative", "analytical", "empathetic", "spontaneous", "ambitious"]. Use null if not enough signal.,
  "partner_personality": list of personality tags describing what this person WANTS IN A PARTNER — e.g. ["curious", "independent", "grounded", "playful"]. Use null if not enough signal.,
  "values": list of value tags that THIS PERSON holds — e.g. ["family", "independence", "honesty", "ambition", "humor", "loyalty", "growth"]. Use null if not enough signal.,
  "partner_values": list of value tags this person WANTS THEIR PARTNER TO HAVE. Use null if not enough signal.,
  "lifestyle": list of lifestyle tags based on what they described — e.g. ["early_bird", "night_owl", "homebody", "social", "active", "city_person", "outdoorsy"]. Use null if not enough signal.,
  "narrative": "~80 word concise matchmaker's notes"
}
"""

COVERAGE_SYSTEM_PROMPT = """\
You are analyzing a matchmaking conversation for spark-signal coverage. Based \
on the conversation so far, estimate confidence (0.0 to 1.0) for each dimension.

Return valid JSON:
{
  "spark_aliveness": <float 0-1>,
  "spark_taste": <float 0-1>,
  "spark_attraction": <float 0-1>,
  "emotional_dynamics": <float 0-1>,
  "partner_vibe": <float 0-1>
}

0.0 = no signal at all, 0.5 = some hints, 0.7 = fairly confident, 1.0 = very clear.

spark_aliveness = whether we know what's currently firing in them — a current \
obsession, a rabbit hole, a project, a phase, or a topic they could talk about \
for hours. Generic hobby mentions without real energy count as ~0.3.
spark_taste = whether we have SPECIFIC recommendations they'd make (actual \
restaurants, bands, books, shows, creators by name) AND/OR favorite places in \
their city by name. Categories alone ("music", "restaurants") = 0.2 max. \
Specifics + favorite places = 1.0.
spark_attraction = whether we understand what pulled them in before — either \
from a past person they cared about (what actually got them, not a checklist) \
or the contradiction that makes them them ("I'm a X who also Y"). Either one \
strong = 0.7; both = 1.0.
emotional_dynamics = whether we understand how this person makes partners feel \
AND what they need to feel from a partner. Both sides needed for high confidence.
partner_vibe = whether we know the kind of *person* they're looking for — \
personality, values, the feeling they want with someone. "Someone grounded who \
can match my energy" = good signal; silence or "I don't know" = low.
"""

SUMMARY_SYSTEM_PROMPT = """\
You're reading back your notes to someone whose dating alter ego you're building. \
Write a quick summary of what you learned about them so they can confirm it's right.

Tone: casual, warm — like a friend saying "ok so here's what I've got on you."

CRITICAL — DO NOT HALLUCINATE:
- Only include things the person ACTUALLY SAID or that are listed in the \
extracted traits below. Do NOT add information that wasn't discussed.
- If a field is null, missing, or not listed below, do NOT mention it and do NOT \
make assumptions about it. If cultural_preferences is null, do NOT say "open to all."
- NEVER state an age, birth year, occupation, location, ethnicity, or other \
demographic unless it is explicitly listed in the extracted traits.
- If you find yourself writing a number, check it came from the traits. If it \
didn't, delete it.
- Better to omit a section than to invent content for it.

Include (only if present in the extracted traits):
- What's firing in them right now — their current obsession or two-hour topic
- Their taste fingerprint — the specific things they'd recommend
- Favorite places they named in their city
- The contradiction hook — what makes them them
- How they show up for someone they love (emotional_giving)
- What they need to feel from a partner (emotional_needs)
- What pulled them in last time (past_attraction) — only if they shared this
- The kind of person they're looking for (partner_personality / partner_values)
- Any standout specifics they mentioned

Keep it under 250 words. End with:
"Does this sound like you? Say 'yes' to lock it in, or tell me what I got wrong."
"""


_DIMENSION_PROMPTS = {
    "spark_aliveness": (
        "What's firing in them right now — a current obsession, a rabbit hole, "
        "a project, a phase. Or a topic they could talk about for two hours "
        "straight. The aliveness signal — what's taking up their brain this month."
    ),
    "spark_taste": (
        "Specific things they'd recommend — restaurants, bands, books, shows, "
        "YouTube channels, anything. Push for actual names, not categories "
        "('music' is nothing; 'Fleet Foxes' is a person). Also: 3 favorite "
        "places in their city — a cafe, a park, a spot they actually go."
    ),
    "spark_attraction": (
        "What actually pulled them in last time — from a specific past person "
        "they cared about, not a checklist. The real moment. AND/OR: the "
        "contradiction that makes them them — 'I'm a [ ] who also [ ]' — the "
        "thing a stranger wouldn't guess. Frame gently on past attraction; "
        "don't push if they don't want to go there."
    ),
    "emotional_dynamics": (
        "How they make a partner FEEL when things are good (the emotional "
        "texture of being loved by them), and what they need to feel from a "
        "partner to be their best self. Both sides."
    ),
    "partner_vibe": (
        "The kind of person they're looking for — personality, values, the "
        "feeling they want. Not a checklist. 'Someone who...' Phrase like a "
        "friend asking, not a form. Pivot to MCQ if they get stuck."
    ),
}


def build_conversation_prompt(
    questions_asked: int,
    max_questions: int,
    coverage: dict[str, float],
    pool_stats: PoolStats | None = None,
    memory_block: str = "",
    missing_essentials: list[str] | None = None,
) -> str:
    coverage_lines = []
    for dim in TRAIT_DIMENSIONS:
        conf = coverage.get(dim, 0.0)
        bar = "#" * int(conf * 10) + "." * (10 - int(conf * 10))
        coverage_lines.append(f"  {dim}: [{bar}] {conf:.1f}")
    coverage_summary = "\n".join(coverage_lines)

    # Tell the agent which phase it should be in based on progress
    ratio = questions_asked / max_questions if max_questions > 0 else 0
    if ratio < 0.35:
        phase_hint = (
            "You are in PHASE 1 (aliveness + taste). Get them showing you who "
            "they are — what they're currently obsessed with, what they'd "
            "recommend, their favorite places in their city. Specifics, not "
            "categories.\n\n"
            "**Don't milk small talk.** Warmth is a tone, not a length. The "
            "user's first answer is a BRIDGE, not a thread to unravel. Rules:\n"
            "  - ONE clarifying follow-up max per topic, then pivot to a real "
            "pillar. If they say 'kitties,' you get one light beat ('cat person "
            "or admiring from afar?'), then you move on — don't ladder into "
            "'do you have one → admiring — dedication → so what made you start "
            "dating.' That's four turns burned on nothing.\n"
            "  - If their answer is already pillar-signal (a current obsession, "
            "a specific recommendation, a project) — chase THAT, don't detour.\n"
            "  - Keep it curious and fun in tone, but move. You have ~5 turns "
            "in phase 1 total; don't spend them all on one warm-up topic.\n\n"
            "Do NOT ask about birthdays, gender preference, or relationship "
            "logistics yet — those come later."
        )
    elif ratio < 0.75:
        phase_hint = (
            "You are in PHASE 2 (emotional texture + attraction). Go into how "
            "it feels to be loved by them and what they need to feel from a "
            "partner. If it's natural, ask what pulled them in before (past "
            "attraction) — gently, don't push. Look for the contradiction hook "
            "('I'm a X who also Y'). Use what they told you in phase 1 as bridges."
        )
    else:
        phase_hint = (
            "You are in PHASE 3 (partner vibe + anything still missing). Focus "
            "on what kind of person they're looking for — personality, values, "
            "the feeling. Phrase like a friend, not a form. Circle back to any "
            "spark pillar that's still thin. "
            "**Do NOT ask about birthday, location, age range, distance, kids, "
            "relationship structure, religion, substances, attachment style, "
            "conflict style, or love languages** — all of that is collected "
            "separately after the summary via structured MCQs. "
            "If you genuinely have what you need, wrap with one last natural "
            "follow-up. The system takes over from there."
        )

    # Pacing label — coverage-driven, what you'd tell the user if they asked.
    avg_coverage = sum(coverage.values()) / max(len(coverage), 1)
    if questions_asked <= 2:
        pacing_label = "just getting started"
        pacing_guidance = "ease them in, don't go heavy yet."
    elif avg_coverage < 0.4:
        pacing_label = "early — settling in"
        pacing_guidance = "still gathering the basics; you've got time."
    elif avg_coverage < 0.7:
        pacing_label = "midway"
        pacing_guidance = "good rhythm; this is the meat of the conversation."
    elif missing_essentials:
        pacing_label = "closing in — still need a couple things"
        pacing_guidance = (
            "you're nearly there but missing required signal — pivot to what's missing now."
        )
    else:
        pacing_label = "wrapping up soon (internally)"
        pacing_guidance = (
            "you've got most of what you need. Pick up any last loose ends, but don't tell "
            "the user you're wrapping — the system will move to the summary on its own."
        )

    pool_section = ""
    if pool_stats and pool_stats.total_eligible > 0:
        pool_section = POOL_AWARE_SECTION.format(
            total_eligible=pool_stats.total_eligible,
            dominant_attachment=", ".join(pool_stats.dominant_attachment_styles[:3]),
            differentiators=", ".join(pool_stats.differentiating_dimensions[:3])
            or "none identified",
        )

    essentials_block = ""
    if missing_essentials:
        bullets = "\n".join(
            f"  - **{d}**: {_DIMENSION_PROMPTS.get(d, d)}" for d in missing_essentials
        )
        essentials_block = (
            "\n\n**REQUIRED PILLARS STILL MISSING** — you cannot wrap up until you've "
            "gotten real signal on each of these. Pick whichever fits the conversation "
            "best and pivot toward it now. Don't ask multiple in one message — pull on "
            "one thread, then circle to the next:\n"
            f"{bullets}\n"
        )

    runtime = RUNTIME_CONTEXT_TEMPLATE.format(
        target=max_questions,
        questions_asked=questions_asked,
        coverage_summary=coverage_summary,
        pool_section=pool_section,
        phase_hint=phase_hint,
        pacing_label=pacing_label,
        pacing_guidance=pacing_guidance,
    )
    return SOUL + memory_block + runtime + essentials_block


CHAT_RUNTIME_TEMPLATE = """\

---

# Session context

This is an ongoing conversation with someone you already know. There is no \
question budget, no phase, no coverage to fill. You're just talking — like a \
friend they texted because something is on their mind.

Listen first. Don't pivot to matchmaking unless they bring it up or it's \
genuinely the right moment. If they share something hard, sit with it before \
you respond. If they're venting, don't fix — ask the question that helps them \
see it more clearly.

If something from your memory of them is relevant, weave it in naturally. Don't \
recite the file. Don't say "I remember you said..." — just talk like someone who \
remembers.
"""


def build_chat_prompt(memory_block: str = "") -> str:
    """System prompt for ongoing post-onboarding Kandal chat."""
    return SOUL + memory_block + CHAT_RUNTIME_TEMPLATE


def build_summary_prompt(
    traits: InferredTraits,
    narrative: str,
    low_conf: set[str] | None = None,
) -> str:
    """Format extracted traits into a prompt for the summary LLM call.

    Fields named in `low_conf` are omitted entirely so the summary doesn't
    state defaulted values as facts.
    """
    low_conf = low_conf or set()
    parts = ["Extracted traits (only mention what's listed below — do NOT invent anything else):\n"]
    if traits.current_obsession:
        parts.append(f"- Current obsession: {traits.current_obsession}\n")
    if traits.two_hour_topic:
        parts.append(f"- Could talk for hours about: {traits.two_hour_topic}\n")
    if traits.taste_fingerprint:
        parts.append(f"- Taste fingerprint: {traits.taste_fingerprint}\n")
    if traits.favorite_places:
        place_strs = []
        for p in traits.favorite_places[:5]:
            if isinstance(p, dict):
                name = p.get("name") or ""
                ptype = p.get("type") or ""
                bit = f"{name} ({ptype})" if ptype else name
                if bit:
                    place_strs.append(bit)
        if place_strs:
            parts.append(f"- Favorite places: {', '.join(place_strs)}\n")
    if traits.contradiction_hook:
        parts.append(f"- Contradiction hook: {traits.contradiction_hook}\n")
    if traits.past_attraction:
        parts.append(f"- What pulled them in last time: {traits.past_attraction}\n")
    if traits.emotional_giving:
        parts.append(f"- How they show up for a partner: {traits.emotional_giving}\n")
    if traits.emotional_needs:
        parts.append(f"- What they need to feel: {traits.emotional_needs}\n")
    if traits.partner_personality:
        parts.append(f"- Partner personality they want: {', '.join(traits.partner_personality)}\n")
    if traits.partner_values:
        parts.append(f"- Partner values they want: {', '.join(traits.partner_values)}\n")
    if traits.gender_preference:
        parts.append(f"- Attracted to: {', '.join(traits.gender_preference)}\n")
    if traits.cultural_preferences:
        parts.append(f"- Cultural preferences: {', '.join(traits.cultural_preferences)}\n")

    parts.append(f"\nMatchmaker's notes:\n{narrative}")
    return "".join(parts)
