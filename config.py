import os

# ============================================================
# CONFIGURATION - CLOUD VERSION (Hugging Face Spaces)
# API keys come from HF Spaces Secrets (environment variables)
# ============================================================

# --- API Keys (from HF Spaces Secrets) ---
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()
FREESOUND_API_KEY = os.getenv("FREESOUND_API_KEY", "").strip()

# --- ElevenLabs Voice Settings ---
# Voice: Adam - Deep English Story Voice
ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
VOICE_SETTINGS = {
    "stability": 0.62,
    "similarity_boost": 0.80,
    "style": 0.0,
    "use_speaker_boost": True,
}
VOICE_SPEED = 0.83

# --- Video Settings ---
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_FORMAT = "mp4"

# --- Caption Style ---
CAPTION_FONT_SIZE = 65
CAPTION_COLOR = "white"
CAPTION_HIGHLIGHT_COLOR = "#E8A817"
CAPTION_FONT = "Arial-Bold"
CAPTION_POSITION = ("center", 0.83)
CAPTION_STROKE_COLOR = "black"
CAPTION_STROKE_WIDTH = 2

# --- Color Grading ---
BRIGHTNESS_FACTOR = 0.55
SATURATION_FACTOR = 0.45
CONTRAST_FACTOR = 1.20

# --- Audio Settings ---
VOICEOVER_VOLUME = 1.0
MUSIC_VOLUME = 0.32

# --- Paths (cloud: use /tmp for writable storage) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
MUSIC_DIR = os.path.join("/tmp", "luminous_music")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
OUTPUT_DIR = os.path.join("/tmp", "luminous_output")
TEMP_DIR = os.path.join("/tmp", "luminous_temp")

# --- Logo Outro ---
LOGO_DURATION = 3

# --- Clip Settings ---
MIN_CLIP_DURATION = 2.5
MAX_CLIP_DURATION = 10

# --- Pexels Search Settings ---
PEXELS_ORIENTATION = "portrait"
PEXELS_SIZE = "large"
PEXELS_PER_PAGE = 10

# --- Trending Topics ---
TRENDING_TOPICS = [
    "The psychology of silence and power",
    "Why high-value people walk alone",
    "Dark psychology of manipulation tactics",
    "The quiet leader vs the loud victim",
    "Why loneliness is a superpower",
    "The psychology behind fake friends",
    "Signs of a mentally strong person",
    "Why successful people are quiet",
    "The art of not reacting",
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
    "Dark truths about human nature",
    "Why being feared is better than being loved",
    "The stoic mindset that changes your life",
    "Psychology of body language and dominance",
    "Why your silence terrifies them",
    "The power of walking away",
    "How narcissists manipulate you",
    "The mindset of a high-value man",
    "Why you attract toxic people",
    "The psychology of winning alone",
    "Why most people will never succeed",
    "The hidden envy around you",
    "Comfort is killing your potential",
]
