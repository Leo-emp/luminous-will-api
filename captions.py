import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import config

# ============================================================
# CAPTION GENERATOR - CLOUD VERSION
# Creates word-synced captions with keyword highlighting
# Uses Liberation Sans Bold (Linux-compatible Arial equivalent)
# ============================================================


def _load_font(font_size):
    # --- Try multiple font paths for cross-platform compatibility ---
    font_paths = [
        # Linux (HF Spaces / Ubuntu)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # Windows fallbacks
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "Arial Bold.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, font_size)
        except OSError:
            continue
    print("[CAPTIONS] WARNING: No bold font found, using default")
    return ImageFont.load_default()


def create_caption_clips(word_timestamps, script_segments, video_duration):
    # --- Groups words into display chunks synced to voiceover ---
    print("[CAPTIONS] Building word-synced caption events...")

    if not word_timestamps:
        print("[CAPTIONS] WARNING: No timestamps, using fallback timing")
        return create_fallback_captions(script_segments, video_duration)

    emphasis_words = set()
    for seg in script_segments:
        if "emphasis_word" in seg:
            emphasis_words.add(seg["emphasis_word"].lower())

    caption_events = []
    chunk_size = 4
    i = 0

    while i < len(word_timestamps):
        chunk_end = min(i + chunk_size, len(word_timestamps))
        chunk = word_timestamps[i:chunk_end]

        words_in_chunk = [w["word"] for w in chunk]
        caption_text = " ".join(words_in_chunk)

        highlight_word = None
        for word_data in chunk:
            clean_word = word_data["word"].strip(".,!?;:'\"").lower()
            if clean_word in emphasis_words:
                highlight_word = word_data["word"]
                break

        start_time = chunk[0]["start"]
        end_time = chunk[-1]["end"]

        caption_events.append({
            "text": caption_text,
            "start": start_time,
            "end": end_time,
            "highlight_word": highlight_word,
            "words": chunk,
        })

        i = chunk_end

    print(f"[CAPTIONS] Created {len(caption_events)} caption events")
    return caption_events


def create_fallback_captions(script_segments, video_duration):
    # --- Fallback when no word timestamps available ---
    time_per_segment = video_duration / len(script_segments)
    events = []
    for i, seg in enumerate(script_segments):
        events.append({
            "text": seg["text"],
            "start": i * time_per_segment,
            "end": (i + 1) * time_per_segment,
            "highlight_word": seg.get("emphasis_word"),
            "words": [],
        })
    return events


def render_caption_frame(text, highlight_word, frame_width, frame_height):
    # --- Renders a single caption frame as RGBA numpy array ---
    img = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = config.CAPTION_FONT_SIZE
    font = _load_font(font_size)

    words = text.split()
    lines = wrap_text_to_lines(words, font, draw, frame_width - 100)

    line_height = font_size + 8
    total_text_height = len(lines) * line_height
    y_start = int(frame_height * config.CAPTION_POSITION[1]) - total_text_height // 2

    for line_idx, line_words in enumerate(lines):
        line_text = " ".join(line_words)
        line_width = draw.textlength(line_text, font=font)
        x = (frame_width - line_width) // 2
        y = y_start + line_idx * line_height

        for word in line_words:
            is_highlight = False
            if highlight_word:
                clean_word = word.strip(".,!?;:'\"").lower()
                clean_highlight = highlight_word.strip(".,!?;:'\"").lower()
                if clean_word == clean_highlight:
                    is_highlight = True

            color = config.CAPTION_HIGHLIGHT_COLOR if is_highlight else config.CAPTION_COLOR

            stroke_w = config.CAPTION_STROKE_WIDTH
            for dx in range(-stroke_w, stroke_w + 1):
                for dy in range(-stroke_w, stroke_w + 1):
                    if dx != 0 or dy != 0:
                        draw.text(
                            (x + dx, y + dy), word,
                            font=font,
                            fill=config.CAPTION_STROKE_COLOR,
                        )

            draw.text((x, y), word, font=font, fill=color)

            word_width = draw.textlength(word + " ", font=font)
            x += word_width

    return np.array(img)


def wrap_text_to_lines(words, font, draw, max_width):
    # --- Wraps words into lines that fit within max_width ---
    lines = []
    current_line = []

    for word in words:
        test_line = current_line + [word]
        test_text = " ".join(test_line)
        text_width = draw.textlength(test_text, font=font)

        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(current_line)
            current_line = [word]

    if current_line:
        lines.append(current_line)

    return lines
