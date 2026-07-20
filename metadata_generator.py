import json
import config

# ============================================================
# METADATA GENERATOR — VIRAL-OPTIMIZED SOCIAL MEDIA CAPTIONS
# Generates platform-specific captions, hashtags, titles and
# descriptions tuned for maximum reach on each platform.
#
# Platforms covered:
#   - TikTok          : punchy hook + trending/niche hashtag mix
#   - Instagram Reels : hook + storytelling body + 15 hashtags
#   - Facebook        : emotional story-style + 3-5 hashtags only
#   - YouTube Shorts  : keyword-front title + tags in description
#   - YouTube Long    : SEO description + chapters + 15+ tags
#
# Strategy per spec §13:
#   - First line is always the hook — must stop the scroll
#   - Use "you" and "your" — make it personal
#   - No generic fluff ("keep grinding!")
#   - Natural CTA: "Save this", "Send to someone who needs this"
#   - Hashtags: mix broad viral + niche dark motivation
# ============================================================

# Try the new google.genai SDK first; fall back to legacy if unavailable.
# The legacy google.generativeai package is deprecated and will eventually
# stop receiving updates — the new google.genai package is the replacement.
try:
    import google.genai as genai
    _USING_NEW_SDK = True
except ImportError:
    # Legacy fallback — still functional but shows FutureWarning
    import google.generativeai as genai  # type: ignore
    _USING_NEW_SDK = False


def generate_metadata(topic, script_segments, video_format, chapters=None):
    # --------------------------------------------------------
    # Main entry point — called by the pipeline after the video
    # is assembled. Returns a dict keyed by platform name.
    #
    # Args:
    #   topic          : str  — e.g. "Power of Silence"
    #   script_segments: list — each item has "text" key
    #   video_format   : str  — "short" or "long"
    #   chapters       : list — optional, each item has "time" + "title"
    #
    # Returns:
    #   dict with keys: "youtube", "tiktok", "instagram", "facebook"
    # --------------------------------------------------------

    # If no Gemini API key is configured, skip the API call entirely
    # and return safe fallback metadata — pipeline still runs cleanly
    if not config.GEMINI_API_KEY:
        print("[METADATA] No GEMINI_API_KEY — using fallback metadata")
        return _fallback_metadata(topic, video_format)

    # ----- Build context for the prompt -----
    # Take first 10 segments to stay within prompt length limits
    script_text = " ".join([s["text"] for s in script_segments[:10]])

    # Format chapters as timestamp list if provided (long-form only)
    chapter_text = ""
    if chapters:
        chapter_text = "\n".join([f"{c['time']} - {c['title']}" for c in chapters])

    # Human-readable format label used inside the prompt
    format_label = (
        "YouTube long-form (8-12 min)"
        if video_format == "long"
        else "Short-form vertical (60-90 seconds)"
    )

    # ----- Viral caption prompt — spec §13 -----
    # The prompt is explicit about structure so Gemini returns
    # exactly the JSON keys the publisher adapters expect.
    prompt = f"""You are writing viral social media captions for a dark motivation video brand.

BRAND: Luminous Will — stoic philosophy, dark psychology, power dynamics, self-mastery.
Tone: dark, intense, minimal. No emojis. No fluff. No clichés like "keep grinding".

TOPIC: {topic}
FORMAT: {format_label}
SCRIPT EXCERPT (for context): {script_text[:600]}
{"CHAPTERS:\n" + chapter_text if chapter_text else ""}

CAPTION RULES (follow these exactly):
1. First line is the hook — it must make someone stop scrolling
2. Use "you" and "your" — make every caption feel personal
3. Include a natural CTA — "Save this.", "Send this to someone who needs it.", "Follow for more."
4. Hashtag strategy:
   - TikTok: 5 trending broad (#motivation #psychology #mindset) + 7 niche dark (#darkmotivation #stoicmindset #sigmamindset #mentaltoughness #darkpsychology #luminouswill #powerofmind)
   - Instagram: 10 trending broad + 5 niche dark + 5 topical (related to the specific topic)
   - Facebook: 3-5 hashtags only — broad is fine, do not over-hashtag
   - YouTube tags: 15-20 tags mixing exact keywords, broad topics, and long-tail phrases

OUTPUT: Respond with ONLY a valid JSON object — no markdown fences, no explanation.

{{
  "youtube": {{
    "title": "SEO-optimised title, max 60 chars, keyword-front-loaded. Must be a hook.",
    "description": "Full SEO description. Open with the hook. 2nd paragraph expands the idea. 3rd paragraph CTA to subscribe. Include chapters if provided. Min 200 chars. Max 2000 chars.",
    "tags": ["15-20 tags mixing exact topic keywords, broad motivational terms, and long-tail phrases"],
    "category": "Education"
  }},
  "tiktok": {{
    "caption": "One punchy hook sentence. Max 150 chars. No hashtags here — they go in hashtags field.",
    "hashtags": ["fyp", "foryou", "motivation", "psychology", "mindset", "darkmotivation", "stoicmindset", "sigmamindset", "mentaltoughness", "darkpsychology", "luminouswill", "powerofmind"]
  }},
  "instagram": {{
    "caption": "Hook line (1-2 sentences that stop the scroll).\\n\\nBody: 2-3 sentences that expand the idea using storytelling.\\n\\nCTA: natural, not salesy. Example: Save this for when you need it.",
    "hashtags": ["10 trending broad hashtags", "5 niche dark motivation hashtags", "5 hashtags specific to this topic"]
  }},
  "facebook": {{
    "description": "2-3 sentence emotional story-style post. Opens with hook. Ends with a question or CTA to drive comments. Include 3-5 relevant hashtags inline at the end.",
    "hashtags": ["3-5 hashtags only"]
  }}
}}"""

    try:
        # ----- Call Gemini -----
        # Use new SDK if available, otherwise use legacy
        if _USING_NEW_SDK:
            # New google.genai SDK — client-based approach
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            raw = response.text.strip()
        else:
            # Legacy google.generativeai SDK — still functional
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            raw = response.text.strip()

        # Strip markdown code fences if Gemini wraps the JSON anyway
        # (happens occasionally even when we ask it not to)
        if raw.startswith("```"):
            # Remove opening fence (```json or ```)
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])  # drop first line
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        metadata = json.loads(raw)
        print(f"[METADATA] Generated viral-optimised metadata for all platforms")
        return metadata

    except Exception as e:
        # Any Gemini error (quota, network, parse failure) falls back
        # to the hardcoded fallback — pipeline never breaks
        print(f"[METADATA] Gemini error: {e}, using fallback")
        return _fallback_metadata(topic, video_format)


