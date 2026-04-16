"""Long-term compatibility scenario MCQs. These are secondary signals —
the LLM judge uses them to sanity-check pairs flagged by spark matching,
not as primary ranking criteria. Kept intentionally small (4 questions)
since the freeform conversation + basics MCQs + spark MCQs already do
most of the work.

Coverage:
- Q1: partner cancels → attachment + conflict (covers all 4 attachment styles)
- Q2: after-argument repair → love_giving + conflict
- Q3: felt truly loved → love_receiving
- Q4: relationship history → history
"""

QUESTIONS = [
    {
        "id": 1,
        "text": (
            "Your partner cancels dinner plans at the last minute "
            "because they're drained from work. What's your first instinct?"
        ),
        "options": [
            {
                "text": "No worries — I'll bring food to yours and we can just hang.",
                "signals": {"attachment:secure": 1, "conflict:collaborative": 1},
            },
            {
                "text": (
                    "I'd feel a bit stung but say it's fine, "
                    "then quietly wonder if they actually wanted to see me."
                ),
                "signals": {"attachment:anxious": 1, "conflict:avoidant": 1},
            },
            {
                "text": "Perfect — I was kind of hoping for a solo night anyway.",
                "signals": {"attachment:avoidant": 1, "conflict:need_space": 1},
            },
            {
                "text": "I'd be upset but not sure whether to say something or let it go.",
                "signals": {"attachment:disorganized": 1, "conflict:avoidant": 1},
            },
        ],
    },
    {
        "id": 2,
        "text": "After an argument is resolved, how do you reconnect?",
        "options": [
            {
                "text": (
                    "I say something like "
                    "'I'm sorry, and here's what I appreciate about us.'"
                ),
                "signals": {
                    "love_giving:words_of_affirmation": 1,
                    "conflict:talk_immediately": 1,
                },
            },
            {
                "text": (
                    "I suggest doing something together "
                    "— a meal, a walk, anything shared."
                ),
                "signals": {
                    "love_giving:quality_time": 1,
                    "conflict:collaborative": 1,
                },
            },
            {
                "text": "I do something thoughtful for them without being asked.",
                "signals": {
                    "love_giving:acts_of_service": 1,
                    "conflict:collaborative": 1,
                },
            },
            {
                "text": (
                    "I pick up a small thing I know they'd like "
                    "— flowers, their favorite snack."
                ),
                "signals": {"love_giving:gifts": 1},
            },
        ],
    },
    {
        "id": 3,
        "text": "Think about a time you felt truly loved. What was happening?",
        "options": [
            {
                "text": (
                    "Someone told me, in specific terms, why I mattered to them."
                ),
                "signals": {"love_receiving:words_of_affirmation": 1},
            },
            {
                "text": "Someone dropped everything to spend unhurried time with me.",
                "signals": {"love_receiving:quality_time": 1},
            },
            {
                "text": (
                    "Someone did something for me that made my life easier "
                    "without being asked."
                ),
                "signals": {"love_receiving:acts_of_service": 1},
            },
            {
                "text": (
                    "Physical closeness "
                    "— a hand on my back, falling asleep together."
                ),
                "signals": {"love_receiving:physical_touch": 1},
            },
        ],
    },
    {
        "id": 4,
        "text": "Which best describes your relationship history?",
        "options": [
            {
                "text": "Mostly long-term relationships (1+ years).",
                "signals": {"history:long_term": 1},
            },
            {
                "text": (
                    "A mix of shorter things "
                    "— I date but it doesn't always stick."
                ),
                "signals": {"history:mostly_casual": 1},
            },
            {
                "text": "I'm coming out of something serious.",
                "signals": {"history:recently_out_of_ltr": 1},
            },
            {
                "text": (
                    "I haven't been in many relationships "
                    "— this is relatively new for me."
                ),
                "signals": {"history:limited_experience": 1},
            },
        ],
    },
]
