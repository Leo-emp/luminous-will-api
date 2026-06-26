# ============================================================
# CONTENT TYPE DEFINITIONS
# Single source of truth for all 4 content types.
# Each type has: topics, visual style, accent color, music mood,
# Gemini persona, visual subjects, avoid lists, and hashtag sets.
#
# Other modules import from here — never duplicate type data.
# ============================================================

# --- All 4 content types ---
# Keys are used as identifiers throughout the pipeline and web app
CONTENT_TYPES = {

    # ── Dark Motivation ─────────────────────────────────────
    # The original Luminous Will style — intense, aggressive, fire energy
    "dark_motivation": {
        "name": "Dark Motivation",
        "accent_color": "#E8A817",
        "music_mood": "intense",
        "visual_style": "dark cinematic",
        # Curated stock footage subjects that match this type
        "visual_subjects": [
            "lion dark savanna cinematic",
            "wolf dark forest night",
            "man training gym dark silhouette",
            "boxing ring dark cinematic",
            "suited man walking dark city",
            "dark cityscape night aerial",
            "storm clouds dramatic cinematic",
            "fire flames dark abstract",
        ],
        # Subjects that would feel wrong for this type
        "visual_avoid": ["ancient ruins", "statues", "money", "luxury cars", "temple"],
        # Gemini persona for script generation
        "gemini_persona": (
            "You are a ruthless motivational voice. Stoic, commanding, no-nonsense. "
            "Short punchy sentences. Dark, intense energy. The tone of someone who has "
            "seen the worst and emerged stronger. Speak in universal truths. Never say "
            "'I' or 'we'. Use 'you' and 'they'. No fluff, no clichés like 'grind', "
            "'hustle', or 'manifest'. No questions to the audience."
        ),
        # Platform-specific hashtag sets for auto-posting captions
        "hashtags": {
            "youtube": ["#darkmotivation", "#motivation", "#mindset", "#selfimprovement", "#discipline"],
            "tiktok": ["#darkmotivation", "#mindset", "#discipline", "#fyp", "#mentaltoughness"],
            "instagram": ["#darkmotivation", "#mindset", "#selfimprovement", "#growthmindset", "#motivation"],
            "facebook": ["#motivation", "#mindset", "#selfimprovement"],
        },
        # Seed topics — each will only be used once, ever
        "topics": [
            "The psychology of silence and power",
            "Why high-value people walk alone",
            "The art of not reacting",
            "The hidden envy around you",
            "Comfort is killing your potential",
            "The quiet leader vs the loud victim",
            "Why loneliness is a superpower",
            "The psychology behind fake friends",
            "Signs of a mentally strong person",
            "Why successful people are quiet",
            "Psychology of self-discipline",
            "Why people disrespect you (and how to stop it)",
            "The dark truth about comfort zones",
            "How emotional control changes everything",
            "The psychology of revenge vs moving on",
            "Why nice people finish last (the truth)",
            "Signs you are becoming dangerous (in a good way)",
            "The wolf mentality - psychology of lone wolves",
            "Why you should never explain yourself",
            "The 48 laws of power - key lessons",
        ],
    },

    # ── Stoic Philosophy ────────────────────────────────────
    # Ancient wisdom, measured delivery, marble/stone aesthetic
    "stoic_philosophy": {
        "name": "Stoic Philosophy",
        "accent_color": "#7B9EB8",
        "music_mood": "reflective",
        "visual_style": "ancient cinematic",
        "visual_subjects": [
            "marble statue dark cinematic",
            "ancient ruins columns shadow",
            "mountain peak fog dark",
            "rain stone surface cinematic",
            "old book candle dark room",
            "temple columns shadow cinematic",
            "ocean horizon calm dark",
            "solitary tree storm dark",
        ],
        "visual_avoid": ["gym", "boxing", "luxury cars", "money", "modern city", "skyscraper"],
        "gemini_persona": (
            "You are a stoic philosopher speaking timeless truths from the ancient world. "
            "Measured, deliberate, wise. Reference Marcus Aurelius, Epictetus, and Seneca "
            "naturally — not as direct quotes, but as woven wisdom. Never say 'I' or 'we'. "
            "Use 'you' and 'they'. No modern slang. No questions to the audience. "
            "Speak as if carving words into marble — every sentence must be worth preserving."
        ),
        "hashtags": {
            "youtube": ["#stoicism", "#stoicphilosophy", "#marcusaurelius", "#wisdom", "#philosophy"],
            "tiktok": ["#stoicism", "#stoicquotes", "#marcusaurelius", "#philosophy", "#fyp"],
            "instagram": ["#stoicism", "#stoicphilosophy", "#marcusaurelius", "#ancientwisdom", "#philosophy"],
            "facebook": ["#stoicism", "#philosophy", "#wisdom"],
        },
        "topics": [
            "Marcus Aurelius on controlling your emotions",
            "Why the Stoics chose discomfort on purpose",
            "Epictetus on what you can and cannot control",
            "The Stoic response to betrayal",
            "Why Seneca said wealth is a test",
            "How to think like a Roman emperor",
            "The Stoic art of letting go",
            "Why Marcus Aurelius journaled every night",
            "Amor fati - how to love your fate",
            "The dichotomy of control explained",
            "Why Stoics trained for the worst day",
            "Memento mori - the power of remembering death",
            "How Epictetus turned slavery into philosophy",
            "The Stoic way to handle insults",
            "Why ancient Rome valued silence over speech",
            "Seneca's letters on the shortness of life",
            "The Stoic practice of voluntary hardship",
            "How to be unshakeable like Marcus Aurelius",
            "Why the Stoics said anger is weakness",
            "The four Stoic virtues that build an unbreakable mind",
        ],
    },

    # ── Success & Wealth Mindset ────────────────────────────
    # Luxury aesthetic, cold strategy, psychology of money
    "wealth_mindset": {
        "name": "Success & Wealth Mindset",
        "accent_color": "#C9A84C",
        "music_mood": "powerful",
        "visual_style": "luxury dark cinematic",
        "visual_subjects": [
            "luxury car dark night driving",
            "skyline penthouse dark cinematic",
            "suit businessman dark office",
            "watch luxury dark close up",
            "private jet dark cinematic",
            "boardroom dark empty cinematic",
            "skyscraper night lights dark",
            "financial chart dark screen",
        ],
        "visual_avoid": ["ancient ruins", "statues", "wolves", "forest", "temple", "boxing"],
        "gemini_persona": (
            "You are a cold, calculated wealth strategist who speaks from experience. "
            "No 'grind' or 'hustle' clichés. Talk about systems, leverage, compounding, "
            "and the psychology of money. Never say 'I' or 'we'. Use 'you' and 'they'. "
            "Speak like someone who built wealth quietly and now shares the blueprint. "
            "No motivational fluff — only cold, actionable truths about building wealth."
        ),
        "hashtags": {
            "youtube": ["#wealthmindset", "#financialfreedom", "#money", "#investing", "#success"],
            "tiktok": ["#wealthmindset", "#moneymindset", "#financialliteracy", "#success", "#fyp"],
            "instagram": ["#wealthmindset", "#financialfreedom", "#moneymindset", "#investing", "#success"],
            "facebook": ["#wealth", "#success", "#money"],
        },
        "topics": [
            "Why the rich think differently than the poor",
            "The psychology of financial discipline",
            "How compound habits build empires",
            "Why your network determines your net worth",
            "The wealth trap of looking rich vs being rich",
            "How the wealthy use time as their greatest asset",
            "Why 95% of people will never build real wealth",
            "The psychology behind delayed gratification",
            "How to build systems that make money while you sleep",
            "Why the rich read and the poor watch TV",
            "The invisible tax of bad financial decisions",
            "How leverage separates the rich from the middle class",
            "Why most lottery winners go broke",
            "The psychology of scarcity vs abundance thinking",
            "How the wealthy protect their energy",
            "Why financial education is more valuable than a degree",
            "The compounding effect of daily 1% improvements",
            "How to think in assets not liabilities",
            "Why the rich embrace risk and the poor avoid it",
            "The silent habits of self-made millionaires",
        ],
    },

    # ── Dark Psychology ─────────────────────────────────────
    # Noir aesthetic, clinical analysis, psychological edge
    "dark_psychology": {
        "name": "Dark Psychology",
        "accent_color": "#B83C3C",
        "music_mood": "dark",
        "visual_style": "shadow noir cinematic",
        "visual_subjects": [
            "chess pieces dark cinematic board",
            "shadow silhouette dark corridor",
            "mask dark artistic cinematic",
            "puppet strings dark manipulation",
            "dark corridor shadows cinematic",
            "smoke dark abstract cinematic",
            "mirror reflection dark moody",
            "rain soaked street dark night",
        ],
        "visual_avoid": ["gym", "luxury cars", "ancient ruins", "nature", "forest", "mountain"],
        "gemini_persona": (
            "You are a cold analyst of human darkness. Clinical, unsettling, precise. "
            "Break down manipulation tactics, body language tells, and power dynamics "
            "like a forensic psychologist. Never say 'I' or 'we'. Use 'you' and 'they'. "
            "No moral judgments — present the psychology neutrally. Let the listener "
            "draw their own conclusions. Every sentence should feel like it's revealing "
            "something dangerous."
        ),
        "hashtags": {
            "youtube": ["#darkpsychology", "#psychology", "#manipulation", "#bodylanguage", "#mindgames"],
            "tiktok": ["#darkpsychology", "#psychologyfacts", "#manipulation", "#bodylanguage", "#fyp"],
            "instagram": ["#darkpsychology", "#psychologyfacts", "#manipulation", "#humanpsychology", "#mindgames"],
            "facebook": ["#psychology", "#darkpsychology", "#humanpsychology"],
        },
        "topics": [
            "How narcissists trap you without you knowing",
            "The 7 signs someone is manipulating you",
            "Dark psychology of first impressions",
            "Why psychopaths are more successful than you think",
            "The manipulation tactic called gaslighting explained",
            "How to read someone in 5 seconds",
            "The dark triad personality and why it attracts people",
            "Body language signals that reveal hidden intentions",
            "How social media is designed to manipulate you",
            "The psychology of love bombing",
            "Why toxic people target empaths",
            "How cults use psychology to control members",
            "The Machiavellian tactics used in everyday life",
            "Psychological tricks used in advertising and sales",
            "How to detect a liar using micro-expressions",
            "The psychology of power and who really has it",
            "Why people stay in toxic relationships",
            "How fear is weaponized to control behavior",
            "The psychology behind passive-aggressive behavior",
            "Dark persuasion techniques used by politicians",
        ],
    },
}


def get_content_type(type_key):
    """
    # Returns the full config dict for a content type
    # Raises KeyError if the type_key doesn't exist
    """
    if type_key not in CONTENT_TYPES:
        raise KeyError(f"Unknown content type: {type_key}. Valid: {list(CONTENT_TYPES.keys())}")
    return CONTENT_TYPES[type_key]


def get_all_topics(type_key):
    """
    # Returns the seed topics list for a content type
    """
    return get_content_type(type_key)["topics"]


def get_all_type_keys():
    """
    # Returns all content type keys: ["dark_motivation", "stoic_philosophy", ...]
    """
    return list(CONTENT_TYPES.keys())
