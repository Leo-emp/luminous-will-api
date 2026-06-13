import random
import json
import config
import google.generativeai as genai

# ============================================================
# SCRIPT GENERATOR
# Generates motivational/psychological scripts with punchy hooks
# ============================================================


# --- Hook templates that stop the scroll ---
# These are proven viral hook formulas for dark motivation content
HOOK_TEMPLATES = [
    "If you {action}, you need to hear this.",
    "Stop {bad_habit}. Here's why.",
    "The reason you feel {emotion} isn't what you think.",
    "Most people will ignore this. But the smart ones won't.",
    "This one habit is quietly destroying your life.",
    "They don't want you to know this.",
    "If nobody told you this today, listen carefully.",
    "The harsh truth about {topic} nobody talks about.",
    "You're not {problem}. You're just surrounded by the wrong people.",
    "A psychologist once said something that changed everything.",
    "Read this before it's too late.",
    "The difference between you and them? This.",
    "This is why you always feel {emotion}.",
    "Pay attention. This will change how you see everything.",
    "Here's what {bad_people} don't want you to figure out.",
    "If you're always the one trying, read this.",
    "One sentence that will change your entire mindset.",
    "You were never {problem}. You were just {truth}.",
    "Some people need to hear this right now.",
    "The psychology behind why {topic} will shock you.",
]


def generate_script(topic=None, custom_hook=None, video_format=None):
    """
    # Generates a video script based on the format:
    #   - VERTICAL_SHORT: template-based (existing behavior)
    #   - HORIZONTAL_LONG: Gemini AI-generated (8-12 min)
    #
    # Returns (segments_list, topic_string)
    """

    # Import here to avoid circular import
    from config import VideoFormat

    if video_format == VideoFormat.HORIZONTAL_LONG:
        return generate_long_script(topic)

    # --- Default: short-form template script ---
    if topic is None:
        topic = random.choice(config.TRENDING_TOPICS)

    print(f"[SCRIPT] Generating script for: {topic}")
    script = get_template_script(topic)
    return script, topic


def generate_long_script(topic=None):
    """
    # Generates an 8-12 minute script using Gemini AI
    # Returns 40-60 segments with narrative arc structure:
    #   hook -> setup -> escalation -> climax -> resolution -> callback
    # Each segment includes visual keywords and chapter markers
    """

    if topic is None:
        topic = random.choice(config.TRENDING_TOPICS)

    print(f"[SCRIPT] Generating long-form script for: {topic}")

    if not config.GEMINI_API_KEY:
        print("[SCRIPT] WARNING: No Gemini API key, falling back to chained templates")
        return _chain_template_scripts(topic), topic

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""You are a scriptwriter for the YouTube channel "Luminous Will" — dark motivation, stoic philosophy, psychology of power.

VOICE RULES:
- Stoic, commanding, no-nonsense. Short punchy sentences even in long form.
- No fluff, no clichés ("grind", "hustle", "manifest"), no questions to the audience.
- Speak in universal truths. Never say "I" or "we". Use "you" and "they".
- Dark, intense energy. The tone of someone who has seen the worst and emerged stronger.

STRUCTURE for an 8-12 minute script on "{topic}":
1. HOOK (first 30 seconds) — One shocking statement that stops the scroll
2. SETUP (1-2 min) — Frame the problem, make it personal
3. ESCALATION (3-4 min) — Go deeper, reveal uncomfortable truths, build intensity
4. CLIMAX (2-3 min) — The turning point, the harsh lesson, the wake-up call
5. RESOLUTION (1-2 min) — The path forward, actionable transformation
6. CALLBACK (30 seconds) — Circle back to the opening hook with new meaning

Generate exactly 50 segments. Each segment is ONE sentence (max 20 words).

CHAPTER MARKERS: Insert a chapter title every 6-8 segments (for YouTube chapters). Set chapter to null for non-chapter segments.

OUTPUT FORMAT — respond with ONLY a JSON array, no markdown, no explanation:
[
  {{
    "text": "The sentence spoken in the voiceover.",
    "visual_keywords": "5-6 keywords for stock footage search (landscape orientation, dark cinematic)",
    "visual_keywords_alt": [
      "alternative search query 1 — different angle on same visual concept",
      "alternative search query 2 — broader or abstract version",
      "alternative search query 3 — concrete subject that matches the mood"
    ],
    "mood": "dark|intense|reflective|powerful",
    "emphasis_words": ["one", "key", "word"],
    "chapter": "Chapter Title Here or null"
  }},
  ...
]

