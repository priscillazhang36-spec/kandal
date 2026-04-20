"""20 hand-crafted archetype profiles for the synthetic matching test.

Each entry is a dict with profile_data + prefs_data, linked by a pre-generated
UUID so the driver can insert both rows without a round-trip.

Design intent:
- Mix of genders / ages / orientations so dealbreakers fire realistically
- Mix of attachment / conflict / history so the LLM judge has signal
- A few deliberately high-compatibility pairs and a few train-wreck pairs
  as sanity checks (see comments inline)
- All NYC-ish coords so distance dealbreakers don't zero out the pool
"""

from __future__ import annotations

from uuid import uuid4


def _pair(profile: dict, prefs: dict) -> dict:
    pid = str(uuid4())
    profile["id"] = pid
    prefs["profile_id"] = pid
    return {"profile": profile, "prefs": prefs}


PROFILES: list[dict] = [
    # 1. Maya — anxious-but-working-on-it yoga teacher / writer
    _pair(
        profile={
            "name": "Maya", "age": 29, "gender": "female",
            "location_lat": 40.7282, "location_lng": -73.9942, "city": "NYC",
            "narrative": (
                "I teach vinyasa four mornings a week and write essays nobody asks for in the afternoons. "
                "I love the hour before the city wakes up. I used to confuse intensity for intimacy — I'm "
                "unlearning that. I want someone who doesn't mind that I cry at commercials and also "
                "argues with me about books. I'm anxious but I can tell when I'm spiraling now, which "
                "feels like progress."
            ),
            "emotional_giving": "I notice the small things and name them back. I remember what you said in passing.",
            "emotional_needs": "Reassurance I don't have to earn. Someone who stays on the phone when I'm quiet.",
            "taste_fingerprint": "Clarice Lispector, sour cherries, Rohmer films, a specific kind of slant light",
            "current_obsession": "Learning to bake sourdough without doom-scrolling while it proofs",
            "two_hour_topic": "Why most self-help is repackaged grief",
            "contradiction_hook": "Spiritual but reads evolutionary biology for fun",
            "past_attraction": "A painter who talked like he was narrating a film. Bad for me, hard to forget.",
            "favorite_places": [{"name": "Prospect Park boathouse", "type": "outdoor"}],
        },
        prefs={
            "min_age": 27, "max_age": 36, "max_distance_km": 40,
            "gender_preferences": ["male"], "relationship_types": ["long_term"],
            "interests": ["yoga", "writing", "film", "cooking"],
            "personality": ["empathetic", "creative", "introspective"],
            "partner_personality": ["grounded", "curious", "emotionally literate"],
            "values": ["depth", "growth", "honesty"],
            "partner_values": ["presence", "growth"],
            "communication_style": "deliberate", "lifestyle": ["early_bird", "active"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "anxious",
            "love_language_giving": ["quality_time", "words_of_affirmation", "acts_of_service", "physical_touch", "gifts"],
            "love_language_receiving": ["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"],
            "conflict_style": "talk_immediately", "relationship_history": "long_term",
            "humor_style": "dry", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "craft",
        },
    ),
    # 2. Jordan — extroverted chef, warm but messy feelings
    _pair(
        profile={
            "name": "Jordan", "age": 31, "gender": "male",
            "location_lat": 40.7484, "location_lng": -73.9857, "city": "NYC",
            "narrative": (
                "I run the line at a mid-size Italian place in Midtown. Fifty hours a week on my feet, "
                "then I go home and cook more because I can't help it. I'm loud, I apologize too much, "
                "and I text back eventually. My ex said I love-bomb; I think I just run hot. I want someone "
                "who lets me feed them and doesn't mind that I fall asleep during movies."
            ),
            "emotional_giving": "Food, rides home at 2am, showing up when it's inconvenient.",
            "emotional_needs": "Someone who sees past the volume and tells me to slow down.",
            "taste_fingerprint": "Offal, Fellini, Tom Waits, hand-written menus",
            "current_obsession": "A 40-year-old sourdough starter I'm trying to revive from a friend's fridge",
            "two_hour_topic": "Why every great restaurant is one cook's hurt feelings away from closing",
            "contradiction_hook": "Chef who can barely feed himself on his days off",
            "past_attraction": "A sommelier who didn't flinch when I cried in a walk-in. Haven't met one since.",
            "favorite_places": [{"name": "Estela", "type": "restaurant"}, {"name": "Carroll Gardens bar X", "type": "bar"}],
        },
        prefs={
            "min_age": 26, "max_age": 35, "max_distance_km": 50,
            "gender_preferences": ["female"], "relationship_types": ["long_term"],
            "interests": ["cooking", "music", "film", "wine"],
            "personality": ["extrovert", "empathetic", "creative"],
            "partner_personality": ["patient", "playful", "secure"],
            "values": ["family", "craft", "loyalty"],
            "partner_values": ["presence", "humor"],
            "communication_style": "direct", "lifestyle": ["night_owl", "social"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "anxious",
            "love_language_giving": ["acts_of_service", "physical_touch", "quality_time", "gifts", "words_of_affirmation"],
            "love_language_receiving": ["physical_touch", "words_of_affirmation", "quality_time", "acts_of_service", "gifts"],
            "conflict_style": "talk_immediately", "relationship_history": "long_term",
            "humor_style": "playful", "conversational_texture": "story_mode",
            "energy_pace": "high", "ambition_shape": "craft",
        },
    ),
    # 3. Sage — avoidant software engineer, slow warmth
    _pair(
        profile={
            "name": "Sage", "age": 27, "gender": "nonbinary",
            "location_lat": 40.7055, "location_lng": -73.9437, "city": "NYC",
            "narrative": (
                "I write distributed systems for a living and distributed-systems my feelings on the side. "
                "I need a lot of alone time and I'm bad at explaining why. I don't lie but I do disappear. "
                "I want someone who doesn't take my silence personally and who has their own thing going. "
                "When I let you in you'll know — I just don't announce it."
            ),
            "emotional_giving": "Reliability. I do what I say. I fix things before you notice they broke.",
            "emotional_needs": "Space without apology. Someone who doesn't require constant evidence of love.",
            "taste_fingerprint": "Stanislaw Lem, ambient electronic, climbing gyms, good font choices",
            "current_obsession": "Bouldering a V5 that's been humbling me for a month",
            "two_hour_topic": "Why most code review is actually about power",
            "contradiction_hook": "Writes software for a living, keeps a daily handwritten journal",
            "past_attraction": "Someone who didn't text back for three days and I respected it, which is maybe a red flag about me",
            "favorite_places": [{"name": "Brooklyn Boulders", "type": "gym"}],
        },
        prefs={
            "min_age": 25, "max_age": 35, "max_distance_km": 40,
            "gender_preferences": ["male", "female", "nonbinary"], "relationship_types": ["long_term"],
            "interests": ["coding", "climbing", "reading", "electronic music"],
            "personality": ["introvert", "analytical", "independent"],
            "partner_personality": ["independent", "self-contained", "curious"],
            "values": ["autonomy", "craft", "honesty"],
            "partner_values": ["autonomy", "depth"],
            "communication_style": "reserved", "lifestyle": ["night_owl", "active"],
            "selectivity": "picky", "cultural_preferences": [],
            "attachment_style": "avoidant",
            "love_language_giving": ["acts_of_service", "quality_time", "physical_touch", "words_of_affirmation", "gifts"],
            "love_language_receiving": ["acts_of_service", "quality_time", "physical_touch", "words_of_affirmation", "gifts"],
            "conflict_style": "need_space", "relationship_history": "mostly_casual",
            "humor_style": "dry", "conversational_texture": "deep_dive",
            "energy_pace": "low", "ambition_shape": "craft",
        },
    ),
    # 4. Leo — secure, outdoorsy photographer (designed to pair well with Maya/Priya/Elena)
    _pair(
        profile={
            "name": "Leo", "age": 33, "gender": "male",
            "location_lat": 40.7128, "location_lng": -74.0060, "city": "NYC",
            "narrative": (
                "I shoot for magazines — travel and portraits, mostly. I grew up in a loud warm family and "
                "I think I've been looking for that ever since. I've been in two long relationships and "
                "I'm proud of how they ended. I'm not in a rush and I'm also not going to play it cool. "
                "I cook on Sundays, I hike most weekends, I text good-morning."
            ),
            "emotional_giving": "Presence. I put the phone down. I remember your sister's name.",
            "emotional_needs": "Someone who lets me see them before they're camera-ready.",
            "taste_fingerprint": "Richard Avedon, Patagonia merino, ceviche, fog in mountains",
            "current_obsession": "Film cameras again — specifically a Mamiya 7 I can't afford",
            "two_hour_topic": "What you actually see when you stop composing and just look",
            "contradiction_hook": "Professional observer who talks a lot at dinner",
            "past_attraction": "Someone who cried at my ex's mom's funeral and I realized I was in the wrong relationship",
            "favorite_places": [{"name": "Fort Tryon Park", "type": "outdoor"}, {"name": "Via Carota", "type": "restaurant"}],
        },
        prefs={
            "min_age": 26, "max_age": 36, "max_distance_km": 60,
            "gender_preferences": ["female"], "relationship_types": ["long_term"],
            "interests": ["photography", "hiking", "cooking", "travel"],
            "personality": ["extrovert", "empathetic", "creative", "grounded"],
            "partner_personality": ["emotionally literate", "curious", "warm"],
            "values": ["family", "presence", "craft"],
            "partner_values": ["depth", "honesty"],
            "communication_style": "deliberate", "lifestyle": ["early_bird", "active", "traveler"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["physical_touch", "quality_time", "words_of_affirmation", "acts_of_service", "gifts"],
            "love_language_receiving": ["quality_time", "physical_touch", "words_of_affirmation", "acts_of_service", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "long_term",
            "humor_style": "warm", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "craft",
        },
    ),
    # 5. Priya — anxious designer, recently out of LTR (should match Leo well, probably NOT Tomás)
    _pair(
        profile={
            "name": "Priya", "age": 26, "gender": "female",
            "location_lat": 40.7393, "location_lng": -74.0020, "city": "NYC",
            "narrative": (
                "I design brand systems at an agency I'll probably leave. I got out of a six-year thing "
                "eight months ago — it ended well, but I'm still reassembling. I journal a lot. I call my "
                "mom most days. I can be intense but I'm also funny and self-aware about it. I want someone "
                "patient who likes when someone cares as hard as I do."
            ),
            "emotional_giving": "Gifts that are actually observed. I remember what you said you wanted six months ago.",
            "emotional_needs": "Words. Tell me. Don't make me guess if we're okay.",
            "taste_fingerprint": "Ocean Vuong, Korean skincare, slow films, linen",
            "current_obsession": "Rebuilding my morning routine without my ex's rituals embedded in it",
            "two_hour_topic": "Why most design is just managing someone else's insecurity",
            "contradiction_hook": "Public-facing confidence, journals obsessively in private",
            "past_attraction": "Someone who told me he was proud of me and I realized I'd never heard that",
            "favorite_places": [{"name": "Maman West Village", "type": "cafe"}],
        },
        prefs={
            "min_age": 27, "max_age": 34, "max_distance_km": 40,
            "gender_preferences": ["male"], "relationship_types": ["long_term"],
            "interests": ["design", "reading", "yoga", "travel"],
            "personality": ["empathetic", "creative", "intense"],
            "partner_personality": ["patient", "secure", "emotionally literate"],
            "values": ["growth", "family", "honesty"],
            "partner_values": ["presence", "honesty"],
            "communication_style": "deliberate", "lifestyle": ["early_bird", "homebody"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "anxious",
            "love_language_giving": ["gifts", "words_of_affirmation", "quality_time", "acts_of_service", "physical_touch"],
            "love_language_receiving": ["words_of_affirmation", "quality_time", "physical_touch", "gifts", "acts_of_service"],
            "conflict_style": "collaborative", "relationship_history": "recently_out_of_ltr",
            "humor_style": "self_deprecating", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "craft",
        },
    ),
    # 6. Alex — disorganized indie game dev (hard to match; designed to be rough)
    _pair(
        profile={
            "name": "Alex", "age": 30, "gender": "male",
            "location_lat": 40.6782, "location_lng": -73.9442, "city": "NYC",
            "narrative": (
                "I make a weird little game nobody's bought yet. I've been single for most of my adult life "
                "and I'm not sure if that's because I like it or because I'm avoiding something. I stay up "
                "too late. I'm warm when I'm warm and gone when I'm gone. I don't really know what I'm doing "
                "here — a friend made me sign up."
            ),
            "emotional_giving": "Intensity when I'm present. I'll text you a 900-word thing at 3am.",
            "emotional_needs": "I don't actually know. Probably someone who'd ask.",
            "taste_fingerprint": "Kentucky Route Zero, ambient black metal, cheap diners",
            "current_obsession": "Porting my game to a console that may not approve it",
            "two_hour_topic": "Why procedural generation is almost always a cope",
            "contradiction_hook": "Makes art for a living, can't articulate what he needs",
            "past_attraction": "Nobody recent. Maybe a friend's sister in 2019.",
            "favorite_places": [],
        },
        prefs={
            "min_age": 24, "max_age": 36, "max_distance_km": 50,
            "gender_preferences": ["female", "nonbinary"], "relationship_types": ["long_term", "casual"],
            "interests": ["gaming", "music", "film"],
            "personality": ["introvert", "analytical", "moody"],
            "partner_personality": ["patient", "curious"],
            "values": ["autonomy", "craft"],
            "partner_values": ["autonomy"],
            "communication_style": "reserved", "lifestyle": ["night_owl", "homebody"],
            "selectivity": "open", "cultural_preferences": [],
            "attachment_style": "disorganized",
            "love_language_giving": ["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"],
            "love_language_receiving": ["quality_time", "words_of_affirmation", "physical_touch", "acts_of_service", "gifts"],
            "conflict_style": "avoidant", "relationship_history": "limited_experience",
            "humor_style": "dry", "conversational_texture": "deep_dive",
            "energy_pace": "low", "ambition_shape": "craft",
        },
    ),
    # 7. Nora — secure, type-A ER nurse, wants family soon (designed to match Deshawn)
    _pair(
        profile={
            "name": "Nora", "age": 34, "gender": "female",
            "location_lat": 40.7589, "location_lng": -73.9851, "city": "NYC",
            "narrative": (
                "ER nurse, twelve years in. I'm direct, I don't manage feelings for sport, and I'd like to "
                "have a kid in the next three years. I don't find this embarrassing to say. I've had one "
                "real partnership and we ended it cleanly. I'm looking for someone who's done their work "
                "and knows what they want. I'm not looking to date around."
            ),
            "emotional_giving": "I show up. I hold the line when things get bad. I don't flinch.",
            "emotional_needs": "Someone who can meet me without getting weird about it.",
            "taste_fingerprint": "Hospital cafeteria coffee, John Prine, well-made denim, Sicily",
            "current_obsession": "Triathlon training — first one in August",
            "two_hour_topic": "The specific failure modes of the American healthcare system",
            "contradiction_hook": "Emotionally composed at work, cries at dog videos",
            "past_attraction": "My ex when he fixed my bike wordlessly at 11pm. That's when I knew.",
            "favorite_places": [{"name": "Central Park reservoir", "type": "outdoor"}],
        },
        prefs={
            "min_age": 30, "max_age": 40, "max_distance_km": 40,
            "gender_preferences": ["male"], "relationship_types": ["long_term"],
            "interests": ["running", "cooking", "travel"],
            "personality": ["direct", "grounded", "driven"],
            "partner_personality": ["grounded", "decisive", "warm"],
            "values": ["family", "integrity", "competence"],
            "partner_values": ["family", "integrity"],
            "communication_style": "direct", "lifestyle": ["early_bird", "active"],
            "selectivity": "picky", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["acts_of_service", "quality_time", "physical_touch", "words_of_affirmation", "gifts"],
            "love_language_receiving": ["acts_of_service", "physical_touch", "quality_time", "words_of_affirmation", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "long_term",
            "humor_style": "dry", "conversational_texture": "direct",
            "energy_pace": "high", "ambition_shape": "career",
        },
    ),
    # 8. Tomás — avoidant, commitment-skeptical bass player (mismatch w/ Priya, maybe OK w/ Sage/Farah)
    _pair(
        profile={
            "name": "Tomás", "age": 28, "gender": "male",
            "location_lat": 40.7168, "location_lng": -73.9560, "city": "NYC",
            "narrative": (
                "I play bass in two bands and bartend four nights a week. I've never lived with a partner "
                "and I'm not sure I want to. I like my apartment the way it is. I'm not a jerk about it — "
                "I just mean what I say. I want someone who has their own full life. We can share edges, "
                "not centers."
            ),
            "emotional_giving": "Physical ease. I'm calm in the body. I don't fuss.",
            "emotional_needs": "Minimal. Please don't tell me you're proud of me, it's weird.",
            "taste_fingerprint": "Fela Kuti, bodegas, Charles Mingus, black coffee",
            "current_obsession": "A fretless bass I'm probably going to regret buying",
            "two_hour_topic": "Why every NYC band eventually becomes a real-estate story",
            "contradiction_hook": "Commitment-shy with instruments he keeps for decades",
            "past_attraction": "Nobody I'd tell you about",
            "favorite_places": [{"name": "Nublu", "type": "music_venue"}],
        },
        prefs={
            "min_age": 25, "max_age": 35, "max_distance_km": 40,
            "gender_preferences": ["female", "nonbinary"], "relationship_types": ["long_term", "casual"],
            "interests": ["music", "reading", "film"],
            "personality": ["introvert", "independent"],
            "partner_personality": ["independent", "self-contained"],
            "values": ["autonomy", "craft"],
            "partner_values": ["autonomy"],
            "communication_style": "reserved", "lifestyle": ["night_owl"],
            "selectivity": "open", "cultural_preferences": [],
            "attachment_style": "avoidant",
            "love_language_giving": ["physical_touch", "quality_time", "acts_of_service", "words_of_affirmation", "gifts"],
            "love_language_receiving": ["physical_touch", "quality_time", "acts_of_service", "words_of_affirmation", "gifts"],
            "conflict_style": "need_space", "relationship_history": "mostly_casual",
            "humor_style": "dry", "conversational_texture": "direct",
            "energy_pace": "low", "ambition_shape": "craft",
        },
    ),
    # 9. Ruth — picky literary agent, intellectual (designed mismatch w/ most; maybe Ben or Leo)
    _pair(
        profile={
            "name": "Ruth", "age": 36, "gender": "female",
            "location_lat": 40.7813, "location_lng": -73.9747, "city": "NYC",
            "narrative": (
                "I rep literary fiction and I'm running out of patience with people who don't read. I'm "
                "sharp, I'm funny in a way that reads as mean if you're insecure, and I'm tired of dating "
                "men who are proud of finishing one book this year. I was married at 29. It was fine until "
                "it wasn't. I want a real thinker or I'd rather be alone."
            ),
            "emotional_giving": "Attention. The real kind. I notice the thing you're afraid I'll notice.",
            "emotional_needs": "Someone who can keep up and won't resent it.",
            "taste_fingerprint": "Denis Johnson, Clarice Lispector, single-origin espresso, brutalism",
            "current_obsession": "A debut novel I might sell for a lot, if I don't overthink the edit",
            "two_hour_topic": "Why the American novel got quiet in 2014 and hasn't recovered",
            "contradiction_hook": "Public defender of difficulty; cries at pop country",
            "past_attraction": "A poet who told me I overexplain. He was right and I didn't forgive him.",
            "favorite_places": [{"name": "McNally Jackson Seaport", "type": "bookstore"}],
        },
        prefs={
            "min_age": 32, "max_age": 45, "max_distance_km": 40,
            "gender_preferences": ["male"], "relationship_types": ["long_term"],
            "interests": ["literature", "film", "art", "travel"],
            "personality": ["analytical", "direct", "sharp"],
            "partner_personality": ["intellectual", "secure", "playful"],
            "values": ["intellect", "honesty", "craft"],
            "partner_values": ["intellect", "honesty"],
            "communication_style": "direct", "lifestyle": ["night_owl", "social"],
            "selectivity": "picky", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["words_of_affirmation", "quality_time", "gifts", "acts_of_service", "physical_touch"],
            "love_language_receiving": ["words_of_affirmation", "quality_time", "physical_touch", "gifts", "acts_of_service"],
            "conflict_style": "talk_immediately", "relationship_history": "long_term",
            "humor_style": "sharp", "conversational_texture": "deep_dive",
            "energy_pace": "high", "ambition_shape": "career",
        },
    ),
    # 10. Kai — anxious exuberant dancer, physical-touch-driven
    _pair(
        profile={
            "name": "Kai", "age": 25, "gender": "nonbinary",
            "location_lat": 40.7420, "location_lng": -73.9890, "city": "NYC",
            "narrative": (
                "I dance contemporary and I barista to make rent. I'm loud, I hug too hard, and I know when "
                "I'm too much because I can feel the room shift. Still working on that. I want someone who "
                "isn't afraid of big feelings and who actually likes being touched. I'm exhausting to some "
                "people. I'm looking for someone I'm not exhausting to."
            ),
            "emotional_giving": "Body. I'll hold you for an hour. I'll dance in your kitchen.",
            "emotional_needs": "To not be shushed when I'm big. To be met, not managed.",
            "taste_fingerprint": "Pina Bausch, soft-serve, FKA twigs, public fountains",
            "current_obsession": "Learning to read sheet music at 25",
            "two_hour_topic": "Why modern dance mostly got worse after Twitter",
            "contradiction_hook": "Exuberant in public, cries alone for half an hour",
            "past_attraction": "Someone who put their hand on the small of my back in a subway and I almost proposed",
            "favorite_places": [{"name": "Joyce Theater", "type": "theater"}],
        },
        prefs={
            "min_age": 23, "max_age": 34, "max_distance_km": 50,
            "gender_preferences": ["male", "female", "nonbinary"], "relationship_types": ["long_term"],
            "interests": ["dance", "music", "art"],
            "personality": ["extrovert", "empathetic", "intense"],
            "partner_personality": ["warm", "patient", "physical"],
            "values": ["presence", "growth", "play"],
            "partner_values": ["presence"],
            "communication_style": "direct", "lifestyle": ["night_owl", "active", "social"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "anxious",
            "love_language_giving": ["physical_touch", "quality_time", "words_of_affirmation", "acts_of_service", "gifts"],
            "love_language_receiving": ["physical_touch", "quality_time", "words_of_affirmation", "acts_of_service", "gifts"],
            "conflict_style": "talk_immediately", "relationship_history": "mostly_casual",
            "humor_style": "playful", "conversational_texture": "story_mode",
            "energy_pace": "high", "ambition_shape": "craft",
        },
    ),
    # 11. Mia — analytical PhD student, introvert, late bloomer
    _pair(
        profile={
            "name": "Mia", "age": 27, "gender": "female",
            "location_lat": 40.8075, "location_lng": -73.9626, "city": "NYC",
            "narrative": (
                "Fourth year of a linguistics PhD. I study how people make small talk across languages — "
                "which is funny because I'm bad at it. I've been in one short relationship and I was "
                "twenty-three. I'm not in a rush; I also don't want to still be saying that at thirty-five. "
                "I'd like someone who likes me when I'm quiet."
            ),
            "emotional_giving": "Close attention to your specific weirdness. I remember your jokes.",
            "emotional_needs": "Patience with ramp-up. I take a while to warm but I stay warm.",
            "taste_fingerprint": "Anne Carson, Bach partitas, Japanese stationery",
            "current_obsession": "My dissertation data, which may or may not say anything",
            "two_hour_topic": "How language reveals what a culture refuses to name",
            "contradiction_hook": "Studies talk for a living, goes quiet at parties",
            "past_attraction": "A TA in undergrad who asked what I thought and actually waited",
            "favorite_places": [{"name": "Butler Library", "type": "library"}],
        },
        prefs={
            "min_age": 26, "max_age": 36, "max_distance_km": 40,
            "gender_preferences": ["male", "female"], "relationship_types": ["long_term"],
            "interests": ["linguistics", "reading", "classical music", "tea"],
            "personality": ["introvert", "analytical", "gentle"],
            "partner_personality": ["patient", "curious", "intellectual"],
            "values": ["intellect", "honesty", "growth"],
            "partner_values": ["intellect", "presence"],
            "communication_style": "deliberate", "lifestyle": ["early_bird", "homebody"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["acts_of_service", "quality_time", "words_of_affirmation", "physical_touch", "gifts"],
            "love_language_receiving": ["quality_time", "words_of_affirmation", "physical_touch", "acts_of_service", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "limited_experience",
            "humor_style": "dry", "conversational_texture": "deep_dive",
            "energy_pace": "low", "ambition_shape": "craft",
        },
    ),
    # 12. Deshawn — secure, methodical architect (designed pair with Nora)
    _pair(
        profile={
            "name": "Deshawn", "age": 35, "gender": "male",
            "location_lat": 40.7338, "location_lng": -74.0027, "city": "NYC",
            "narrative": (
                "Architect, mid-career, partner-track at a firm I actually respect. I grew up in a house "
                "with two parents who still like each other and I noticed. I was engaged once; we called "
                "it off and I'm glad. I cook on Sundays for the week. I want kids eventually and I don't "
                "think that's the same as wanting them tomorrow. I take my time."
            ),
            "emotional_giving": "Consistency. You know what you're getting. I don't do surprise shifts.",
            "emotional_needs": "Honesty on the way up, not after it's a problem.",
            "taste_fingerprint": "Ando, miso, vintage Saabs, mid-century anything",
            "current_obsession": "A cabin I'm designing for myself in the Hudson Valley",
            "two_hour_topic": "Why most new buildings will not age well",
            "contradiction_hook": "Designs for permanence, lives in a rental",
            "past_attraction": "My fiancée when she told me the truth about why it wasn't working. Grew up in that conversation.",
            "favorite_places": [{"name": "Storm King", "type": "outdoor"}, {"name": "Atoboy", "type": "restaurant"}],
        },
        prefs={
            "min_age": 30, "max_age": 38, "max_distance_km": 50,
            "gender_preferences": ["female"], "relationship_types": ["long_term"],
            "interests": ["architecture", "cooking", "hiking", "jazz"],
            "personality": ["grounded", "analytical", "warm"],
            "partner_personality": ["direct", "grounded", "decisive"],
            "values": ["family", "integrity", "craft"],
            "partner_values": ["family", "integrity"],
            "communication_style": "deliberate", "lifestyle": ["early_bird", "active"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["acts_of_service", "quality_time", "physical_touch", "gifts", "words_of_affirmation"],
            "love_language_receiving": ["quality_time", "acts_of_service", "physical_touch", "words_of_affirmation", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "long_term",
            "humor_style": "warm", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "career",
        },
    ),
    # 13. Farah — secure-avoidant, travels for work, needs autonomy
    _pair(
        profile={
            "name": "Farah", "age": 30, "gender": "female",
            "location_lat": 40.7061, "location_lng": -74.0087, "city": "NYC",
            "narrative": (
                "Documentary filmmaker. I'm on a plane eight times a year, sometimes to places I can't say "
                "much about. I've dated seriously twice; both ended because I couldn't stay in one place "
                "and they couldn't keep not asking me to. I'm not looking to be fixed. I want someone with "
                "their own full thing who's happy to see me when I land."
            ),
            "emotional_giving": "Intensity when I'm here. No pretending I'm 'available' when I'm gone.",
            "emotional_needs": "A partner who doesn't measure love in frequency of texts.",
            "taste_fingerprint": "Werner Herzog, roadside food, analog film, winter light",
            "current_obsession": "A long piece about women in border towns, maybe two more years",
            "two_hour_topic": "Why documentary ethics are hand-wavier than people want to admit",
            "contradiction_hook": "Films other people's lives; rarely invites anyone into hers",
            "past_attraction": "My last partner the week before he asked me to quit. Up until that moment, kind of perfect.",
            "favorite_places": [{"name": "Film Forum", "type": "theater"}],
        },
        prefs={
            "min_age": 28, "max_age": 42, "max_distance_km": 80,
            "gender_preferences": ["male", "female"], "relationship_types": ["long_term"],
            "interests": ["film", "reading", "travel", "photography"],
            "personality": ["independent", "analytical", "warm"],
            "partner_personality": ["independent", "secure", "self-contained"],
            "values": ["autonomy", "craft", "honesty"],
            "partner_values": ["autonomy", "integrity"],
            "communication_style": "deliberate", "lifestyle": ["traveler", "night_owl"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "avoidant",
            "love_language_giving": ["quality_time", "words_of_affirmation", "physical_touch", "acts_of_service", "gifts"],
            "love_language_receiving": ["quality_time", "physical_touch", "words_of_affirmation", "acts_of_service", "gifts"],
            "conflict_style": "need_space", "relationship_history": "long_term",
            "humor_style": "dry", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "craft",
        },
    ),
    # 14. Ben — earnest secure schoolteacher (could pair with Mia, Priya, maybe Ruth on a good day)
    _pair(
        profile={
            "name": "Ben", "age": 29, "gender": "male",
            "location_lat": 40.6953, "location_lng": -73.9892, "city": "NYC",
            "narrative": (
                "I teach 8th grade English in Brooklyn. I love it. My students would tell you I'm earnest "
                "to a fault and slightly embarrassing, and they're right. I'm secure, I'm a good listener, "
                "I read way too much. I don't have a lot of game but I'm told I improve on close inspection. "
                "I want a partnership, not a project."
            ),
            "emotional_giving": "I listen properly. I ask the second question, not just the first.",
            "emotional_needs": "Kindness. I'm less interesting to people who need to be the sharpest in the room.",
            "taste_fingerprint": "George Saunders, public libraries, diner coffee, proper rain jackets",
            "current_obsession": "Teaching The Odyssey to kids who think it's cringe",
            "two_hour_topic": "What you actually teach when you teach a book",
            "contradiction_hook": "Earnest teacher with a filthy sense of humor",
            "past_attraction": "A woman at a wedding who said she was tired of irony. We didn't exchange numbers and I still think about it.",
            "favorite_places": [{"name": "BPL Central", "type": "library"}],
        },
        prefs={
            "min_age": 26, "max_age": 36, "max_distance_km": 40,
            "gender_preferences": ["female"], "relationship_types": ["long_term"],
            "interests": ["reading", "teaching", "film", "baseball"],
            "personality": ["empathetic", "gentle", "curious"],
            "partner_personality": ["warm", "curious", "grounded"],
            "values": ["family", "integrity", "growth"],
            "partner_values": ["growth", "honesty"],
            "communication_style": "deliberate", "lifestyle": ["early_bird", "homebody"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["quality_time", "acts_of_service", "words_of_affirmation", "physical_touch", "gifts"],
            "love_language_receiving": ["words_of_affirmation", "quality_time", "physical_touch", "acts_of_service", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "long_term",
            "humor_style": "dry", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "service",
        },
    ),
    # 15. Yuna — ambitious PM, type-A, warm underneath
    _pair(
        profile={
            "name": "Yuna", "age": 28, "gender": "female",
            "location_lat": 40.7549, "location_lng": -73.9840, "city": "NYC",
            "narrative": (
                "Senior PM at a fintech that'll probably IPO. I work a lot. I'm told I come across as "
                "transactional and I think that's partly fair and partly people not liking that I'm direct. "
                "I'm warm once I trust you. I don't want a stay-at-home partner energy — I want someone "
                "running their own thing hard."
            ),
            "emotional_giving": "Clarity. I'll tell you what I need. I'll ask what you need.",
            "emotional_needs": "Respect for my schedule without it becoming a thing.",
            "taste_fingerprint": "Negronis, structured blazers, Joan Didion, running",
            "current_obsession": "Marathon training — first one in the fall",
            "two_hour_topic": "Why most tech orgs are badly designed in predictable ways",
            "contradiction_hook": "Ice at work, soft with friends' dogs",
            "past_attraction": "My college boyfriend when he told me he'd wait for me after grad school. He didn't. Fair.",
            "favorite_places": [{"name": "Court Street Grocers", "type": "cafe"}],
        },
        prefs={
            "min_age": 28, "max_age": 38, "max_distance_km": 40,
            "gender_preferences": ["male"], "relationship_types": ["long_term"],
            "interests": ["running", "business", "reading", "design"],
            "personality": ["driven", "direct", "analytical"],
            "partner_personality": ["driven", "direct", "secure"],
            "values": ["competence", "integrity", "growth"],
            "partner_values": ["competence", "integrity"],
            "communication_style": "direct", "lifestyle": ["early_bird", "active"],
            "selectivity": "picky", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["acts_of_service", "quality_time", "words_of_affirmation", "physical_touch", "gifts"],
            "love_language_receiving": ["quality_time", "acts_of_service", "physical_touch", "words_of_affirmation", "gifts"],
            "conflict_style": "talk_immediately", "relationship_history": "long_term",
            "humor_style": "sharp", "conversational_texture": "direct",
            "energy_pace": "high", "ambition_shape": "career",
        },
    ),
    # 16. Rafe — ex-Marine, recently single, disciplined
    _pair(
        profile={
            "name": "Rafe", "age": 34, "gender": "male",
            "location_lat": 40.6912, "location_lng": -73.9897, "city": "NYC",
            "narrative": (
                "I did six years active duty, out since 2019. I work in logistics now — boring to describe, "
                "not boring to do. I got out of an eight-year thing last fall. I'm not bitter, I'm just "
                "re-learning what I like. I'm steady, I'm honest, I don't play games. I run at 5am and "
                "I'm probably asleep by ten."
            ),
            "emotional_giving": "I do what I say I'll do. I'm calm under pressure.",
            "emotional_needs": "Tell me directly. I'd rather hear it hard than read it sideways.",
            "taste_fingerprint": "Cormac McCarthy, bourbon, old Hondas, Memphis barbecue",
            "current_obsession": "Reading fiction for the first time in years",
            "two_hour_topic": "How institutions actually function vs. their org charts",
            "contradiction_hook": "Marine who cries at the Pixar short before the movie",
            "past_attraction": "My ex, for eight years. I'm not ready to talk about it yet. Soon.",
            "favorite_places": [{"name": "Prospect Park loop", "type": "outdoor"}],
        },
        prefs={
            "min_age": 28, "max_age": 38, "max_distance_km": 50,
            "gender_preferences": ["female"], "relationship_types": ["long_term"],
            "interests": ["running", "reading", "cooking"],
            "personality": ["grounded", "disciplined", "quiet"],
            "partner_personality": ["direct", "grounded", "warm"],
            "values": ["integrity", "family", "competence"],
            "partner_values": ["integrity", "family"],
            "communication_style": "direct", "lifestyle": ["early_bird", "active"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["acts_of_service", "words_of_affirmation", "quality_time", "physical_touch", "gifts"],
            "love_language_receiving": ["words_of_affirmation", "acts_of_service", "quality_time", "physical_touch", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "recently_out_of_ltr",
            "humor_style": "dry", "conversational_texture": "direct",
            "energy_pace": "steady", "ambition_shape": "service",
        },
    ),
    # 17. Elena — therapist, secure, emotionally literate
    _pair(
        profile={
            "name": "Elena", "age": 32, "gender": "female",
            "location_lat": 40.7295, "location_lng": -73.9965, "city": "NYC",
            "narrative": (
                "Therapist in private practice. Yes, I have my own therapist. I'm warm, I'm honest, and "
                "I screen carefully — not picky, just clear. I've been in two long relationships, both "
                "ended kindly. I'd like kids in the next few years. I want someone who's done some of the "
                "work and isn't expecting me to do the rest of it for them."
            ),
            "emotional_giving": "Real attention. I can tell what you're not saying and I'll ask carefully.",
            "emotional_needs": "A partner who can tell me what's going on without me excavating.",
            "taste_fingerprint": "James Baldwin, dumplings, Bon Iver, honest haircuts",
            "current_obsession": "Learning Portuguese for a Lisbon trip in October",
            "two_hour_topic": "What therapy can and can't actually do for people",
            "contradiction_hook": "Professional listener who talks a lot on dates",
            "past_attraction": "My ex when he named what I was feeling before I did. Rare and good.",
            "favorite_places": [{"name": "Washington Square Park", "type": "outdoor"}],
        },
        prefs={
            "min_age": 29, "max_age": 40, "max_distance_km": 40,
            "gender_preferences": ["male"], "relationship_types": ["long_term"],
            "interests": ["reading", "running", "travel", "film"],
            "personality": ["empathetic", "grounded", "warm"],
            "partner_personality": ["grounded", "emotionally literate", "warm"],
            "values": ["growth", "family", "integrity"],
            "partner_values": ["growth", "family"],
            "communication_style": "deliberate", "lifestyle": ["early_bird", "active"],
            "selectivity": "picky", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["quality_time", "words_of_affirmation", "physical_touch", "acts_of_service", "gifts"],
            "love_language_receiving": ["quality_time", "physical_touch", "words_of_affirmation", "acts_of_service", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "long_term",
            "humor_style": "warm", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "service",
        },
    ),
    # 18. Marcus — ambitious banker, time-poor (designed to mismatch Kai, maybe OK w/ Yuna)
    _pair(
        profile={
            "name": "Marcus", "age": 33, "gender": "male",
            "location_lat": 40.7074, "location_lng": -74.0113, "city": "NYC",
            "narrative": (
                "I'm a VP at an investment bank. The hours are what you think they are. I'm honest about "
                "that upfront because pretending otherwise is how relationships end. I'm confident, I'm "
                "funny when I'm not tired, and I want someone whose life is also full. I'm not looking for "
                "someone to entertain when I'm off."
            ),
            "emotional_giving": "I'm good when I'm present. I don't half-ass.",
            "emotional_needs": "Someone who gets the work without resenting it.",
            "taste_fingerprint": "Steakhouses, Miles Davis, Brioni, golf",
            "current_obsession": "A boat I can't justify owning",
            "two_hour_topic": "How capital allocation actually works once you strip out the theater",
            "contradiction_hook": "Works in finance; reads a lot of poetry on trains",
            "past_attraction": "My ex at our engagement party right before I knew I couldn't do it. I'm clearer now.",
            "favorite_places": [{"name": "Keens", "type": "restaurant"}],
        },
        prefs={
            "min_age": 27, "max_age": 36, "max_distance_km": 50,
            "gender_preferences": ["female"], "relationship_types": ["long_term"],
            "interests": ["finance", "golf", "wine", "reading"],
            "personality": ["driven", "direct", "confident"],
            "partner_personality": ["driven", "secure", "independent"],
            "values": ["competence", "ambition", "integrity"],
            "partner_values": ["ambition", "competence"],
            "communication_style": "direct", "lifestyle": ["early_bird", "social"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "avoidant",
            "love_language_giving": ["gifts", "quality_time", "physical_touch", "acts_of_service", "words_of_affirmation"],
            "love_language_receiving": ["physical_touch", "words_of_affirmation", "quality_time", "gifts", "acts_of_service"],
            "conflict_style": "need_space", "relationship_history": "recently_out_of_ltr",
            "humor_style": "dry", "conversational_texture": "direct",
            "energy_pace": "high", "ambition_shape": "career",
        },
    ),
    # 19. Ivy — enthusiastic new grad engineer, limited experience
    _pair(
        profile={
            "name": "Ivy", "age": 24, "gender": "female",
            "location_lat": 40.7202, "location_lng": -74.0006, "city": "NYC",
            "narrative": (
                "I'm a software engineer eighteen months into my first real job. I moved to New York for "
                "it and I still can't believe I live here. I've only dated a couple of people; I'm curious "
                "and I'm not in a rush. I'm probably too enthusiastic for some people. I'm fine with that."
            ),
            "emotional_giving": "Delight. I get excited about your thing. I show up.",
            "emotional_needs": "Kindness and a sense that you're actually into this.",
            "taste_fingerprint": "Cortado mornings, indie games, Le Guin, good socks",
            "current_obsession": "Learning to cook something besides pasta",
            "two_hour_topic": "How to convince senior engineers that code review matters",
            "contradiction_hook": "Cheerful optimist who reads sci-fi dystopias for fun",
            "past_attraction": "My college boyfriend when he bought me a ridiculous birthday cake",
            "favorite_places": [{"name": "Housing Works Bookstore", "type": "bookstore"}],
        },
        prefs={
            "min_age": 23, "max_age": 32, "max_distance_km": 40,
            "gender_preferences": ["male", "female"], "relationship_types": ["long_term", "casual"],
            "interests": ["coding", "reading", "gaming", "cooking"],
            "personality": ["curious", "enthusiastic", "gentle"],
            "partner_personality": ["kind", "curious", "patient"],
            "values": ["growth", "honesty", "play"],
            "partner_values": ["growth", "honesty"],
            "communication_style": "direct", "lifestyle": ["early_bird", "active"],
            "selectivity": "open", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["quality_time", "words_of_affirmation", "acts_of_service", "gifts", "physical_touch"],
            "love_language_receiving": ["words_of_affirmation", "quality_time", "physical_touch", "gifts", "acts_of_service"],
            "conflict_style": "talk_immediately", "relationship_history": "limited_experience",
            "humor_style": "playful", "conversational_texture": "story_mode",
            "energy_pace": "high", "ambition_shape": "career",
        },
    ),
    # 20. Oscar — divorced dad (kid part-time), secure, recalibrated
    _pair(
        profile={
            "name": "Oscar", "age": 37, "gender": "male",
            "location_lat": 40.7614, "location_lng": -73.9776, "city": "NYC",
            "narrative": (
                "I'm a product designer. I've got a six-year-old half the week. My marriage ended two years "
                "ago and I've done the work — real therapy, not just the jokes about it. I'm not looking for "
                "someone to parent with tomorrow. I'm looking for someone who's OK with a kid existing and "
                "with me being unavailable Wednesdays and every other weekend."
            ),
            "emotional_giving": "I don't hide. I'll tell you what's hard and what's good.",
            "emotional_needs": "Someone who doesn't make me small for having a kid.",
            "taste_fingerprint": "Wes Anderson, good bagels, small-batch mezcal, the High Line in winter",
            "current_obsession": "Teaching my kid to ride a bike without losing my mind",
            "two_hour_topic": "What I got wrong in my first marriage, in specific rather than general terms",
            "contradiction_hook": "Designer who's tired of design discourse",
            "past_attraction": "My ex the first year we dated — I keep that separate from how it ended",
            "favorite_places": [{"name": "Court Street Bagels", "type": "deli"}],
        },
        prefs={
            "min_age": 30, "max_age": 40, "max_distance_km": 40,
            "gender_preferences": ["female"], "relationship_types": ["long_term"],
            "interests": ["design", "cooking", "film", "running"],
            "personality": ["grounded", "warm", "analytical"],
            "partner_personality": ["grounded", "warm", "direct"],
            "values": ["family", "honesty", "growth"],
            "partner_values": ["honesty", "family"],
            "communication_style": "direct", "lifestyle": ["early_bird", "active"],
            "selectivity": "balanced", "cultural_preferences": [],
            "attachment_style": "secure",
            "love_language_giving": ["quality_time", "acts_of_service", "physical_touch", "words_of_affirmation", "gifts"],
            "love_language_receiving": ["physical_touch", "quality_time", "words_of_affirmation", "acts_of_service", "gifts"],
            "conflict_style": "collaborative", "relationship_history": "long_term",
            "humor_style": "dry", "conversational_texture": "deep_dive",
            "energy_pace": "steady", "ambition_shape": "craft",
        },
    ),
]