def _fallback_metadata(topic, video_format):
    # --------------------------------------------------------
    # Fallback metadata — returned when Gemini is unavailable.
    # Contains properly structured viral-optimised captions and
    # hashtag strategies matching spec §13 for each platform.
    #
    # Args:
    #   topic        : str — the video topic
    #   video_format : str — "short" or "long"
    #
    # Returns:
    #   dict with keys: "youtube", "tiktok", "instagram", "facebook"
    # --------------------------------------------------------

    # ----- Shared hashtag pools -----

    # Broad viral hashtags — high reach, millions of posts
    broad_hashtags = [
        "motivation", "mindset", "psychology", "selfimprovement",
        "discipline", "success", "mentalhealth", "growthmindset",
        "personaldevelopment", "lifecoach",
    ]

    # Niche dark motivation hashtags — lower volume but hyper-relevant audience
    niche_hashtags = [
        "darkmotivation", "stoicmindset", "sigmamindset", "mentaltoughness",
        "darkpsychology", "luminouswill", "stoic", "powerofmind",
        "darkphilosophy", "mentalstrength",
    ]

    # Topic-derived hashtag — slugified version of the topic
    # e.g. "Power of Silence" → "powerofsilence"
    topic_tag = topic.lower().replace(" ", "").replace("-", "")

    # TikTok hashtag strategy:
    #   - Needs at least 12 total (5 trending + 7 niche) per spec §13
    #   - "fyp" and "foryou" are essential for TikTok's algorithm
    tiktok_hashtags = (
        ["fyp", "foryou"]            # TikTok algorithm boosters
        + broad_hashtags[:5]         # trending broad tags (high reach)
        + niche_hashtags[:7]         # niche dark motivation tags (right audience)
    )

    # Instagram hashtag strategy:
    #   - 10 broad trending + 5 niche + topic tag (16 total)
    #   - Instagram optimal: 10-15 hashtags (over 30 looks spammy)
    instagram_hashtags = (
        broad_hashtags                 # 10 broad viral hashtags
        + niche_hashtags[:5]           # 5 niche dark motivation hashtags
        + [topic_tag, "reels", "instareels", "explorepage", "viral"]
    )

    # YouTube SEO tags:
    #   - Mix of exact, broad, and long-tail phrases
    #   - 15-20 tags max per YouTube guidelines
    youtube_tags = (
        broad_hashtags
        + niche_hashtags
        + [topic_tag, "dark motivation", "stoic philosophy", "power mindset"]
    )

    # ----- YouTube description — long vs short -----
    # Long-form needs a proper multi-paragraph SEO description.
    # Short-form (YouTube Shorts) uses a brief keyword-heavy description.
    if video_format == "long":
        youtube_description = (
            f"They never told you this about {topic.lower()}. Most people go their entire lives "
            f"without understanding the psychological edge that separates the powerful from the weak.\n\n"
            f"In this video, we break down the dark psychology behind {topic.lower()} — "
            f"the stoic principles, the mental frameworks, and the hard truths that high-value people "
            f"already live by.\n\n"
            f"If this changes how you see the world, subscribe. More dark psychology every week.\n\n"
            f"Luminous Will — psychology of power, discipline, and self-mastery.\n\n"
            f"#darkmotivation #stoicmindset #psychology #mindset #luminouswill"
        )
    else:
        # Short-form: keyword-dense, punchy, under 200 chars for YouTube Shorts
        youtube_description = (
            f"The psychology of {topic.lower()}. "
            f"Dark motivation for the disciplined mind.\n"
            f"#darkmotivation #stoic #psychology #mindset #luminouswill"
        )

    # ----- Assemble and return -----
    return {
        # YouTube — SEO-first, keyword-front-loaded title, full description
        "youtube": {
            "title": f"{topic} — The Psychology of Power | Luminous Will",
            "description": youtube_description,
            "tags": youtube_tags,
            "category": "Education",
        },

        # TikTok — one punchy hook line + trending + niche hashtags
        # Caption is separate from hashtags so adapters can place them correctly
        "tiktok": {
            "caption": (
                f"They don't want you to know this about {topic.lower()}. "
                f"Save this before it's too late."
            ),
            "hashtags": tiktok_hashtags,  # at least 12 (spec requires ≥5)
        },

        # Instagram — hook → storytelling body → CTA
        # Hashtags in a separate list (often posted as first comment)
        "instagram": {
            "caption": (
                f"They never taught you this about {topic.lower()}.\n\n"
                f"The most powerful people in any room understand something "
                f"most people will spend a lifetime ignoring. "
                f"Once you see it, you cannot unsee it.\n\n"
                f"Save this for when you need it most."
            ),
            "hashtags": instagram_hashtags,  # 16 total: broad + niche + topical
        },

        # Facebook — emotional, story-style, fewer hashtags
        # Facebook algorithm rewards genuine conversation over hashtag dumps
        "facebook": {
            "description": (
                f"Most people will never understand the psychology behind {topic.lower()}. "
                f"They're too busy reacting to realise they've already lost. "
                f"Watch this if you're ready to think differently.\n\n"
                f"#darkmotivation #psychology #mindset"
            ),
            "hashtags": ["darkmotivation", "psychology", "mindset"],  # 3 only per spec
        },
    }


