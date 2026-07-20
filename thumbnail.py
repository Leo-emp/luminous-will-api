import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import VideoFileClip
import config

# ============================================================
# PREMIUM THUMBNAIL GENERATOR
# Picks the most striking frame and adds punchy text overlay
# Goal: looks like a designer made it in Photoshop
#
# Pipeline:
#   1. Sample 25 evenly-spaced frames from the video
#   2. Score each frame on contrast, brightness, sharpness, color
#   3. Pick the best-scoring frame
#   4. Resize to 1280x720
#   5. Ask Gemini for a 2-3 word ALL CAPS punch line
#   6. Apply heavy vignette + bottom gradient (dark grade)
#   7. Overlay white bold text with black stroke + amber glow
#   8. Save as JPEG at quality 95
# ============================================================

# --- Output dimensions (standard YouTube thumbnail) ---
THUMB_WIDTH = 1280
THUMB_HEIGHT = 720


# ============================================================
# PUBLIC INTERFACE
# generate_thumbnail — same signature as original, premium output
# ============================================================

def generate_thumbnail(video_path, title, output_path=None):
    # Generates a premium branded thumbnail from the best video frame
    # Scores 25 candidate frames, picks the most visually striking one
    # Adds Gemini-generated punch line with Montserrat Bold + amber glow
    # Returns path to the saved thumbnail JPG

    # --- Default output path: same location as video, _thumb suffix ---
    if output_path is None:
        output_path = video_path.replace(".mp4", "_thumb.jpg")

    # --------------------------------------------------------
    # STEP 1: Extract and score candidate frames
    # Sample 25 evenly-spaced frames (up from 10 in old code)
    # More samples = higher chance of finding a striking moment
    # --------------------------------------------------------
    clip = VideoFileClip(video_path)
    duration = clip.duration
    num_candidates = 25  # sample more frames for better selection

    best_frame = None
    best_score = -1

    for i in range(num_candidates):
        # Space frames evenly across the video duration
        # Avoid the very start and end (often black fade-in/out)
        t = (i + 1) * duration / (num_candidates + 1)
        frame = clip.get_frame(t)   # returns numpy array (H, W, 3) uint8

        score = _score_frame(frame)

        if score > best_score:
            best_score = score
            best_frame = frame

    clip.close()

    # Fallback: if no frame found (shouldn't happen), use black frame
    if best_frame is None:
        best_frame = np.zeros((THUMB_HEIGHT, THUMB_WIDTH, 3), dtype=np.uint8)

    # --------------------------------------------------------
    # STEP 2: Resize to thumbnail dimensions (1280x720)
    # LANCZOS = best quality downscaling algorithm
    # --------------------------------------------------------
    img = Image.fromarray(best_frame)
    img = img.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.LANCZOS)

    # --------------------------------------------------------
    # STEP 3: Generate punch line via Gemini
    # 2-3 word ALL CAPS phrase — more impactful than full title
    # --------------------------------------------------------
    punch_line = _generate_punch_line(title)

    # --------------------------------------------------------
    # STEP 4: Apply premium dark visual treatment
    # Heavy vignette + bottom gradient for text area
    # --------------------------------------------------------
    img = _apply_thumbnail_grade(img)

    # --------------------------------------------------------
    # STEP 5: Add text overlay (Montserrat Bold, glow effect)
    # --------------------------------------------------------
    img = _add_text_overlay(img, punch_line)

    # --------------------------------------------------------
    # STEP 6: Save as high-quality JPEG
    # quality=95 is near-lossless — good for platform uploads
    # --------------------------------------------------------
    img = img.convert("RGB")  # flatten RGBA back to RGB for JPEG
    img.save(output_path, "JPEG", quality=95)
    print(f"[THUMBNAIL] Premium thumbnail saved: {output_path}")

    return output_path


# ============================================================
# FRAME SCORING
# _score_frame — rates each frame 0-2+ (higher = better)
# Weighted combination of 4 factors:
#   - Contrast (40%): high std dev = visually rich frame
#   - Brightness (20%): prefer medium-dark (target ~80/255)
#   - Sharpness (25%): edges via np.diff gradient = clear subject
#   - Color interest (15%): variance across channels = warm/cool
# ============================================================

