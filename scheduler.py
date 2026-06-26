import os
import json
import random
from datetime import datetime
import google.generativeai as genai
import config
from content_types import get_content_type, get_all_topics, CONTENT_TYPES

# ============================================================
# SCHEDULER
# Handles two jobs:
#   1. Auto-rotation: which 2 content types to generate today
#   2. Topic tracking: pick an unused topic, never repeat
#
# Used topic history is stored in a local JSON file.
# On HF Spaces this lives in /tmp (ephemeral), but the web app
# also tracks used topics in Vercel Blob as the persistent copy.
# ============================================================

# --- Path to the used topics file ---
# On HF Spaces: /tmp/luminous_used_topics.json
# Locally: ./used_topics.json
_USED_TOPICS_PATH = os.path.join(
    "/tmp" if os.getenv("SPACE_ID") else os.path.dirname(__file__),
    "used_topics.json"
)


def get_todays_types():
    """
    # Returns the 2 content type keys to generate today
    # Uses day-of-year modulo 2:
    #   Odd days  → dark_motivation + stoic_philosophy
    #   Even days → wealth_mindset + dark_psychology
    """
    day_of_year = datetime.utcnow().timetuple().tm_yday

    if day_of_year % 2 == 1:
        # Odd day: motivation + stoic
        return ["dark_motivation", "stoic_philosophy"]
    else:
        # Even day: wealth + psychology
        return ["wealth_mindset", "dark_psychology"]


def _load_used_topics():
    """
    # Loads the used topics dict from disk
    # Returns: {"dark_motivation": ["topic1", ...], ...}
    """
    if not os.path.exists(_USED_TOPICS_PATH):
        return {}

    try:
        with open(_USED_TOPICS_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Corrupted file — start fresh
        return {}


def _save_used_topics(used):
    """
    # Saves the used topics dict to disk
    """
    try:
        os.makedirs(os.path.dirname(_USED_TOPICS_PATH), exist_ok=True)
        with open(_USED_TOPICS_PATH, "w") as f:
            json.dump(used, f, indent=2)
    except IOError as e:
        print(f"[SCHEDULER] WARNING: Failed to save used topics: {e}")


def pick_unused_topic(type_key):
    """
    # Picks a topic for the given content type that has never been used.
    #
    # Strategy:
    #   1. Check seed topics — pick a random unused one
    #   2. If all seed topics exhausted → ask Gemini for new unique topics
    #   3. Mark the picked topic as used immediately
    #
    # Returns: topic string (guaranteed unique within this type's history)
    """
    used = _load_used_topics()
    used_for_type = set(used.get(type_key, []))
    seed_topics = get_all_topics(type_key)

    # --- Find unused seed topics ---
    available = [t for t in seed_topics if t not in used_for_type]

    if not available:
        # All seed topics exhausted — generate new ones via Gemini
        print(f"[SCHEDULER] All {len(seed_topics)} seed topics used for {type_key}, generating new ones...")
        new_topics = _generate_new_topics(type_key, used_for_type)
        available = [t for t in new_topics if t not in used_for_type]

        if not available:
            # Gemini failed — last resort: pick random seed topic (allows rare repeat)
            print(f"[SCHEDULER] WARNING: Gemini generation failed, picking random seed topic")
            available = seed_topics

    # --- Pick a random topic from the available pool ---
    topic = random.choice(available)

    # --- Mark as used ---
    if type_key not in used:
        used[type_key] = []
    used[type_key].append(topic)
    _save_used_topics(used)

    print(f"[SCHEDULER] Picked topic for {type_key}: {topic}")
    print(f"[SCHEDULER] Used {len(used[type_key])}/{len(seed_topics)} seed topics")

    return topic


def _generate_new_topics(type_key, used_topics):
    """
    # Uses Gemini to generate 10 new unique topics for a content type
    # Passes the full used topics list so Gemini avoids any repeats
    #
    # Returns: list of new topic strings, or empty list on failure
    """
    if not config.GEMINI_API_KEY:
        print("[SCHEDULER] No Gemini API key — cannot generate new topics")
        return []

    content_type = get_content_type(type_key)
    used_list = list(used_topics)

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""You generate video topics for the YouTube channel "Luminous Will".

CONTENT TYPE: {content_type["name"]}
PERSONA: {content_type["gemini_persona"]}

ALREADY USED TOPICS (do NOT repeat any of these):
{json.dumps(used_list, indent=2)}

Generate exactly 10 NEW video topics that:
1. Match the {content_type["name"]} content type
2. Are completely different from all used topics above
3. Are specific and compelling (not generic)
4. Would make someone stop scrolling
5. Are 5-12 words each

Respond with ONLY a JSON array of 10 strings, no markdown:
["Topic 1", "Topic 2", ...]"""

    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        new_topics = json.loads(raw_text)

        if isinstance(new_topics, list) and len(new_topics) > 0:
            # Ensure all are strings
            new_topics = [str(t) for t in new_topics if t]
            print(f"[SCHEDULER] Gemini generated {len(new_topics)} new topics for {type_key}")
            return new_topics

    except Exception as e:
        print(f"[SCHEDULER] Gemini topic generation failed: {e}")

    return []


def get_used_count(type_key):
    """
    # Returns how many topics have been used for a content type
    # Useful for monitoring and the web dashboard
    """
    used = _load_used_topics()
    return len(used.get(type_key, []))