# ============================================================
# QUOTE REEL METADATA — TAILORED CAPTION + HASHTAG PIPELINE
# The quote itself is the hook. No generic filler.
#
# Strategy:
#   - TikTok: punchiest quote as caption, save-driven CTA
#   - Instagram: quote hook + context body + save/share CTA
#   - YouTube Shorts: quote as title, topic-rich description
#   - Facebook: quote + question CTA for comments
#   - Hashtags: quote-reel niche + dark motivation + trending
# ============================================================

# --- Quote reel hashtag pools ---
REEL_HASHTAGS_TRENDING = [
    "fyp", "foryou", "viral", "explore", "trending",
]

REEL_HASHTAGS_QUOTE = [
    "quotestoliveby", "quotesoftheday", "motivationalquotes",
    "dailyquotes", "quotereels", "quotestagram", "quotesdaily",
    "deepquotes", "quoteoftheday", "realquotes",
]

REEL_HASHTAGS_DARK = [
    "darkmotivation", "stoicquotes", "sigmaquotes", "mentaltoughness",
    "darkpsychology", "stoicmindset", "disciplinequotes",
    "luminouswill", "mindsetshift", "powerofmind",
]


def _pick_hook_quote(quotes):
    """
    # Picks the punchiest quote for the caption hook.
    # Prefers 3-8 word quotes — short hits harder in a caption.
    # Falls back to shortest quote if none in ideal range.
    """
    ideal = [q for q in quotes if 3 <= len(q.split()) <= 8]
    if ideal:
        return min(ideal, key=len)
    return min(quotes, key=len)


def generate_reel_metadata(topic, quotes):
    """
    # Generates viral captions + hashtags tailored for quote reels.
    # Uses the actual quotes as hooks — not generic motivation copy.
    #
    # Args:
    #   topic  : str  — e.g. "Discipline"
    #   quotes : list — the actual quotes in the reel
    #
    # Returns:
    #   dict with keys: "youtube", "tiktok", "instagram", "facebook"
    """
    if not quotes:
        return _fallback_metadata(topic, "short")

    hook = _pick_hook_quote(quotes)
    topic_tag = topic.lower().replace(" ", "").replace("-", "")

    # --- Try Gemini for premium captions ---
    if config.GEMINI_API_KEY:
        result = _gemini_reel_captions(topic, quotes, hook)
        if result:
            return result

    # --- Fallback: template-based ---
    return _reel_fallback(topic, quotes, hook, topic_tag)


