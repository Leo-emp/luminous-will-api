import os
import sys
import shutil
import time
import config
from script_generator import generate_script, get_script_text
from voiceover import generate_voiceover, get_audio_duration
from visuals import search_and_download_videos
from captions import create_caption_clips
from video_assembler import assemble_video
from brand_reference import validate_references, VIDEO_SPECS
from music import select_music

# ============================================================
# LUMINOUS WILL - AUTOMATED VIDEO PIPELINE
# ============================================================
# Creates dark aesthetic motivational videos automatically:
#   1. Generate script with punchy hook
#   2. Generate voiceover (ElevenLabs - Adam voice)
#   3. Download matching stock footage (Pexels)
#   4. Build word-synced captions
#   5. Assemble final video with color grading + music + logo
#
# Usage:
#   python main.py                          -> random trending topic
#   python main.py "your topic here"        -> specific topic
#   python main.py --list                   -> list trending topics
# ============================================================


def validate_setup():
    """
    # Checks that all required API keys and files are present
    # before starting the pipeline
    """

    errors = []

    # --- Check API keys ---
    if not config.ELEVENLABS_API_KEY or config.ELEVENLABS_API_KEY == "your_elevenlabs_api_key_here":
        errors.append("ELEVENLABS_API_KEY not set in .env file")

    if not config.PEXELS_API_KEY or config.PEXELS_API_KEY == "your_pexels_api_key_here":
        errors.append("PEXELS_API_KEY not set in .env file")

    # --- Check logo file ---
    if not os.path.exists(config.LOGO_PATH):
        errors.append(f"Logo file not found at: {config.LOGO_PATH}")

    # --- Check directories ---
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    if errors:
        print("\n[SETUP ERROR] Fix the following before running:\n")
        for e in errors:
            print(f"  - {e}")
        print(f"\n  Edit your .env file at: {os.path.join(config.BASE_DIR, '.env')}")
        return False

    return True



def run_pipeline(topic=None, video_format=None):
    """
    # Main pipeline: runs all steps in sequence
    # Accepts video_format for dual-format support
    """

    from config import VideoFormat, get_format_profile

    if video_format is None:
        video_format = VideoFormat.VERTICAL_SHORT

    profile = get_format_profile(video_format)

    start_time = time.time()
    print("\n" + "=" * 60)
    print("  LUMINOUS WILL - VIDEO PIPELINE")
    print(f"  Format: {video_format.value} ({profile['width']}x{profile['height']})")
    print("=" * 60)

    # --- STEP 1: VALIDATE ---
    print("\n[STEP 1/6] Validating setup...")
    if not validate_setup():
        return None

    validate_references()

    # --- STEP 2: GENERATE SCRIPT ---
    print("\n[STEP 2/6] Generating script...")
    script_segments, topic = generate_script(topic, video_format=video_format)
    full_script = get_script_text(script_segments)
    print(f"[SCRIPT] Topic: {topic}")
    print(f"[SCRIPT] Segments: {len(script_segments)}")
    print(f"[SCRIPT] Full text:\n  {full_script[:200]}...")

    safe_topic = topic.replace(" ", "_").replace("'", "")[:50]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_name = f"{safe_topic}_{timestamp}"
    video_temp = os.path.join(config.TEMP_DIR, video_name)
    os.makedirs(video_temp, exist_ok=True)

    # --- STEP 3: GENERATE VOICEOVER ---
    print("\n[STEP 3/6] Generating voiceover...")
    voiceover_path = os.path.join(video_temp, "voiceover.mp3")
    word_timestamps = generate_voiceover(full_script, voiceover_path, profile=profile)
    audio_duration = get_audio_duration(voiceover_path)
    print(f"[VOICEOVER] Duration: {audio_duration:.1f}s")

    # --- STEP 4: DOWNLOAD STOCK FOOTAGE ---
    print("\n[STEP 4/6] Downloading stock footage...")
    clips_dir = os.path.join(video_temp, "clips")
    clip_paths = search_and_download_videos(script_segments, clips_dir, profile=profile)

    if not clip_paths:
        print("[ERROR] No footage downloaded. Check your Pexels API key.")
        return None

    # --- STEP 5: BUILD CAPTIONS ---
    print("\n[STEP 5/6] Building word-synced captions...")
    caption_events = create_caption_clips(
        word_timestamps, script_segments, audio_duration
    )

    # --- STEP 6: ASSEMBLE FINAL VIDEO ---
    print("\n[STEP 6/6] Assembling final video...")
    output_path = os.path.join(config.OUTPUT_DIR, f"{video_name}.mp4")
    # --- Mood-based music selection (matches track to script's dominant mood) ---
    music_path = select_music(script_segments)

    if not music_path:
        print("[MUSIC] No background music available - video will have voiceover only")

    assemble_video(
        clip_paths=clip_paths,
        voiceover_path=voiceover_path,
        caption_events=caption_events,
        script_segments=script_segments,
        music_path=music_path,
        output_path=output_path,
        video_format=video_format,
    )

    # --- DONE ---
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"  VIDEO COMPLETE!")
    print(f"  Format: {video_format.value}")
    print(f"  Topic: {topic}")
    print(f"  Output: {output_path}")
    print(f"  Time: {elapsed:.0f} seconds")
    print("=" * 60 + "\n")

    return output_path


def list_topics():
    """
    # Prints all available trending topics
    """
    print("\n Available Trending Topics:\n")
    for i, topic in enumerate(config.TRENDING_TOPICS, 1):
        print(f"  {i:2d}. {topic}")
    print(f"\n Total: {len(config.TRENDING_TOPICS)} topics")
    print(f" Usage: python main.py \"topic name here\"")


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Luminous Will Video Pipeline")
    parser.add_argument("topic", nargs="?", default=None, help="Video topic")
    parser.add_argument("--format", choices=["short", "long"], default="short",
                        help="Video format: short (9:16, 60-90s) or long (16:9, 8-12min)")
    parser.add_argument("--list", action="store_true", help="List available topics")
    args = parser.parse_args()

    if args.list:
        list_topics()
    else:
        from config import VideoFormat
        fmt = VideoFormat.HORIZONTAL_LONG if args.format == "long" else VideoFormat.VERTICAL_SHORT
        run_pipeline(topic=args.topic, video_format=fmt)
