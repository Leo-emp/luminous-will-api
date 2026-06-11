import os
import numpy as np
from PIL import Image
import config

# ============================================================
# BRAND REFERENCE MODULE
# ============================================================
# This module contains the EXACT specifications extracted from
# real Luminous Will videos by analyzing them frame-by-frame.
#
# Reference frames are stored in assets/references/ so the
# pipeline can always be calibrated against the real brand.
#
# These values were measured directly from:
#   - "The quiet leader vs the loud victim.mp4"
#   - "High value solitude.mp4"
# ============================================================


# ============================================================
# VIDEO SPECIFICATIONS (measured from actual videos)
# ============================================================

VIDEO_SPECS = {
    # --- Resolution and format ---
    "width": 1080,                  # exact pixel width
    "height": 1920,                 # exact pixel height
    "aspect_ratio": "9:16",         # vertical/portrait format
    "fps": 30,                      # frames per second (~29.98 rounded up)
    "codec": "libx264",             # H.264 encoding
    "audio_codec": "aac",           # AAC audio
    "bitrate": "12000k",            # ~10-12 Mbps matches the originals
    "duration_range": (60, 90),     # videos are typically 60-90 seconds

    # --- These match the original video file quality ---
    # "quiet leader" was 10,819 kbps
    # "high value solitude" was 12,374 kbps
    # We use 12,000 kbps to match or exceed both
}


# ============================================================
# COLOR GRADING SPECS (measured from actual video frames)
# ============================================================

COLOR_GRADE_SPECS = {
    # --- Brightness ---
    # Measured: avg brightness is 24-25% (very dark)
    # On a 0-255 scale: avg V channel = 60-63
    # To achieve this from normal footage (avg ~50% brightness):
    "target_brightness_pct": 24,     # target: 24% brightness
    "brightness_factor": 0.55,       # multiply to darken (was 0.65, too bright)

    # --- Saturation ---
    # "quiet leader": 10% saturation (nearly B&W)
    # "high value solitude": 47% saturation (warm animal tones kept)
    # Average: ~28% saturation
    # The videos mix desaturated scenes with warm-toned wildlife
    "target_saturation_pct": 28,     # target: 28% saturation
    "saturation_factor": 0.45,       # reduce saturation (was 0.55)

    # --- Contrast ---
    # Dark shadows with some highlight detail
    "contrast_factor": 1.20,         # slightly higher contrast (was 1.15)

    # --- Split toning ---
    # Shadows: cool/blue tint
    # Highlights: warm/amber tint (especially on lion footage)
    "shadow_blue_tint": 0.04,        # blue in shadows (was 0.03)
    "highlight_red_tint": 0.03,      # warm highlights (was 0.02)
    "highlight_green_tint": 0.015,   # warm highlights (was 0.01)
}


# ============================================================
# CAPTION STYLE SPECS (measured from actual video frames)
# ============================================================

CAPTION_SPECS = {
    # --- Position ---
    # Measured: captions sit at 80-86% from top of frame
    # Center of caption text: 83.2% from top
    "y_position_pct": 0.83,          # 83% from top (was 0.82)

    # --- Font ---
    # Font appears to be a clean sans-serif, bold weight
    # Approximate size relative to frame width: ~6-7% of width per character
    "font_size": 65,                 # slightly smaller than before for cleaner look
    "font_style": "bold",            # always bold
    "font_family": "Arial-Bold",     # closest match to the original

    # --- Colors ---
    # Normal text: pure white with slight transparency feel
    "text_color": "white",           # #FFFFFF
    # Highlighted word: warm amber/gold
    "highlight_color": "#E8A817",    # slightly more orange than pure gold
    # Stroke/outline: black for readability
    "stroke_color": "black",         # #000000
    "stroke_width": 2,              # thinner stroke (was 3) - cleaner look

    # --- Layout ---
    # Captions show 3-6 words at a time
    # Centered horizontally
    # Max 2 lines of text
    "words_per_chunk": 4,            # 4 words shown at a time
    "max_lines": 2,                  # wrap to max 2 lines
    "line_spacing": 8,               # pixels between lines
}


# ============================================================
# CLIP PACING SPECS (measured from scene change analysis)
# ============================================================

PACING_SPECS = {
    # --- Clip durations ---
    # Measured from "quiet leader":
    #   Average: 7.2s, Median: 5.4s
    #   Range: 1.8s to 23.8s
    #   Most clips: 3-8 seconds
    "avg_clip_duration": 5.5,        # target average seconds per clip
    "min_clip_duration": 2.5,        # minimum clip length
    "max_clip_duration": 10.0,       # maximum clip length

    # --- Transitions ---
    # No visible hard cuts with effects - clean cuts between clips
    # Some clips have natural motion (slow pan, zoom)
    "transition_type": "cut",        # clean cuts, no fancy transitions

    # --- Pacing feel ---
    # Clips change roughly every sentence or thought
    # Faster cuts during emotional peaks
    # Longer holds on powerful imagery (lions, chess)
}


# ============================================================
# AUDIO SPECS
# ============================================================