def _gemini_reel_captions(topic, quotes, hook):
    """
    # Uses Gemini to write platform-specific captions for a quote reel.
    # Passes the actual quotes so captions reference the real content.
    """
    quotes_text = "\n".join([f"- {q}" for q in quotes])

    prompt = f"""You are writing viral social media captions for a QUOTE REEL video.

BRAND: Luminous Will — stoic philosophy, dark psychology, self-mastery.
Tone: dark, raw, minimal. No emojis. No fluff.

TOPIC: {topic}
QUOTES IN THIS REEL:
{quotes_text}

BEST HOOK QUOTE: "{hook}"

RULES:
1. Use the actual quotes from the reel — the quote IS the hook
2. TikTok caption: the hook quote only (max 150 chars). No hashtags in caption.
3. Instagram: hook quote as first line, 2 lines expanding the theme, "Save this." as CTA
4. YouTube Shorts title: the hook quote (max 60 chars), no brand name
5. Facebook: hook quote + one reflective question to drive comments
6. All captions must feel like they belong on a @theapollomethod or @vo1dm1nd post
7. No quotation marks around the quote — it should read as a statement

OUTPUT: Respond with ONLY valid JSON — no markdown fences.

{{
  "youtube": {{
    "title": "Hook quote as title, max 60 chars",
    "description": "2-3 lines: hook quote, brief expansion, subscribe CTA",
    "tags": ["15-20 tags: quote keywords + motivation + dark psychology"]
  }},
  "tiktok": {{
    "caption": "The hook quote only. Max 150 chars.",
    "hashtags": ["12-15 hashtags: fyp + quote niche + dark motivation"]
  }},
  "instagram": {{
    "caption": "Hook quote\\n\\n2 lines expanding the theme\\n\\nSave this.",
    "hashtags": ["15-20 hashtags: quote niche + dark motivation + trending"]
  }},
  "facebook": {{
    "description": "Hook quote + one reflective question",
    "hashtags": ["3-5 hashtags only"]
  }}
}}"""

    try:
        if _USING_NEW_SDK:
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            raw = response.text.strip()
        else:
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            raw = response.text.strip()

        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        metadata = json.loads(raw)
        print(f"[METADATA] Generated quote reel captions via Gemini")
        return metadata

    except Exception as e:
        print(f"[METADATA] Gemini reel caption error: {e}")
        return None


def _reel_fallback(topic, quotes, hook, topic_tag):
    """
    # Template-based fallback captions for quote reels.
    # Uses the actual quotes — never generic filler.
    """
    # --- TikTok: hook quote + trending/niche hashtags ---
    tiktok_hashtags = (
        REEL_HASHTAGS_TRENDING[:3]
        + REEL_HASHTAGS_QUOTE[:7]
        + REEL_HASHTAGS_DARK[:5]
    )

    # --- Instagram: broader hashtag mix ---
    instagram_hashtags = (
        REEL_HASHTAGS_QUOTE
        + REEL_HASHTAGS_DARK[:7]
        + [topic_tag, "reels", "instareels", "explorepage", "viral"]
    )

    # --- YouTube: SEO tags ---
    youtube_tags = (
        [topic_tag, "quotes", "motivation", "dark motivation"]
        + REEL_HASHTAGS_QUOTE[:5]
        + REEL_HASHTAGS_DARK[:5]
        + ["stoic philosophy", "self mastery", "discipline quotes",
           "mindset quotes", "quote reel", "luminous will"]
    )

    # --- Pick a second quote for variety in longer captions ---
    second = quotes[1] if len(quotes) > 1 else quotes[0]

    return {
        "youtube": {
            "title": hook[:60],
            "description": (
                f"{hook}\n\n"
                f"Dark motivation for the disciplined mind. "
                f"These aren't feel-good quotes — they're wake-up calls.\n\n"
                f"Subscribe for daily quote reels.\n"
                f"#darkmotivation #stoicquotes #luminouswill"
            ),
            "tags": youtube_tags,
            "category": "Education",
        },

        "tiktok": {
            "caption": hook[:150],
            "hashtags": tiktok_hashtags,
        },

        "instagram": {
            "caption": (
                f"{hook}\n\n"
                f"{second}\n\n"
                f"Which one hit harder? Save this for when you need it."
            ),
            "hashtags": instagram_hashtags,
        },

        "facebook": {
            "description": (
                f"{hook}\n\n"
                f"Which line do you need to hear right now?\n\n"
                f"#darkmotivation #quotes #mindset"
            ),
            "hashtags": ["darkmotivation", "quotes", "mindset"],
        },
    }
