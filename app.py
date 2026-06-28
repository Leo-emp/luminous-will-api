import os
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
    if not config.ELEVENLABS_API_KEY:
        errors.append("ELEVENLABS_API_KEY not set (add it in HF Space Secrets)")
    if not config.PEXELS_API_KEY:
        errors.append("PEXELS_API_KEY not set (add it in HF Space Secrets)")
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
    # Previously, when topic was None, generate_script did random.choice(ct["topics"])
    # internally — meaning it could repeat any topic at random.
    # Now we call pick_unused_topic BEFORE generate_script so the scheduler tracks
    # exactly which topics have been used and never repeats one until all are exhausted.
    if not topic or topic.strip() == "":
        # No topic specified — ask the scheduler for a never-used topic
        topic = pick_unused_topic(content_type_key)

    script_segments, topic = generate_script(topic, video_format=fmt, content_type_key=content_type_key)
    full_script = get_script_text(script_segments)

    # --- Build unique temp folder for this video's working files ---
    safe_topic = topic.replace(" ", "_").replace("'", "")[:50]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_name = f"{safe_topic}_{timestamp}"
    video_temp = os.path.join(config.TEMP_DIR, video_name)
    os.makedirs(video_temp, exist_ok=True)

    # --- ElevenLabs voiceover generation ---
    progress(0.10, desc="Creating voiceover (ElevenLabs)...")
    voiceover_path = os.path.join(video_temp, "voiceover.mp3")
    word_timestamps = generate_voiceover(full_script, voiceover_path, profile=profile)
    audio_duration = get_audio_duration(voiceover_path)

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
    output_path = os.path.join(config.OUTPUT_DIR, f"{video_name}.mp4")

    assemble_video(
        clip_paths=clip_paths,
        voiceover_path=voiceover_path,
        caption_events=caption_events,
        script_segments=script_segments,
        music_path=music_path,
        output_path=output_path,
        video_format=fmt,
    )

    # --- Remove temp working directory to free disk space ---
    progress(0.95, desc="Cleaning up...")
    shutil.rmtree(video_temp, ignore_errors=True)

    elapsed = time.time() - start_time
    progress(1.0, desc=f"Done! ({elapsed:.0f}s)")

    # --- Return video file path + summary markdown for Gradio UI ---
    return output_path, f"**{ct['name']}: {topic}** ({fmt.value})\n\nGenerated in {elapsed:.0f} seconds | {len(script_segments)} segments | {audio_duration:.0f}s voiceover"


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
        # Pass content_type_key so the right visual style is applied
        return generate_video(topic, fmt_str, content_type_key=content_type_key, progress=progress)

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
    demo.queue(default_concurrency_limit=1).launch()