def _score_frame(frame):
    # Scores a single video frame for thumbnail suitability
    # frame: numpy array of shape (H, W, 3), dtype uint8
    # Returns: float score (higher = better candidate)

    # Convert to float32 for safe math (avoid uint8 overflow)
    frame_f = frame.astype(np.float32)

    # --- Compute grayscale luminance (average of R, G, B channels) ---
    # axis=2 collapses the colour dimension → shape becomes (H, W)
    gray = np.mean(frame_f, axis=2)

    # --- FACTOR 1: Brightness (20% weight) ---
    # We want medium-dark frames (target ~80/255 = ~31% brightness)
    # Formula: 1.0 - normalized distance from ideal (80)
    # Range: penalizes very dark (<30) and very bright (>180) frames
    brightness = np.mean(gray)
    brightness_score = 1.0 - abs(brightness - 80) / 128.0
    # Clamp to [0, 1] — can go negative for extreme blacks/whites
    brightness_score = max(0.0, brightness_score)

    # --- FACTOR 2: Contrast (40% weight) ---
    # Standard deviation of grayscale = how spread the luminance is
    # Higher std dev = more visual drama = better thumbnail
    # Cap at 1.5 to prevent one extreme frame dominating
    contrast = np.std(gray)
    contrast_score = min(contrast / 50.0, 1.5)

    # --- FACTOR 3: Sharpness (25% weight) ---
    # Uses np.diff to compute pixel-to-pixel differences (gradient proxy)
    # Sharp frames have large local differences at edges
    # dy = vertical differences, dx = horizontal differences
    # High std dev of these differences = lots of sharp edges
    dy = np.diff(gray, axis=0)   # shape: (H-1, W) — vertical gradient
    dx = np.diff(gray, axis=1)   # shape: (H, W-1) — horizontal gradient
    sharpness = (np.std(dy) + np.std(dx)) / 2.0
    sharpness_score = min(sharpness / 30.0, 1.0)
    # Cap at 1.0 — we don't want noise/artifacts to win

    # --- FACTOR 4: Color interest (15% weight) ---
    # Computes per-channel average then measures variance between channels
    # High variance = warm/cool imbalance = visually interesting (amber, blue, etc.)
    # Low variance = monochrome/gray = less interesting for thumbnail
    r_mean = frame_f[:, :, 0].mean()
    g_mean = frame_f[:, :, 1].mean()
    b_mean = frame_f[:, :, 2].mean()
    color_var = np.std([r_mean, g_mean, b_mean])
    color_score = min(color_var / 30.0, 1.0)

    # --- Weighted combination ---
    # Contrast is the strongest signal for thumbnail quality
    # Sharpness ensures we pick frames with clear subjects
    # Brightness prevents picking unusable dark/washed-out frames
    # Color interest rewards the amber/warm tones of our brand
    score = (brightness_score * 0.20
             + contrast_score  * 0.40
             + sharpness_score * 0.25
             + color_score     * 0.15)

    return score


# ============================================================
# GEMINI PUNCH LINE GENERATOR
# _generate_punch_line — asks Gemini for a 2-3 word ALL CAPS phrase
# Example outputs: "STAY SILENT", "COMFORT KILLS", "NEVER AVERAGE"
# Falls back to first 3 words of title if no API key / error
# ============================================================

def _generate_punch_line(title):
    # Generates a short, punchy thumbnail text via Gemini
    # title: the full video title (used as topic context)
    # Returns: 2-3 word ALL CAPS string (e.g. "WALK ALONE")

    # --- Fallback helper: first 3 words of title, uppercased ---
    def _fallback():
        words = title.upper().split()[:3]
        return " ".join(words)

    # If no Gemini API key configured, use fallback immediately
    if not config.GEMINI_API_KEY:
        print("[THUMBNAIL] No GEMINI_API_KEY — using title fallback for punch line")
        return _fallback()

    try:
        import google.generativeai as genai

        # Configure the Gemini SDK with our API key
        genai.configure(api_key=config.GEMINI_API_KEY)

        # Use Gemini 2.5 Flash — fast and capable for short creative tasks
        model = genai.GenerativeModel("gemini-2.5-flash")

        # Prompt: strict instructions to get ONLY the punch line back
        # No explanations, no quotes, just the 2-3 word phrase
        prompt = f"""Generate a 2-3 word punch line for a dark motivation video thumbnail.
Topic: "{title}"
Rules: ALL CAPS, maximum 3 words, punchy, emotional, commanding.
Examples: "STAY SILENT", "COMFORT KILLS", "NEVER AVERAGE", "WALK ALONE"
Respond with ONLY the punch line, nothing else."""

        response = model.generate_content(prompt)
        punch = response.text.strip().upper()

        # Sanitize: strip quotes, punctuation, limit to 3 words max
        # Some models add quotes or trailing periods — remove them
        punch = punch.strip('"\'.,!?')
        words = punch.split()[:3]
        result = " ".join(words)

        print(f"[THUMBNAIL] Gemini punch line: '{result}'")
        return result

    except Exception as e:
        # Network error, quota exceeded, etc. — degrade gracefully
        print(f"[THUMBNAIL] Gemini punch line failed: {e}")
        return _fallback()