VISUAL KEYWORD RULES:
- Always include "dark" or "cinematic" in keywords
- Use landscape-oriented subjects: cityscapes, mountains, oceans, highways, architecture, storms
- Vary the subjects — no two consecutive segments should have the same visual theme
- Preferred subjects: dark cityscape night, storm clouds dramatic, mountain peak dark, ocean waves cinematic, businessman walking dark, wolf forest night, lion savanna dark, chess board dark, gym training dark, running athlete silhouette

VISUAL KEYWORDS ALT RULES:
- Each alt query should be a DIFFERENT way to find footage that matches this segment's meaning
- Alt 1: rephrase the main query with different synonyms (e.g. "dark city skyline night" vs "urban nightscape cinematic")
- Alt 2: zoom out to a broader concept (e.g. "dark atmospheric landscape" for a power segment)
- Alt 3: use a concrete, searchable subject (e.g. "wolf standing alone dark forest" for a solitude segment)
- All alts must still match the dark/cinematic brand — no bright, happy, colorful subjects

Generate the script now. 50 segments, JSON array only."""

    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        segments = json.loads(raw_text)

        # Validate and normalize segment structure
        validated = []
        for seg in segments:
            # --- Parse alt keywords: list of 3 alternative search queries ---
            raw_alts = seg.get("visual_keywords_alt", [])
            alts = [str(a) for a in raw_alts if a] if isinstance(raw_alts, list) else []

            validated.append({
                "text": str(seg.get("text", "")),
                "visual_keywords": str(seg.get("visual_keywords", "dark cinematic landscape")),
                "visual_keywords_alt": alts,
                "emphasis_word": seg.get("emphasis_words", [""])[0] if seg.get("emphasis_words") else "",
                "mood": str(seg.get("mood", "dark")),
                "chapter": seg.get("chapter"),
            })

        if len(validated) < 30:
            print(f"[SCRIPT] WARNING: Only {len(validated)} segments generated, expected 40-60")

        print(f"[SCRIPT] Generated {len(validated)} segments via Gemini")

        # Count chapters
        chapters = [s for s in validated if s.get("chapter")]
        print(f"[SCRIPT] Chapters: {len(chapters)}")

        return validated, topic

    except json.JSONDecodeError as e:
        print(f"[SCRIPT] JSON parse error from Gemini: {e}")
        print(f"[SCRIPT] Raw response (first 500 chars): {raw_text[:500]}")
        print("[SCRIPT] Falling back to chained templates")
        return _chain_template_scripts(topic), topic

    except Exception as e:
        print(f"[SCRIPT] Gemini API error: {e}")
        print("[SCRIPT] Falling back to chained templates")
        return _chain_template_scripts(topic), topic


def _chain_template_scripts(topic):
    """
    # Fallback: chains multiple template scripts together for long-form
    # Used when Gemini API is unavailable
    """
    available_scripts = []
    for t in config.TRENDING_TOPICS:
        script = get_template_script(t)
        if len(script) > 0:
            available_scripts.append(script)

    # Shuffle and take enough to fill 8-12 minutes (~50 segments)
    random.shuffle(available_scripts)
    chained = []
    for script in available_scripts:
        chained.extend(script)
        if len(chained) >= 45:
            break

    return chained


def extract_chapters(script_segments, caption_events):
    """
    # Extracts YouTube chapter markers from long-form script segments
    # Returns list of {time: "M:SS", title: str} for video description
    """
    chapters = []
    word_index = 0

    for seg in script_segments:
        if seg.get("chapter"):
            # Find the timestamp for this segment
            if word_index < len(caption_events):
                start_time = caption_events[word_index]["start"] if caption_events else 0
            else:
                start_time = 0

            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            chapters.append({
                "time": f"{minutes}:{seconds:02d}",
                "title": seg["chapter"],
                "seconds": start_time,
            })

        word_index += 1

    # Ensure first chapter starts at 0:00
    if chapters and chapters[0]["seconds"] > 0:
        chapters.insert(0, {"time": "0:00", "title": "Introduction", "seconds": 0})

    return chapters


def get_template_script(topic):
    """
    # Returns a pre-written template script
    # Replace this function with LLM-generated scripts for variety
    # Each segment = one caption group shown on screen
    """

    # --- Collection of full scripts organized by topic ---
    scripts = {

        # =====================================================
        # SCRIPT: The psychology of silence and power
        # ~27 segments, ~185 words -> ~70s at 2.62 wps
        # =====================================================
        "The psychology of silence and power": [
            {
                "text": "The most powerful people in the room never raise their voice.",
                "visual_keywords": "man silhouette suit dark office window",
                "emphasis_word": "powerful",
            },
            {
                "text": "And there's a psychological reason for that.",
                "visual_keywords": "chess pieces dark cinematic board",
                "emphasis_word": "psychological",
            },
            {
                "text": "When you stay silent, people can't read you.",
                "visual_keywords": "man back view walking dark hallway",
                "emphasis_word": "silent",
            },
            {
                "text": "They can't predict your next move.",
                "visual_keywords": "chess hand moving piece dark",
                "emphasis_word": "predict",
            },
            {
                "text": "And that makes you dangerous.",
                "visual_keywords": "lion adult male dark wild savanna",
                "emphasis_word": "dangerous",
            },
            {
                "text": "Psychologists call this the power of ambiguity.",
                "visual_keywords": "man silhouette dark shadow mysterious",
                "emphasis_word": "ambiguity",
            },
            {
                "text": "When people don't know what you're thinking,",
                "visual_keywords": "dark smoke fog cinematic abstract",
                "emphasis_word": "thinking",
            },
            {
                "text": "they fill the gap with their own fears.",
                "visual_keywords": "dark corridor shadows cinematic moody",
                "emphasis_word": "fears",
            },
            {
                "text": "Your silence becomes their anxiety.",
                "visual_keywords": "rain dark window cinematic night drops",
                "emphasis_word": "anxiety",
            },
            {
                "text": "The loud ones? They expose everything.",
                "visual_keywords": "dark city crowd night aerial",
                "emphasis_word": "expose",
            },
            {
                "text": "Their emotions. Their insecurities. Their weaknesses.",
                "visual_keywords": "boxing gloves gym dark punching bag",
                "emphasis_word": "weaknesses",
            },
            {
                "text": "But the silent ones? They observe.",
                "visual_keywords": "wolf dark forest night walking",
                "emphasis_word": "observe",
            },
            {
                "text": "They calculate. They wait.",
                "visual_keywords": "city skyline night dark rooftop cinematic",
                "emphasis_word": "wait",
            },
            {
                "text": "And when they finally speak, the whole room listens.",
                "visual_keywords": "dark boardroom empty table cinematic",
                "emphasis_word": "listens",
            },
            {
                "text": "This is why silence is the language of the strong.",
                "visual_keywords": "dark mountain peak clouds cinematic",
                "emphasis_word": "strong",
            },
            {
                "text": "While others waste energy arguing, you conserve yours.",
                "visual_keywords": "man training gym dark silhouette weights",
                "emphasis_word": "conserve",
            },
            {
                "text": "While they react, you respond with precision.",
                "visual_keywords": "archer dark silhouette focus aim",
                "emphasis_word": "precision",
            },
            {
                "text": "That's power. Real power.",
                "visual_keywords": "dark ocean storm waves cinematic",
                "emphasis_word": "power",
            },
            {
                "text": "The kind of power that no one can take from you.",
                "visual_keywords": "dark storm clouds cinematic dramatic",
                "emphasis_word": "take",
            },
            {
                "text": "Because it comes from within.",
                "visual_keywords": "dark fire flames cinematic abstract",
                "emphasis_word": "within",
            },
            {
                "text": "So starting today, choose silence over noise.",
                "visual_keywords": "man meditating dark room calm",
                "emphasis_word": "silence",
            },
            {
                "text": "Choose discipline over emotion.",
                "visual_keywords": "athlete running dark silhouette training",
                "emphasis_word": "discipline",
            },
            {
                "text": "Choose growth over approval.",
                "visual_keywords": "dark workspace laptop night coding",
                "emphasis_word": "growth",
            },
            {
                "text": "The world will try to make you loud. Stay quiet.",
                "visual_keywords": "dark city crowd night aerial busy",
                "emphasis_word": "quiet",
            },
            {
                "text": "You were built for greatness.",
                "visual_keywords": "luxury dark car night driving cinematic",
                "emphasis_word": "greatness",
            },
            {
                "text": "Now go out there and prove it.",
                "visual_keywords": "man walking away dark city silhouette night",
                "emphasis_word": "prove",
            },
        ],

        # =====================================================
        # SCRIPT: Why high-value people walk alone
        # ~26 segments, ~185 words -> ~70s at 2.62 wps
        # =====================================================
        "Why high-value people walk alone": [
            {
                "text": "If you're always alone, this message is for you.",
                "visual_keywords": "man walking alone dark street night",
                "emphasis_word": "alone",
            },
            {
                "text": "High-value people don't have big friend groups.",
                "visual_keywords": "solitary man dark aesthetic",
                "emphasis_word": "High-value",
            },
            {
                "text": "Not because they can't socialize.",
                "visual_keywords": "crowd busy people dark city",
                "emphasis_word": "socialize",
            },
            {
                "text": "But because they refuse to lower their standards.",
                "visual_keywords": "man in suit looking down dark",
                "emphasis_word": "standards",
            },
            {
                "text": "They've learned that most people drain your energy.",
                "visual_keywords": "tired person dark room moody",
                "emphasis_word": "drain",
            },
            {
                "text": "Most people gossip instead of building.",
                "visual_keywords": "people whispering dark scene",
                "emphasis_word": "gossip",
            },
            {
                "text": "They complain instead of creating.",
                "visual_keywords": "dark workspace laptop night",
                "emphasis_word": "creating",
            },
            {
                "text": "And they criticize instead of growing.",
                "visual_keywords": "plant growing dark time lapse",
                "emphasis_word": "growing",
            },
            {
                "text": "A lion doesn't lose sleep over the opinion of sheep.",
                "visual_keywords": "lion portrait dark dramatic",
                "emphasis_word": "lion",
            },
            {
                "text": "Your solitude is not loneliness.",
                "visual_keywords": "man on mountain top dark sky",
                "emphasis_word": "solitude",
            },
            {
                "text": "It's a sign that you've outgrown your environment.",
                "visual_keywords": "dark city skyline night cinematic",
                "emphasis_word": "outgrown",
            },
            {
                "text": "Every great person in history walked a lonely path.",
                "visual_keywords": "dark road empty night cinematic",
                "emphasis_word": "great",
            },
            {
                "text": "They were misunderstood. They were doubted.",
                "visual_keywords": "rain dark window cinematic night drops",
                "emphasis_word": "doubted",
            },
            {
                "text": "But they never stopped moving forward.",
                "visual_keywords": "man running dark tunnel silhouette",
                "emphasis_word": "forward",
            },
            {
                "text": "And neither should you.",
                "visual_keywords": "dark storm clouds cinematic dramatic",
                "emphasis_word": "neither",
            },
            {
                "text": "The right people will find you.",
                "visual_keywords": "sunrise dark clouds dramatic",
                "emphasis_word": "find",
            },
            {
                "text": "But only when you stop settling for the wrong ones.",
                "visual_keywords": "man walking away dramatic dark",
                "emphasis_word": "settling",
            },
            {
                "text": "So walk alone if you have to.",
                "visual_keywords": "lone wolf dark forest",
                "emphasis_word": "alone",
            },
            {
                "text": "Protect your peace. Guard your energy.",
                "visual_keywords": "dark ocean waves calm night",
                "emphasis_word": "peace",
            },
            {
                "text": "Because one day, they will all see what you were building in silence.",
                "visual_keywords": "dark skyscraper night lights cinematic",
                "emphasis_word": "building",
            },
            {
                "text": "The loneliness you feel right now is temporary.",
                "visual_keywords": "dark corridor shadows cinematic moody",
                "emphasis_word": "temporary",
            },
            {
                "text": "But the strength you are building is permanent.",
                "visual_keywords": "man training gym dark silhouette weights",
                "emphasis_word": "permanent",
            },
            {
                "text": "Stay patient. Stay focused. Stay hungry.",
                "visual_keywords": "man meditating dark room calm",
                "emphasis_word": "hungry",
            },
            {
                "text": "Your time is coming.",
                "visual_keywords": "luxury dark car night driving cinematic",
                "emphasis_word": "coming",
            },
            {
                "text": "And when it does, you'll be ready.",
                "visual_keywords": "man walking away dark city silhouette night",
                "emphasis_word": "ready",
            },
        ],

        # =====================================================
        # SCRIPT: The art of not reacting
        # ~27 segments, ~185 words -> ~70s at 2.62 wps
        # =====================================================
        "The art of not reacting": [
            {
                "text": "Stop reacting to everything. Here's why.",
                "visual_keywords": "calm water dark reflection",
                "emphasis_word": "reacting",
            },
            {
                "text": "Every time you react emotionally, you give away your power.",
                "visual_keywords": "chess king falling dark",
                "emphasis_word": "power",
            },
            {
                "text": "The person who made you angry now controls you.",
                "visual_keywords": "puppet strings dark artistic",
                "emphasis_word": "controls",
            },
            {
                "text": "That's exactly what they wanted.",
                "visual_keywords": "dark silhouette manipulation",
                "emphasis_word": "wanted",
            },
            {
                "text": "But when you don't react, something shifts.",
                "visual_keywords": "still man dark room confident",
                "emphasis_word": "shifts",
            },
            {
                "text": "You become unpredictable.",
                "visual_keywords": "dark fog mysterious cinematic",
                "emphasis_word": "unpredictable",
            },
            {
                "text": "And unpredictable people cannot be manipulated.",
                "visual_keywords": "lion staring dark intense",
                "emphasis_word": "manipulated",
            },
            {
                "text": "Think about the people who tried to break you.",
                "visual_keywords": "dark storm clouds cinematic dramatic",
                "emphasis_word": "break",
            },
            {
                "text": "They used your reactions against you.",
                "visual_keywords": "chess dark hand moving piece strategic",
                "emphasis_word": "reactions",
            },
            {
                "text": "Every outburst was a victory for them.",
                "visual_keywords": "dark boxing ring empty cinematic",
                "emphasis_word": "victory",
            },
            {
                "text": "But that ends now.",
                "visual_keywords": "man standing dark silhouette powerful",
                "emphasis_word": "now",
            },
            {
                "text": "Train yourself to pause before you speak.",
                "visual_keywords": "man meditating dark room",
                "emphasis_word": "pause",
            },
            {
                "text": "Breathe before you respond.",
                "visual_keywords": "dark ocean waves slow motion",
                "emphasis_word": "Breathe",
            },
            {
                "text": "Let them wonder what you're thinking.",
                "visual_keywords": "dark mysterious man silhouette window",
                "emphasis_word": "wonder",
            },
            {
                "text": "The most powerful response is no response at all.",
                "visual_keywords": "empty dark room silence cinematic",
                "emphasis_word": "powerful",
            },
            {
                "text": "When you master this, nothing can touch you.",
                "visual_keywords": "dark mountain peak clouds cinematic",
                "emphasis_word": "master",
            },
            {
                "text": "No opinion. No insult. No betrayal.",
                "visual_keywords": "rain dark window cinematic night drops",
                "emphasis_word": "betrayal",
            },
            {
                "text": "You become untouchable.",
                "visual_keywords": "wolf dark forest night walking",
                "emphasis_word": "untouchable",
            },
            {
                "text": "And that scares the people who once controlled you.",
                "visual_keywords": "dark corridor shadows cinematic moody",
                "emphasis_word": "scares",
            },
            {
                "text": "Because they lost their power over you.",
                "visual_keywords": "chess pieces dark cinematic board",
                "emphasis_word": "lost",
            },
            {
                "text": "So start today. Control your emotions.",
                "visual_keywords": "man training gym dark silhouette weights",
                "emphasis_word": "Control",
            },
            {
                "text": "Let your silence do the talking.",
                "visual_keywords": "dark city skyline night rooftop cinematic",
                "emphasis_word": "silence",
            },
            {
                "text": "Let your peace be your power.",
                "visual_keywords": "dark ocean waves calm night cinematic",
                "emphasis_word": "peace",
            },
            {
                "text": "You are stronger than you think.",
                "visual_keywords": "athlete running dark silhouette training",
                "emphasis_word": "stronger",
            },
            {
                "text": "You have survived every bad day so far.",
                "visual_keywords": "dark fire flames cinematic abstract",
                "emphasis_word": "survived",
            },
            {
                "text": "And that's proof enough that you can handle anything.",
                "visual_keywords": "luxury dark car night driving cinematic",
                "emphasis_word": "anything",
            },
            {
                "text": "Now go prove it to the world.",
                "visual_keywords": "man walking away dark city silhouette night",
                "emphasis_word": "prove",
            },
        ],

        # =====================================================
        # SCRIPT: The hidden envy around you
        # ~24 segments, ~175 words -> ~70s at 0.68 speed
        # Actual rate measured: 2.62 words/sec at 0.68 speed
        # Concept: close people secretly jealous, move in silence
        # =====================================================
        "The hidden envy around you": [
            {
                "text": "The people clapping for you in public are the same ones praying for your downfall in private.",
                "visual_keywords": "dark crowd silhouette night cinematic",
                "emphasis_word": "downfall",
            },
            {
                "text": "That's the truth nobody warns you about.",
                "visual_keywords": "man silhouette dark shadow mysterious",
                "emphasis_word": "truth",
            },
            {
                "text": "Not every smile is genuine.",
                "visual_keywords": "dark mask artistic cinematic moody",
                "emphasis_word": "genuine",
            },
            {
                "text": "Not every friend wants to see you win.",
                "visual_keywords": "chess pieces dark cinematic board",
                "emphasis_word": "win",
            },
            {
                "text": "Some people stay close just to watch you fail.",
                "visual_keywords": "dark corridor shadows cinematic moody",
                "emphasis_word": "fail",
            },
            {
                "text": "They don't celebrate your progress. They study it.",
                "visual_keywords": "dark smoke fog cinematic abstract",
                "emphasis_word": "study",
            },
            {
                "text": "And quietly, they resent you for it.",
                "visual_keywords": "rain dark window cinematic night drops",
                "emphasis_word": "resent",
            },
            {
                "text": "This is why you should never announce your plans.",
                "visual_keywords": "man back view walking dark hallway",
                "emphasis_word": "never",
            },
            {
                "text": "Never reveal your next move.",
                "visual_keywords": "chess hand moving piece dark strategic",
                "emphasis_word": "reveal",
            },
            {
                "text": "Share your dreams with the wrong person, and they will quietly work against you.",
                "visual_keywords": "dark silhouette manipulation puppet",
                "emphasis_word": "against",
            },
            {
                "text": "They will disguise their jealousy as concern.",
                "visual_keywords": "dark corridor shadows cinematic moody",
                "emphasis_word": "jealousy",
            },
            {
                "text": "So move in silence. Let your results make the noise.",
                "visual_keywords": "lion adult male dark wild savanna",
                "emphasis_word": "silence",
            },
            {
                "text": "Work when nobody is watching.",
                "visual_keywords": "man training gym dark silhouette weights",
                "emphasis_word": "Work",
            },
            {
                "text": "Build when nobody believes in you.",
                "visual_keywords": "dark workspace laptop night coding",
                "emphasis_word": "Build",
            },
            {
                "text": "Let discipline be your voice.",
                "visual_keywords": "athlete running dark silhouette training",
                "emphasis_word": "discipline",
            },
            {
                "text": "And let your success be your loudest answer.",
                "visual_keywords": "luxury dark car night driving cinematic",
                "emphasis_word": "success",
            },
            {
                "text": "One day, everyone who doubted you will wish they believed in you sooner.",
                "visual_keywords": "dark city skyline night rooftop cinematic",
                "emphasis_word": "believed",
            },
            {
                "text": "But by then, you won't need their approval.",
                "visual_keywords": "man standing dark silhouette powerful rooftop",
                "emphasis_word": "approval",
            },
            {
                "text": "Because you learned to trust yourself when no one else did.",
                "visual_keywords": "dark mountain peak clouds cinematic",
                "emphasis_word": "yourself",
            },
            {
                "text": "You don't need anyone's permission to become great.",
                "visual_keywords": "wolf dark forest night walking powerful",
                "emphasis_word": "great",
            },
            {
                "text": "Keep going. Silently. Relentlessly. Unstoppably.",
                "visual_keywords": "man walking away dark city silhouette night",
                "emphasis_word": "Unstoppably",
            },
        ],

        # =====================================================
        # SCRIPT: Comfort is killing your potential
        # ~24 segments, ~170 words -> ~72s at 2.35 wps (0.83 speed)
        # Arc: comfort trap (warm) → wake-up call → action (dark)
        # =====================================================
        "Comfort is killing your potential": [
            {
                "text": "Comfort is the biggest threat to your growth.",
                "visual_keywords": "person sitting couch scrolling phone lazy",
                "emphasis_word": "threat",
            },
            {
                "text": "It doesn't look dangerous.",
                "visual_keywords": "cozy bed blanket coffee morning warm",
                "emphasis_word": "dangerous",
            },
            {
                "text": "It feels safe. It feels easy.",
                "visual_keywords": "comfortable room relaxing sofa calm",
                "emphasis_word": "easy",
            },
            {
                "text": "But slowly, it keeps you exactly where you are.",
                "visual_keywords": "person sitting alone dark room still",
                "emphasis_word": "exactly",
            },
            {
                "text": "Day after day. Week after week. Nothing changes.",
                "visual_keywords": "time lapse room day night light changing",
                "emphasis_word": "Nothing",
            },
            {
                "text": "Your brain is wired to avoid pain.",
                "visual_keywords": "person staring blankly dark abstract moody",
                "emphasis_word": "wired",
            },
            {
                "text": "It chooses comfort over progress. Every single time.",
                "visual_keywords": "person closing laptop procrastination dark",
                "emphasis_word": "progress",
            },
            {
                "text": "That's the trap.",
                "visual_keywords": "clock ticking close up dark cinematic",
                "emphasis_word": "trap",
            },
            {
                "text": "You keep telling yourself tomorrow.",
                "visual_keywords": "calendar pages flipping time passing fast",
                "emphasis_word": "tomorrow",
            },
            {
                "text": "But tomorrow never comes.",
                "visual_keywords": "crowd walking fast motion city busy dark",
                "emphasis_word": "never",
            },
            {
                "text": "You don't feel it at first.",
                "visual_keywords": "person tired dark moody exhausted fading",
                "emphasis_word": "feel",
            },
            {
                "text": "Your energy drops. Your standards drop.",
                "visual_keywords": "messy room dark abandoned unused",
                "emphasis_word": "standards",
            },
            {
                "text": "And one day you wake up and realize years have passed.",
                "visual_keywords": "mirror reflection man staring dark moody",
                "emphasis_word": "years",
            },
            {
                "text": "Nothing changed. Because you never did.",
                "visual_keywords": "empty room dark silence cinematic",
                "emphasis_word": "changed",
            },
            {
                "text": "So how do you break free?",
                "visual_keywords": "dark screen man eye contact intense close",
                "emphasis_word": "free",
            },
            {
                "text": "You choose discomfort. On purpose.",
                "visual_keywords": "person waking up dark room early morning",
                "emphasis_word": "discomfort",
            },
            {
                "text": "You wake up when your body says stay in bed.",
                "visual_keywords": "cold shower water dark morning cinematic",
                "emphasis_word": "wake",
            },
            {
                "text": "You train when your mind says rest.",
                "visual_keywords": "gym training dark silhouette weights heavy",
                "emphasis_word": "train",
            },
            {
                "text": "You work when nobody is watching.",
                "visual_keywords": "working alone laptop dark night focused",
                "emphasis_word": "work",
            },
            {
                "text": "You push through when everything tells you to stop.",
                "visual_keywords": "running rain dark cinematic intense",
                "emphasis_word": "push",
            },
            {
                "text": "Because greatness was never built in comfort.",
                "visual_keywords": "athlete training dark intense powerful",
                "emphasis_word": "greatness",
            },
            {
                "text": "It was built in the moments you wanted to quit but didn't.",
                "visual_keywords": "man pushing through dark training exhausted",
                "emphasis_word": "quit",
            },
            {
                "text": "So start now. Not tomorrow. Right now.",
                "visual_keywords": "man tying shoes dark morning workout ready",
                "emphasis_word": "now",
            },
            {
                "text": "Your future self is counting on you.",
                "visual_keywords": "man walking forward sunrise silhouette dark cinematic",
                "emphasis_word": "counting",
            },
        ],

    }

    # --- Return matching script or default ---
    if topic in scripts:
        return scripts[topic]

    # --- Fallback: return the silence and power script ---
    return scripts["The psychology of silence and power"]


def get_all_visual_keywords(script):
    """
    # Extracts all visual keywords from a script
    # Used to batch-download footage before assembly
    """
    return [segment["visual_keywords"] for segment in script]


def get_script_text(script):
    """
    # Returns the full script as a single string
    # Used for generating the voiceover
    """
    return " ".join([segment["text"] for segment in script])


# --- Quick test ---
if __name__ == "__main__":
    script, topic = generate_script("The psychology of silence and power")
    print(f"\nTopic: {topic}")
    print(f"Segments: {len(script)}")
    print(f"\nFull script:\n{get_script_text(script)}")
