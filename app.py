import os
import json
import shutil
import time
import gradio as gr
import config
from script_generator import generate_script, get_script_text
from voiceover import generate_voiceover, get_audio_duration
from visuals import search_and_download_videos
from captions import create_caption_clips
from video_assembler import assemble_video
from brand_reference import validate_references, VIDEO_SPECS
from music import select_music
from thumbnail import generate_thumbnail, generate_reel_thumbnail
from metadata_generator import generate_metadata

# --- Content type system: multi-type video generation support ---
from content_types import CONTENT_TYPES, get_content_type
# --- Scheduler: smart topic rotation to avoid repeats ---
from scheduler import pick_unused_topic

# ============================================================
# LUMINOUS WILL - CLOUD VIDEO PIPELINE (Gradio API)
# Generates dark aesthetic motivational videos via web interface
# Deployed on Hugging Face Spaces
#
# Task 7: Added content type parameter so each video type
# (dark motivation, stoicism, etc.) uses its own visual
# style, topics, music mood, and accent color.
# ============================================================


def validate_setup():
    # --- Check API keys before starting ---
    # Without these keys the pipeline cannot run at all
    errors = []
    if not config.GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY not set (add it in HF Space Secrets)")
    if not config.PEXELS_API_KEY:
        errors.append("PEXELS_API_KEY not set (add it in HF Space Secrets)")
    # # ElevenLabs is optional — Edge TTS fallback handles it
    if errors:
        return False, "\n".join(errors)
    # --- Create required directories if missing ---
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    os.makedirs(config.MUSIC_DIR, exist_ok=True)
    return True, "All checks passed"


