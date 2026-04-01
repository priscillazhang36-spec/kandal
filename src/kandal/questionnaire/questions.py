"""Scenario-based question bank for inferring Tier 2 compatibility traits."""

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
        "text": (
            "Your partner had a terrible day. "
            "How do you most naturally try to make it better?"
        ),
        "options": [
            {
                "text": "I'd tell them exactly what I admire about how they handled it.",
                "signals": {"love_giving:words_of_affirmation": 1},
            },
            {
                "text": "I'd clear my schedule and just be fully present with them.",
                "signals": {"love_giving:quality_time": 1},
            },
            {
                "text": (
                    "I'd handle something on their to-do list "
                    "— cook dinner, run an errand."
                ),
                "signals": {"love_giving:acts_of_service": 1},
            },
            {
                "text": "I'd give them a long hug or a back rub without saying much.",
                "signals": {"love_giving:physical_touch": 1},
            },
        ],
    },
    {
        "id": 3,
        "text": (
            "You and your partner disagree about something "
            "that matters to both of you. What do you do?"
        ),
        "options": [
            {
                "text": (
                    "Sit down right now and talk it through, "
                    "even if it's uncomfortable."
                ),
                "signals": {"conflict:talk_immediately": 1, "attachment:secure": 1},
            },
            {
                "text": (
                    "Try to find a solution that works for both of us, "
                    "even if it takes a while."
                ),
                "signals": {"conflict:collaborative": 1, "attachment:secure": 1},
            },
            {
                "text": (
                    "I need to go for a walk first. "
                    "I can't think straight when emotions are high."
                ),
                "signals": {"conflict:need_space": 1, "attachment:avoidant": 1},
            },
            {
                "text": "I tend to go quiet and hope it resolves itself.",
                "signals": {"conflict:avoidant": 1, "attachment:disorganized": 1},
            },
        ],
    },
    {
        "id": 4,
        "text": (
            "It's your birthday. Which of these from a partner "
            "would mean the most to you?"
        ),
        "options": [
            {
                "text": "A heartfelt letter telling me what I mean to them.",
                "signals": {"love_receiving:words_of_affirmation": 1},
            },
            {
                "text": "A full day planned together doing my favorite things.",
                "signals": {"love_receiving:quality_time": 1},
            },
            {
                "text": (
                    "A gift that shows they've been paying attention "
                    "to something I mentioned months ago."
                ),
                "signals": {"love_receiving:gifts": 1},
            },
            {
                "text": "Honestly, just being held and feeling close.",
                "signals": {"love_receiving:physical_touch": 1},
            },
        ],
    },
    {
        "id": 5,
        "text": (
            "You've been seeing someone for a few weeks. "
            "They don't text you for a full day. What goes through your head?"
        ),
        "options": [
            {
                "text": "They're probably just busy. I'll hear from them.",
                "signals": {"attachment:secure": 1},
            },
            {
                "text": (
                    "I start replaying our last conversation "
                    "wondering if I said something wrong."
                ),
                "signals": {"attachment:anxious": 1},
            },
            {
                "text": (
                    "I honestly might not notice for a while "
                    "— I get absorbed in my own stuff."
                ),
                "signals": {"attachment:avoidant": 1},
            },
            {
                "text": (
                    "Part of me is relieved, part of me is panicking. "
                    "I don't know which feeling to trust."
                ),
                "signals": {"attachment:disorganized": 1},
            },
        ],
    },
    {
        "id": 6,
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
        "id": 7,
        "text": (
            "Your partner seems distant for a few days "
            "but says 'I'm fine.' How do you handle it?"
        ),
        "options": [
            {
                "text": (
                    "I give them space but let them know "
                    "I'm here when they're ready."
                ),
                "signals": {"attachment:secure": 1, "conflict:collaborative": 1},
            },
            {
                "text": "I keep checking in. The uncertainty eats at me.",
                "signals": {"attachment:anxious": 1, "conflict:talk_immediately": 1},
            },
            {
                "text": "I match their energy. If they want distance, fine by me.",
                "signals": {"attachment:avoidant": 1, "conflict:need_space": 1},
            },
            {
                "text": (
                    "I oscillate — one minute I want to confront them, "
                    "the next I want to disappear."
                ),
                "signals": {"attachment:disorganized": 1, "conflict:avoidant": 1},
            },
        ],
    },
    {
        "id": 8,
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
        "id": 9,
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
    {
        "id": 10,
        "text": (
            "How comfortable are you being emotionally vulnerable "
            "with a partner?"
        ),
        "options": [
            {
                "text": (
                    "Very — I think openness is what makes relationships work."
                ),
                "signals": {"attachment:secure": 1, "conflict:talk_immediately": 1},
            },
            {
                "text": "I want to be, but I worry about being 'too much.'",
                "signals": {"attachment:anxious": 1, "conflict:collaborative": 1},
            },
            {
                "text": "I find it hard. I process things internally.",
                "signals": {"attachment:avoidant": 1, "conflict:need_space": 1},
            },
            {
                "text": (
                    "It depends on the day. "
                    "Sometimes I overshare, sometimes I shut down."
                ),
                "signals": {"attachment:disorganized": 1, "conflict:avoidant": 1},
            },
        ],
    },
]
