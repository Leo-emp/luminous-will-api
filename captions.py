import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import config

# ============================================================
# CAPTION GENERATOR
# Creates word-synced captions with keyword highlighting
# Style: white text, gold/amber highlight on emphasis words
# Positioned at bottom of frame, bold font with black stroke
# ============================================================


def create_caption_clips(word_timestamps, script_segments, video_duration):
    """
    # Creates caption data synced to each word from the voiceover
    # Groups words into display chunks (3-5 words at a time)
    # Highlights the emphasis word in each segment
    #
    # Args:
    #   word_timestamps: list of {word, start, end} from ElevenLabs
    #   script_segments: original script with emphasis_word info
    #   video_duration: total video duration in seconds
    #
    # Returns:
    #   list of caption events: {text, start, end, highlight_word}
    """

    print("[CAPTIONS] Building word-synced caption events...")

    if not word_timestamps:
        print("[CAPTIONS] WARNING: No timestamps, using fallback timing")
        return create_fallback_captions(script_segments, video_duration)

    # --- Build emphasis word lookup ---
    # Maps words to their highlight status based on script segments
    emphasis_words = set()
    for seg in script_segments:
        if "emphasis_word" in seg:
            emphasis_words.add(seg["emphasis_word"].lower())

    # --- Group words into display chunks ---
    # Show 3-5 words at a time for readability
    caption_events = []
    chunk_size = 4  # words per caption group
    i = 0

    while i < len(word_timestamps):
        # Grab a chunk of words
        chunk_end = min(i + chunk_size, len(word_timestamps))
        chunk = word_timestamps[i:chunk_end]

        # Build the caption text and find highlight word
        words_in_chunk = [w["word"] for w in chunk]
        caption_text = " ".join(words_in_chunk)

        # Check if any word in this chunk should be highlighted
        highlight_word = None
        for word_data in chunk:
            clean_word = word_data["word"].strip(".,!?;:'\"").lower()
            if clean_word in emphasis_words:
                highlight_word = word_data["word"]
                break

        # Timing: start when first word begins, end when last word ends
        start_time = chunk[0]["start"]
        end_time = chunk[-1]["end"]

        caption_events.append({
            "text": caption_text,
            "start": start_time,
            "end": end_time,
            "highlight_word": highlight_word,
            "words": chunk,  # individual word timing for per-word animation
        })

        i = chunk_end

    print(f"[CAPTIONS] Created {len(caption_events)} caption events")
    return caption_events


def create_fallback_captions(script_segments, video_duration):
    """
    # Fallback when no word timestamps available
    # Divides time equally among segments
    """
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


def render_caption_frame(text, highlight_word, frame_width, frame_height,
                         font_size=None, position_y=None, stroke_width=None):
    """
    # Renders a single caption frame as a numpy array (RGBA)
    # White text with gold highlight on the emphasis word
    # Black stroke/outline for readability over any background
    #
    # Args:
    #   text: caption text to render
    #   highlight_word: word to highlight in gold (or None)
    #   frame_width: output frame width in pixels
    #   frame_height: output frame height in pixels
    #   font_size: optional override for caption font size (default: config.CAPTION_FONT_SIZE)
    #   position_y: optional override for caption vertical position ratio (default: config.CAPTION_POSITION[1])
    #   stroke_width: optional override for text stroke width (default: config.CAPTION_STROKE_WIDTH)
    #
    # Returns: numpy array (H, W, 4) RGBA
    """

    # --- Create transparent image ---
    img = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Load font ---
    # Use optional overrides or fall back to config defaults
    _font_size = font_size or config.CAPTION_FONT_SIZE
    _position_y = position_y or config.CAPTION_POSITION[1]
    _stroke_width = stroke_width or config.CAPTION_STROKE_WIDTH
    try:
        font = ImageFont.truetype("arialbd.ttf", _font_size)
    except OSError:
        try:
            font = ImageFont.truetype("Arial Bold.ttf", _font_size)
        except OSError:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", _font_size)
            except OSError:
                font = ImageFont.load_default()
                print("[CAPTIONS] WARNING: Using default font (Arial Bold not found)")

    # --- Split text into words for highlighting ---
    words = text.split()
    # Calculate total text width to center it
    space_width = draw.textlength(" ", font=font)

    # --- Calculate word positions ---
    # We may need to wrap to multiple lines
    lines = wrap_text_to_lines(words, font, draw, frame_width - 100)

    # --- Calculate vertical position (near bottom) ---
    # Measured from real videos: caption center at 83.2% from top
    # Line spacing of 8px for tighter, cleaner look
    line_height = _font_size + 8
    total_text_height = len(lines) * line_height
    y_start = int(frame_height * _position_y) - total_text_height // 2

    # --- Draw each line ---
    for line_idx, line_words in enumerate(lines):
        # Calculate line width for centering
        line_text = " ".join(line_words)
        line_width = draw.textlength(line_text, font=font)
        x = (frame_width - line_width) // 2
        y = y_start + line_idx * line_height

        # Draw each word
        for word in line_words:
            # Check if this word should be highlighted
            is_highlight = False
            if highlight_word:
                clean_word = word.strip(".,!?;:'\"").lower()
                clean_highlight = highlight_word.strip(".,!?;:'\"").lower()
                if clean_word == clean_highlight:
                    is_highlight = True

            color = config.CAPTION_HIGHLIGHT_COLOR if is_highlight else config.CAPTION_COLOR

            # Draw black outline/stroke for readability
            for dx in range(-_stroke_width, _stroke_width + 1):
                for dy in range(-_stroke_width, _stroke_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text(
                            (x + dx, y + dy), word,
                            font=font,
                            fill=config.CAPTION_STROKE_COLOR,
                        )

            # Draw the actual word
            draw.text((x, y), word, font=font, fill=color)

            # Move x position to next word
            word_width = draw.textlength(word + " ", font=font)
            x += word_width

    return np.array(img)


def wrap_text_to_lines(words, font, draw, max_width):
    """
    # Wraps words into lines that fit within max_width
    # Returns list of lists of words per line
    """
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


# --- Quick test ---
if __name__ == "__main__":
    # Test rendering a caption
    frame = render_caption_frame(
        "Your silence is your greatest weapon",
        "weapon",
        config.VIDEO_WIDTH,
        config.VIDEO_HEIGHT,
    )
    # Save test frame
    test_img = Image.fromarray(frame)
    test_path = os.path.join(config.TEMP_DIR, "test_caption.png")
    test_img.save(test_path)
    print(f"Test caption saved to: {test_path}")