def generate_video(topic, video_format_str="short", content_type_key=None, progress=gr.Progress()):
    """
    # Main pipeline with format and content type support
    # content_type_key: which content type to use for this video
    #   If None, defaults to "dark_motivation"
    # Each content type controls:
    #   - accent color for captions (overrides config default)
    #   - topic pool to draw from
    #   - music mood for background track selection
    #   - visual search keywords passed to Pexels/Pixabay
    """
    from config import VideoFormat, get_format_profile

    # --- Default content type if none provided ---
    # "dark_motivation" is the original/legacy type for backward compat
    if content_type_key is None:
        content_type_key = "dark_motivation"

    # --- Load the full content type config dict ---
    ct = get_content_type(content_type_key)

    # --- Resolve video format enum from string ---
    fmt = VideoFormat.HORIZONTAL_LONG if video_format_str == "long" else VideoFormat.VERTICAL_SHORT
    profile = get_format_profile(fmt)

    start_time = time.time()

    # --- Pre-flight check: API keys and directories ---
    progress(0.0, desc="Checking setup...")
    ok, msg = validate_setup()
    if not ok:
        raise gr.Error(f"Setup error: {msg}")

    # --- Validate brand reference assets (fonts, logos, etc.) ---
    validate_references()

    # --- Override caption highlight color for this content type ---
    # Each content type has its own accent color (e.g. amber for dark motivation,
    # slate-blue for stoicism) so captions match the visual identity
    config.CAPTION_HIGHLIGHT_COLOR = ct["accent_color"]

    # --- Generate script using content-type-aware prompts ---
    progress(0.05, desc=f"Generating {ct['name']} script...")

    # FIX 2: Use pick_unused_topic so every auto-generated video gets a fresh topic.
    if not topic or topic.strip() == "":
        topic = pick_unused_topic(content_type_key)

    # --- Build topic-stable temp dir (no timestamp — survives retries) ---
    # Prevents wasting ElevenLabs/Gemini credits when video assembly fails
    # but voiceover/script were already generated successfully.
    if topic:
        safe_topic = topic.replace(" ", "_").replace("'", "")[:50]
    else:
        safe_topic = "_pending"

    video_temp = os.path.join(config.TEMP_DIR, f"{safe_topic}_{fmt.value}")
    os.makedirs(video_temp, exist_ok=True)

    # --- Check for cached script segments from a previous failed run ---
    script_cache_path = os.path.join(video_temp, "script_segments.json")
    cached_script = None

    if os.path.exists(script_cache_path):
        try:
            with open(script_cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            cached_script = cached_data.get("segments")
            cached_topic = cached_data.get("topic", topic)
            if cached_script and len(cached_script) > 2:
                print(f"[SCRIPT] CACHED — reusing {len(cached_script)} segments for '{cached_topic}'")
                script_segments = cached_script
                topic = cached_topic
            else:
                cached_script = None
        except Exception:
            cached_script = None

    if not cached_script:
        # --- Generate fresh script (costs Gemini credits) ---
        script_segments, topic = generate_script(topic, video_format=fmt, content_type_key=content_type_key)
        # --- Update safe_topic now that we know the actual topic ---
        safe_topic = topic.replace(" ", "_").replace("'", "")[:50]
        real_temp = os.path.join(config.TEMP_DIR, f"{safe_topic}_{fmt.value}")
        if real_temp != video_temp:
            if os.path.exists(real_temp):
                video_temp = real_temp
            else:
                os.rename(video_temp, real_temp)
                video_temp = real_temp
        # --- Cache script segments for retry ---
        script_cache_path = os.path.join(video_temp, "script_segments.json")
        with open(script_cache_path, "w", encoding="utf-8") as f:
            json.dump({"topic": topic, "segments": script_segments}, f, indent=2)
        print(f"[SCRIPT] Cached to {os.path.basename(script_cache_path)}")

    full_script = get_script_text(script_segments)

    # --- ElevenLabs voiceover generation ---
    # voiceover.py has its own cache check — stable dir means retries skip ElevenLabs
    progress(0.10, desc="Creating voiceover (ElevenLabs)...")
    voiceover_path = os.path.join(video_temp, "voiceover.mp3")
    word_timestamps = generate_voiceover(full_script, voiceover_path, profile=profile)
    # --- Use trimmed voiceover if it exists (pause trimming creates _trimmed.mp3) ---
    trimmed_path = voiceover_path.replace(".mp3", "_trimmed.mp3")
    actual_voiceover = trimmed_path if os.path.exists(trimmed_path) else voiceover_path
    audio_duration = get_audio_duration(actual_voiceover)

    # --- Download stock footage matching content type visual keywords ---
    progress(0.25, desc=f"Downloading {ct['name']} footage...")
    clips_dir = os.path.join(video_temp, "clips")
    clip_paths = search_and_download_videos(script_segments, clips_dir, profile=profile, content_type_key=content_type_key)

    if not clip_paths:
        raise gr.Error("No footage downloaded. Check Pexels/Pixabay API keys.")

    # --- Build word-synced caption events from ElevenLabs timestamps ---
    progress(0.45, desc="Building word-synced captions...")
    caption_events = create_caption_clips(word_timestamps, script_segments, audio_duration)

    # --- Select background music matching the content type's mood ---
    progress(0.50, desc=f"Selecting {ct['music_mood']} background music...")
    music_path = select_music(script_segments, content_type_key=content_type_key)

    # --- Final assembly: stitch clips, voice, captions, music ---
    progress(0.55, desc="Assembling video...")
    # --- Timestamp only on the output filename, not the work dir ---
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_name = f"{safe_topic}_{timestamp}"
    output_path = os.path.join(config.OUTPUT_DIR, f"{video_name}.mp4")

    assemble_video(
        clip_paths=clip_paths,
        voiceover_path=actual_voiceover,
        caption_events=caption_events,
        script_segments=script_segments,
        music_path=music_path,
        output_path=output_path,
        video_format=fmt,
    )

    # --- Generate thumbnail from the best video frame ---
    progress(0.80, desc="Generating thumbnail...")
    thumbnail_path = None
    try:
        if fmt == VideoFormat.VERTICAL_SHORT:
            thumbnail_path = generate_reel_thumbnail(output_path, topic)
        else:
            thumbnail_path = generate_thumbnail(output_path, topic)
    except Exception as e:
        print(f"[THUMBNAIL] Skipped: {e}")

    # --- Generate viral platform metadata (titles, captions, hashtags) ---
    progress(0.88, desc="Generating platform metadata...")
    metadata = None
    try:
        metadata = generate_metadata(topic, script_segments, fmt.value)
        # # Save metadata as a JSON sidecar file alongside the video
        # # e.g. output/Power_of_Silence_20260720.mp4 → ...metadata.json
        if metadata:
            meta_path = output_path.replace(".mp4", "_metadata.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"[METADATA] Saved sidecar: {meta_path}")
    except Exception as e:
        print(f"[METADATA] Skipped: {e}")

    # --- Remove temp working directory to free disk space ---
    # Only clean up on SUCCESS — if the pipeline fails partway through,
    # the cached voiceover + script stay for the retry run
    progress(0.95, desc="Cleaning up...")
    shutil.rmtree(video_temp, ignore_errors=True)

    elapsed = time.time() - start_time
    progress(1.0, desc=f"Done! ({elapsed:.0f}s)")

    # --- Build summary with metadata preview ---
    summary = f"**{ct['name']}: {topic}** ({fmt.value})\n\nGenerated in {elapsed:.0f} seconds | {len(script_segments)} segments | {audio_duration:.0f}s voiceover"
    if thumbnail_path:
        summary += f"\n\n**Thumbnail:** Generated"
    if metadata:
        if "youtube" in metadata:
            summary += f"\n\n**YouTube Title:** {metadata['youtube'].get('title', 'N/A')}"
        if "tiktok" in metadata:
            summary += f"\n\n**TikTok Caption:** {metadata['tiktok'].get('caption', 'N/A')[:100]}..."

    return output_path, summary


# ============================================================
# GRADIO INTERFACE
# ============================================================

# --- Custom dark CSS matching Luminous Will brand ---
custom_css = """
.gradio-container {
    background: linear-gradient(180deg, #0a0a0a 0%, #111111 100%) !important;
    font-family: 'Inter', sans-serif !important;
}
.main-title {
    text-align: center;
    color: #E8A817 !important;
    font-size: 2em !important;
    font-weight: 700 !important;
    letter-spacing: 3px;
    margin-bottom: 0.2em !important;
}
.subtitle {
    text-align: center;
    color: #888 !important;
    font-size: 1em !important;
    margin-bottom: 2em !important;
}
"""

with gr.Blocks(
    title="Luminous Will - Video Generator",
    css=custom_css,
    theme=gr.themes.Base(
        primary_hue="amber",
        neutral_hue="zinc",
        font=gr.themes.GoogleFont("Inter"),
    ),
) as demo:

    gr.HTML('<h1 class="main-title">LUMINOUS WILL</h1>')
    gr.HTML('<p class="subtitle">Automated Video Generator</p>')

    with gr.Row():
        with gr.Column(scale=1):
            # --- Content type selector ---
            # Choices are built dynamically from CONTENT_TYPES registry
            # so adding a new type in content_types.py auto-appears here
            content_type_dropdown = gr.Dropdown(
                choices=[(ct["name"], key) for key, ct in CONTENT_TYPES.items()],
                value="dark_motivation",
                label="Content Type",
                info="Each type has unique visual style, topics, and music mood",
            )
            format_dropdown = gr.Dropdown(
                choices=["Vertical Short (9:16)", "Horizontal Long (16:9)"],
                value="Vertical Short (9:16)",
                label="Video Format",
                info="Short = 60-90s for Reels/TikTok. Long = 8-12 min for YouTube.",
            )
            # --- Topic dropdown starts with dark_motivation topics ---
            # Will be updated dynamically when content type changes
            topic_dropdown = gr.Dropdown(
                choices=["(Random)"] + CONTENT_TYPES["dark_motivation"]["topics"],
                value="(Random)",
                label="Select Topic",
                info="Pick a topic or choose Random",
            )
            custom_topic = gr.Textbox(
                label="Or Type a Custom Topic",
                placeholder="e.g., Why discipline beats motivation",
                lines=1,
            )
            generate_btn = gr.Button(
                "Generate Video",
                variant="primary",
                size="lg",
            )

        with gr.Column(scale=2):
            # --- Output area: video player + metadata text ---
            video_output = gr.Video(label="Generated Video")
            info_output = gr.Markdown(label="Details")

    # --- Update topic list when content type changes ---
    # When the user picks a different content type the topic dropdown
    # is rebuilt with that type's specific topic pool
    def update_topics(content_type_key):
        # Load the selected content type and return its topics as new choices
        ct = get_content_type(content_type_key)
        return gr.Dropdown(choices=["(Random)"] + ct["topics"])

    # Wire content type dropdown change to topic refresh
    content_type_dropdown.change(
        fn=update_topics,
        inputs=[content_type_dropdown],
        outputs=[topic_dropdown],
    )

    def on_generate(content_type_key, format_choice, dropdown_topic, custom, progress=gr.Progress()):
        # --- Resolve topic: custom text > dropdown > random ---
        # Custom text takes highest priority so users can go off-topic-list
        topic = custom.strip() if custom and custom.strip() else None
        if topic is None and dropdown_topic and dropdown_topic != "(Random)":
            # Use dropdown selection if no custom text entered
            topic = dropdown_topic
        # None at this point means generate_video will pick randomly
        fmt_str = "long" if "Long" in format_choice else "short"
        # --- Wrap the full pipeline in try/catch ---
        # Without this, any crash (Gemini API error, missing file, MoviePy OOM)
        # propagates as an opaque "An error occurred" to the dashboard.
        # With this, the user sees WHAT actually broke.
        try:
            return generate_video(topic, fmt_str, content_type_key=content_type_key, progress=progress)
        except gr.Error:
            # # gr.Error already has a user-friendly message, re-raise as-is
            raise
        except Exception as e:
            # # Convert raw Python exceptions to clear Gradio errors
            error_msg = str(e)
            # # Tag the error with which pipeline step likely failed
            if "genai" in error_msg.lower() or "gemini" in error_msg.lower() or "404" in error_msg:
                raise gr.Error(f"Script generation failed (Gemini API): {error_msg}")
            elif "elevenlabs" in error_msg.lower() or "quota" in error_msg.lower():
                raise gr.Error(f"Voiceover failed (ElevenLabs): {error_msg}")
            elif "pexels" in error_msg.lower() or "pixabay" in error_msg.lower():
                raise gr.Error(f"Footage download failed: {error_msg}")
            elif "moviepy" in error_msg.lower() or "ffmpeg" in error_msg.lower():
                raise gr.Error(f"Video assembly failed (MoviePy): {error_msg}")
            else:
                raise gr.Error(f"Pipeline error: {error_msg}")

    # --- Connect generate button to pipeline ---
    # Note: content_type_dropdown is now the first input (added in Task 7)
    generate_btn.click(
        fn=on_generate,
        inputs=[content_type_dropdown, format_dropdown, topic_dropdown, custom_topic],
        outputs=[video_output, info_output],
    )

if __name__ == "__main__":
    # --- Launch with queue to serialize concurrent requests ---
    # default_concurrency_limit=1 prevents GPU/memory contention
    demo.queue(default_concurrency_limit=1).launch(show_error=True)
