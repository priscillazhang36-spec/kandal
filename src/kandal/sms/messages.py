"""Conversational message templates for SMS onboarding."""

import random

WELCOME = (
    "Hey! Welcome to Kandal. "
    "We just sent you a 6-digit code. Text it back to verify your number."
)

CODE_WRONG = "That code didn't match. Try again? ({attempts}/3 attempts)"

CODE_EXPIRED = "Too many attempts. Text START to begin again."

CODE_TIMED_OUT = "That code expired. Text START to get a new one."

QUESTION_INTRO = (
    "Nice, you're in! I'm going to ask you 10 quick questions "
    "about how you show up in relationships. No wrong answers "
    "-- just go with your gut.\n\nReady? Here's the first one:"
)

ANSWER_NOT_UNDERSTOOD = "Hmm, I didn't catch that. Just reply with A, B, C, or D."

_TRANSITIONS = [
    "Got it.",
    "Noted.",
    "Interesting.",
    "Okay, next one.",
    "Good to know.",
    "",
]

BASICS_INTRO = "Almost done! Just need a few basics.\n\nWhat's your first name?"

BASICS_AGE = "And how old are you?"

BASICS_AGE_INVALID = "I need a number between 18 and 99."

BASICS_GENDER = "What's your gender? (e.g. male, female, nonbinary)"

BASICS_GENDER_INVALID = "I didn't catch that. Just type: male, female, or nonbinary."

BASICS_GENDER_PREFERENCE = (
    "And who are you interested in? (e.g. male, female, or both)"
)

BASICS_GENDER_PREFERENCE_INVALID = (
    "Just type: male, female, nonbinary, or a combo like 'male and female'."
)

BASICS_CITY = "Last one -- what city are you in?"

ONBOARDING_COMPLETE = (
    "You're all set! Your profile is live. "
    "We'll text you when we find someone worth meeting."
)

FINALIZE_FAILED = (
    "Hmm, something went wrong saving your profile. "
    "Don't worry — your answers are safe. Text RETRY and we'll try again."
)

ALREADY_COMPLETE = "You're already set up! We'll text you when we find a match."

SESSION_EXPIRED = "Your session expired. Text START to begin again."

RESTART_HINT = "Text START to begin."


def transition_phrase() -> str:
    return random.choice(_TRANSITIONS)


def format_question(question: dict) -> str:
    """Return the full question as a single string."""
    letters = ["A", "B", "C", "D"]
    lines = [question["text"], ""]
    for i, opt in enumerate(question["options"]):
        lines.append(f"{letters[i]}) {opt['text']}")
    return "\n".join(lines)
