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

# ============================================================
# LUMINOUS WILL - CLOUD VIDEO PIPELINE (Gradio API)
# Generates dark aesthetic motivational videos via web interface
# Deployed on Hugging Face Spaces
# ============================================================




def validate_setup():
    # --- Check API keys before starting ---
    errors = []
    if not config.ELEVENLABS_API_KEY:
        errors.append("ELEVENLABS_API_KEY not set (add it in HF Space Secrets)")
    if not config.PEXELS_API_KEY:
        errors.append("PEXELS_API_KEY not set (add it in HF Space Secrets)")
    if errors:
        return False, "\n".join(errors)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    os.makedirs(config.MUSIC_DIR, exist_ok=True)
    return True, "All checks passed"


def generate_video(topic, video_format_str="short", progress=gr.Progress()):
    # --- Main pipeline with format support ---

    from config import VideoFormat, get_format_profile

    fmt = VideoFormat.HORIZONTAL_LONG if video_format_str == "long" else VideoFormat.VERTICAL_SHORT
    profile = get_format_profile(fmt)

    start_time = time.time()

    progress(0.0, desc="Checking setup...")
    ok, msg = validate_setup()
    if not ok:
        raise gr.Error(f"Setup error: {msg}")

    validate_references()

    progress(0.05, desc="Generating script...")
    if not topic or topic.strip() == "":
        topic = None
    script_segments, topic = generate_script(topic, video_format=fmt)
    full_script = get_script_text(script_segments)

    safe_topic = topic.replace(" ", "_").replace("'", "")[:50]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_name = f"{safe_topic}_{timestamp}"
    video_temp = os.path.join(config.TEMP_DIR, video_name)
    os.makedirs(video_temp, exist_ok=True)

    progress(0.10, desc="Creating voiceover (ElevenLabs)...")
    voiceover_path = os.path.join(video_temp, "voiceover.mp3")
    word_timestamps = generate_voiceover(full_script, voiceover_path, profile=profile)
    audio_duration = get_audio_duration(voiceover_path)

    progress(0.25, desc="Downloading stock footage...")
    clips_dir = os.path.join(video_temp, "clips")
    clip_paths = search_and_download_videos(script_segments, clips_dir, profile=profile)

    if not clip_paths:
        raise gr.Error("No footage downloaded. Check Pexels/Pixabay API keys.")

    progress(0.45, desc="Building word-synced captions...")
    caption_events = create_caption_clips(word_timestamps, script_segments, audio_duration)

    progress(0.50, desc="Selecting background music...")
    music_path = select_music(script_segments)

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

    progress(0.95, desc="Cleaning up...")
    shutil.rmtree(video_temp, ignore_errors=True)

    elapsed = time.time() - start_time
    progress(1.0, desc=f"Done! ({elapsed:.0f}s)")

    return output_path, f"**{topic}** ({fmt.value})\n\nGenerated in {elapsed:.0f} seconds | {len(script_segments)} segments | {audio_duration:.0f}s voiceover"


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
    gr.HTML('<p class="subtitle">Dark Motivation Video Generator</p>')

    with gr.Row():
        with gr.Column(scale=1):
            format_dropdown = gr.Dropdown(
                choices=["Vertical Short (9:16)", "Horizontal Long (16:9)"],
                value="Vertical Short (9:16)",
                label="Video Format",
                info="Short = 60-90s for Reels/TikTok. Long = 8-12 min for YouTube.",
            )
            topic_dropdown = gr.Dropdown(
                choices=["(Random)"] + config.TRENDING_TOPICS,
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
            video_output = gr.Video(label="Generated Video")
            info_output = gr.Markdown(label="Details")

    def on_generate(format_choice, dropdown_topic, custom, progress=gr.Progress()):
        topic = custom.strip() if custom and custom.strip() else None
        if topic is None and dropdown_topic and dropdown_topic != "(Random)":
            topic = dropdown_topic
        fmt_str = "long" if "Long" in format_choice else "short"
        return generate_video(topic, fmt_str, progress)

    generate_btn.click(
        fn=on_generate,
        inputs=[format_dropdown, topic_dropdown, custom_topic],
        outputs=[video_output, info_output],
    )

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch()