# ============================================================
# VISUAL GRADING
# _apply_thumbnail_grade — heavy dark treatment for thumbnails
# Applies two layers:
#   1. Radial vignette (dark edges, bright center) — heavier than video
#   2. Bottom gradient (solid black at bottom for text readability)
# ============================================================

def _apply_thumbnail_grade(img):
    # Applies enhanced dark cinematic grade optimised for thumbnails
    # Heavier vignette than the video pipeline (thumbnails are viewed small)
    # img: PIL Image (RGB or RGBA)
    # Returns: PIL Image (RGBA with dark overlays composited)

    # Convert to RGBA so we can use alpha compositing
    img = img.convert("RGBA")

    # --------------------------------------------------------
    # LAYER 1: Heavy radial vignette
    # Darkens the edges and corners, preserving the center
    # The step=4 optimisation draws 4px-wide rectangles per row
    # to avoid drawing every pixel individually (still 720*320=230k ops)
    # --------------------------------------------------------
    vignette = Image.new("RGBA", (THUMB_WIDTH, THUMB_HEIGHT), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)

    # Center point of the image
    cx = THUMB_WIDTH  // 2   # 640
    cy = THUMB_HEIGHT // 2   # 360

    # Max possible distance from center to a corner (Euclidean)
    # Used to normalise distance to 0.0–1.0 range
    max_dist = ((THUMB_WIDTH / 2) ** 2 + (THUMB_HEIGHT / 2) ** 2) ** 0.5

    # Draw vignette row by row
    # step=4: draw rectangles 4px wide instead of 1px to speed up
    step = 4
    for y in range(THUMB_HEIGHT):
        for x in range(0, THUMB_WIDTH, step):
            # Normalised distance from center (0.0 = center, ~1.0 = corner)
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            norm_dist = dist / max_dist

            # Vignette starts at 30% radius (inner edge), full at 100%
            # Formula: clamp((dist - 0.3) * 1.5, 0, 1) * max_alpha
            raw = (norm_dist - 0.3) * 1.5      # ramp from 0.3 → 1.0
            strength = min(1.0, max(0.0, raw))  # clamp to [0, 1]
            alpha = int(strength * 180)          # max alpha=180 (heavy but not black)

            # Draw a small rectangle at this position
            vdraw.rectangle([x, y, x + step, y + 1], fill=(0, 0, 0, alpha))

    # Composite vignette on top of the image
    img = Image.alpha_composite(img, vignette)

    # --------------------------------------------------------
    # LAYER 2: Bottom gradient
    # Starts at (THUMB_HEIGHT - 250) = pixel row 470
    # Fades from transparent (top) to alpha=220 (bottom)
    # Ensures the text is always readable regardless of frame content
    # --------------------------------------------------------
    gradient = Image.new("RGBA", (THUMB_WIDTH, THUMB_HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)

    grad_start = THUMB_HEIGHT - 250  # row 470 — start of gradient zone

    for y in range(grad_start, THUMB_HEIGHT):
        # Linear ramp from 0 to 220 alpha over the 250-pixel zone
        progress = (y - grad_start) / 250.0   # 0.0 at top, 1.0 at bottom
        alpha = int(progress * 220)            # max alpha=220 (near-opaque)
        gdraw.line([(0, y), (THUMB_WIDTH, y)], fill=(0, 0, 0, alpha))

    # Composite gradient on top of vignetted image
    img = Image.alpha_composite(img, gradient)

    return img


# ============================================================
# TEXT OVERLAY
# _add_text_overlay — adds punch line with premium styling
# Three-pass rendering:
#   1. Black stroke (4px, all 8 offsets) — hard edge, legibility
#   2. Amber glow (±2px, rgba(232,168,23,60)) — brand colour aura
#   3. White text (centre, no offset) — crisp final layer
# ============================================================

def _add_text_overlay(img, text):
    # Renders the punch line text onto the thumbnail
    # text: ALL CAPS short string (e.g. "STAY SILENT")
    # img: PIL Image (RGBA)
    # Returns: PIL Image (RGBA with text composited)

    draw = ImageDraw.Draw(img)

    # --------------------------------------------------------
    # FONT LOADING: try Montserrat Bold → Arial Bold → default
    # Montserrat Bold gives the premium YouTube thumbnail look
    # Arial Bold is a good Windows fallback
    # load_default() is last resort (bitmap font, small but functional)
    # --------------------------------------------------------
    font_size = 72  # large enough to read on small thumbnail previews

    font = None  # will be set in one of the branches below

    if os.path.exists(config.CAPTION_FONT_FILE):
        # Montserrat Bold found in assets/fonts/ — use it
        try:
            font = ImageFont.truetype(config.CAPTION_FONT_FILE, font_size)
        except OSError:
            pass  # corrupt or incompatible font file — try next

    if font is None:
        # Try Arial Bold (standard Windows system font)
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except OSError:
            pass

    if font is None:
        # Last resort: Pillow's built-in bitmap font (very small but always works)
        font = ImageFont.load_default()

    # --------------------------------------------------------
    # POSITION: centered horizontally, near bottom of frame
    # Bottom of text sits at THUMB_HEIGHT - 60px (well inside gradient zone)
    # --------------------------------------------------------
    text_width = draw.textlength(text, font=font)   # pixel width of the text string
    x = int((THUMB_WIDTH - text_width) // 2)         # horizontal center
    y = THUMB_HEIGHT - 120                            # vertical position (120px from bottom)

    # --------------------------------------------------------
    # PASS 1: Black stroke (4px, offsets in all 8 directions)
    # Drawn first (bottom layer) so it appears behind the white text
    # 4px stroke is heavy — good for small thumbnail previews
    # --------------------------------------------------------
    stroke = 4
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            if dx != 0 or dy != 0:  # skip the center (that's the white text pass)
                draw.text((x + dx, y + dy), text, font=font, fill="black")

    # --------------------------------------------------------
    # PASS 2: Amber outer glow (subtle brand colour aura)
    # Drawn slightly larger (font_size+2) and at ±2px offsets
    # Alpha=60 keeps it subtle — a hint of warmth, not distracting
    # Uses brand amber: #E8A817 = rgb(232, 168, 23)
    # --------------------------------------------------------
    glow_font_size = font_size + 2  # slightly larger to bleed out beyond stroke

    # Try to load glow font (same path, larger size)
    glow_font = None
    if os.path.exists(config.CAPTION_FONT_FILE):
        try:
            glow_font = ImageFont.truetype(config.CAPTION_FONT_FILE, glow_font_size)
        except OSError:
            pass

    if glow_font is None:
        glow_font = font  # fallback: same font at same size

    # Draw amber glow at ±2px in all directions
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            draw.text(
                (x + dx - 1, y + dy - 1),   # -1 offset to center the larger glow font
                text,
                font=glow_font,
                fill=(232, 168, 23, 60)       # amber RGBA: #E8A817 at alpha=60
            )

    # --------------------------------------------------------
    # PASS 3: White text (final layer, crisp center)
    # Drawn last so it sits on top of stroke and glow
    # --------------------------------------------------------
    draw.text((x, y), text, font=font, fill="white")

    return img


# ============================================================
# REEL THUMBNAIL GENERATOR
# For 9:16 portrait quote reels — uses the best quote slide
# image instead of extracting a landscape frame from the video.
# ============================================================

REEL_THUMB_WIDTH = 1080
REEL_THUMB_HEIGHT = 1920


def generate_reel_thumbnail(video_path, title, output_path=None):
    # Generates a 9:16 portrait thumbnail for a quote reel
    # Extracts frames from the video, scores them, picks the best
    # Adds a branded bottom bar with punch line text
    # Returns path to the saved thumbnail

    if output_path is None:
        output_path = video_path.replace(".mp4", "_thumb.jpg")

    # --- Extract and score candidate frames (skip first/last 10%) ---
    clip = VideoFileClip(video_path)
    duration = clip.duration
    num_candidates = 20

    best_frame = None
    best_score = -1

    for i in range(num_candidates):
        t = duration * (0.1 + 0.8 * (i / (num_candidates - 1)))
        frame = clip.get_frame(t)

        score = _score_frame(frame)
        if score > best_score:
            best_score = score
            best_frame = frame

    clip.close()

    if best_frame is None:
        best_frame = np.zeros((REEL_THUMB_HEIGHT, REEL_THUMB_WIDTH, 3), dtype=np.uint8)

    img = Image.fromarray(best_frame)

    # --- Resize to 1080x1920 (center crop if needed) ---
    img_ratio = img.width / img.height
    target_ratio = REEL_THUMB_WIDTH / REEL_THUMB_HEIGHT
    if img_ratio > target_ratio:
        new_h = REEL_THUMB_HEIGHT
        new_w = int(new_h * img_ratio)
    else:
        new_w = REEL_THUMB_WIDTH
        new_h = int(new_w / img_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - REEL_THUMB_WIDTH) // 2
    top = (new_h - REEL_THUMB_HEIGHT) // 2
    img = img.crop((left, top, left + REEL_THUMB_WIDTH, top + REEL_THUMB_HEIGHT))

    # --- Generate punch line ---
    punch_line = _generate_punch_line(title)

    # --- Apply reel-specific dark grade ---
    img = _apply_reel_thumb_grade(img)

    # --- Add text overlay ---
    img = _add_reel_text_overlay(img, punch_line)

    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=95)
    print(f"[THUMBNAIL] Reel thumbnail saved: {output_path}")
    return output_path


def _apply_reel_thumb_grade(img):
    # Dark grade optimized for 9:16 reel thumbnails
    # Heavier bottom gradient since text sits lower on vertical
    img = img.convert("RGBA")

    # --- Radial vignette (numpy-based for speed) ---
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    Y, X = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
    vignette_map = np.clip(1.0 - 0.5 * dist ** 1.8, 0.3, 1.0)
    for c in range(3):
        arr[:, :, c] *= vignette_map
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")

    # --- Bottom gradient for text readability ---
    gradient = Image.new("RGBA", (REEL_THUMB_WIDTH, REEL_THUMB_HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    grad_start = REEL_THUMB_HEIGHT - 500
    for y in range(grad_start, REEL_THUMB_HEIGHT):
        progress = (y - grad_start) / 500.0
        alpha = int(progress * 200)
        gdraw.line([(0, y), (REEL_THUMB_WIDTH, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, gradient)

    return img


def _add_reel_text_overlay(img, text):
    # Adds punch line text to reel thumbnail — large, centered, bottom third
    draw = ImageDraw.Draw(img)

    font_size = 96
    font = None
    if os.path.exists(config.CAPTION_FONT_FILE):
        try:
            font = ImageFont.truetype(config.CAPTION_FONT_FILE, font_size)
        except OSError:
            pass
    if font is None:
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    text_width = draw.textlength(text, font=font)
    x = int((REEL_THUMB_WIDTH - text_width) // 2)
    y = REEL_THUMB_HEIGHT - 250

    # --- Black stroke ---
    stroke = 5
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill="black")

    # --- Amber glow ---
    glow_font = font
    if os.path.exists(config.CAPTION_FONT_FILE):
        try:
            glow_font = ImageFont.truetype(config.CAPTION_FONT_FILE, font_size + 2)
        except OSError:
            pass
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            draw.text((x + dx - 1, y + dy - 1), text,
                      font=glow_font, fill=(232, 168, 23, 50))

    # --- White text ---
    draw.text((x, y), text, font=font, fill="white")

    # --- Brand watermark at bottom ---
    try:
        wm_font = ImageFont.truetype(config.CAPTION_FONT_FILE, 28)
    except Exception:
        wm_font = ImageFont.load_default()
    wm_text = "LUMINOUS WILL"
    wm_w = draw.textlength(wm_text, font=wm_font)
    draw.text(((REEL_THUMB_WIDTH - wm_w) // 2, REEL_THUMB_HEIGHT - 100),
              wm_text, font=wm_font, fill=(180, 180, 180, 160))

    return img