AUDIO_SPECS = {
    # --- Voiceover ---
    # Clear, dominant in the mix
    # Deep, calm, authoritative male voice
    "voiceover_volume": 1.0,         # full volume, never reduced

    # --- Background music ---
    # Loud enough to feel encouraging and motivational
    # Dramatic/cinematic strings, piano, or epic orchestral
    # NEVER competes with the voiceover - voice is always crystal clear
    # Voice is ~7x louder than music at this setting
    "music_volume": 0.15,            # 15% volume - encouraging but voice stays clear
    "music_fade_in": 2.0,            # 2 second fade in
    "music_fade_out": 3.0,           # 3 second fade out (longer for smooth ending)

    # --- Logo outro ---
    # Silent or very faint music during logo
    "outro_duration": 3,             # 3 seconds of logo at the end
}


# ============================================================
# VISUAL SEARCH STRATEGY
# ============================================================

VISUAL_STRATEGY = {
    # --- What makes a clip "on brand" ---
    # 1. Dark overall tone (even before color grading)
    # 2. Cinematic composition (shallow depth of field)
    # 3. Subjects: lions, chess, suited men, dark cityscapes,
    #    solitary figures, rain, shadows
    # 4. Portrait/vertical orientation preferred
    # 5. No bright, colorful, or cheerful footage

    # --- Search keyword modifiers ---
    # Always append these to improve search results
    "keyword_modifiers": ["dark", "cinematic", "moody", "dramatic"],

    # --- Preferred visual themes (from analyzing both videos) ---
    "brand_themes": [
        "lion",                      # brand animal, used frequently
        "chess",                     # strategy/intelligence metaphor
        "businessman suit dark",     # success/power imagery
        "man alone night",           # solitude/independence
        "dark city night",           # urban isolation
        "rain dark moody",           # emotional atmosphere
        "shadows silhouette",        # mystery/power
        "wolf dark",                 # lone wolf mentality
        "mountain dark sky",         # achievement/solitude
        "ocean dark waves",          # emotional depth
        "gym dark aesthetic",        # discipline/strength
        "boxing dark cinematic",     # fighting spirit/power
        "running dark cinematic",    # discipline/endurance
        "modern city architecture",  # ambition/modern power
    ],

    # --- Footage to AVOID ---
    "avoid_themes": [
        "bright", "colorful", "happy", "sunny", "beach",
        "party", "celebration", "kids", "cartoon", "comedy",
        "food", "cooking", "dance", "wedding", "flowers",
    ],
}


# ============================================================
# REFERENCE FRAME PATHS
# ============================================================

REFERENCE_DIR = os.path.join(config.ASSETS_DIR, "references")

REFERENCE_FRAMES = {
    # --- "The quiet leader vs the loud victim" ---
    "hook_example": os.path.join(REFERENCE_DIR, "quiet_leader_hook.png"),
    "caption_style_1": os.path.join(REFERENCE_DIR, "quiet_leader_caption1.png"),
    "caption_style_2": os.path.join(REFERENCE_DIR, "quiet_leader_caption2.png"),
    "dark_scene": os.path.join(REFERENCE_DIR, "quiet_leader_chess.png"),
    "dark_aesthetic": os.path.join(REFERENCE_DIR, "quiet_leader_dark.png"),
    "pre_outro": os.path.join(REFERENCE_DIR, "quiet_leader_outro.png"),

    # --- "High value solitude" ---
    "lion_opening": os.path.join(REFERENCE_DIR, "solitude_hook.png"),
    "caption_warm": os.path.join(REFERENCE_DIR, "solitude_caption1.png"),
    "wildlife_shot": os.path.join(REFERENCE_DIR, "solitude_lioness.png"),
    "night_city": os.path.join(REFERENCE_DIR, "solitude_dark_city.png"),
    "solitary_figure": os.path.join(REFERENCE_DIR, "solitude_night.png"),
    "lion_closing": os.path.join(REFERENCE_DIR, "solitude_closing.png"),
}


def validate_references():
    """
    # Checks that all reference frames exist
    # Prints warning if any are missing
    """
    missing = []
    for name, path in REFERENCE_FRAMES.items():
        if not os.path.exists(path):
            missing.append(name)

    if missing:
        print(f"[BRAND] WARNING: {len(missing)} reference frames missing:")
        for m in missing:
            print(f"  - {m}")
        return False

    print(f"[BRAND] All {len(REFERENCE_FRAMES)} reference frames verified")
    return True


def get_reference_brightness():
    """
    # Calculates the average brightness of all reference frames
    # Used to calibrate color grading to match the originals
    #
    # Returns: target brightness value (0-255)
    """
    import cv2

    brightness_values = []
    for name, path in REFERENCE_FRAMES.items():
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                brightness_values.append(hsv[:, :, 2].mean())

    if brightness_values:
        avg = np.mean(brightness_values)
        print(f"[BRAND] Reference brightness: {avg:.1f}/255 ({avg/255*100:.0f}%)")
        return avg

    return 62.0  # fallback based on original analysis


# --- Quick test ---
if __name__ == "__main__":
    print("Luminous Will Brand Reference")
    print("=" * 40)
    validate_references()
    get_reference_brightness()
    print(f"\nVideo: {VIDEO_SPECS['width']}x{VIDEO_SPECS['height']} @ {VIDEO_SPECS['fps']}fps")
    print(f"Bitrate: {VIDEO_SPECS['bitrate']}")
    print(f"Target brightness: {COLOR_GRADE_SPECS['target_brightness_pct']}%")
    print(f"Target saturation: {COLOR_GRADE_SPECS['target_saturation_pct']}%")
    print(f"Caption position: {CAPTION_SPECS['y_position_pct']*100}% from top")
