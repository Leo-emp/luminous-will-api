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
from music import download_background_music

# ============================================================
# LUMINOUS WILL - CLOUD VIDEO PIPELINE (Gradio API)
# Generates dark aesthetic motivational videos via web interface
# Deployed on Hugging Face Spaces
# ============================================================


def find_background_music():
    # --- Check for cached music in /tmp ---
    if not os.path.exists(config.MUSIC_DIR):
        return None
    for f in os.listdir(config.MUSIC_DIR):
        if f.endswith((".mp3", ".wav", ".m4a")):
            return os.path.join(config.MUSIC_DIR, f)
    return None


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


def generate_video(topic, progress=gr.Progress()):
    # --- Main pipeline: generates a complete Luminous Will video ---

    start_time = time.time()

    # --- Step 0: Validate ---
    progress(0.0, desc="Checking setup...")
    ok, msg = validate_setup()
    if not ok:
        raise gr.Error(f"Setup error: {msg}")

    validate_references()

    # --- Step 1: Generate script ---
    progress(0.05, desc="Generating script...")
    if not topic or topic.strip() == "":
        topic = None
    script_segments, topic = generate_script(topic)
    full_script = get_script_text(script_segments)

    safe_topic = topic.replace(" ", "_").replace("'", "")[:50]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    video_name = f"{safe_topic}_{timestamp}"
    video_temp = os.path.join(config.TEMP_DIR, video_name)
    os.makedirs(video_temp, exist_ok=True)

    # --- Step 2: Generate voiceover ---
    progress(0.10, desc="Creating voiceover (ElevenLabs)...")
    voiceover_path = os.path.join(video_temp, "voiceover.mp3")
    word_timestamps = generate_voiceover(full_script, voiceover_path)
    audio_duration = get_audio_duration(voiceover_path)

    # --- Step 3: Download stock footage ---
    progress(0.25, desc="Downloading stock footage...")
    clips_dir = os.path.join(video_temp, "clips")
    clip_paths = search_and_download_videos(script_segments, clips_dir)

    if not clip_paths:
        raise gr.Error("No footage downloaded. Check Pexels/Pixabay API keys.")

    # --- Step 4: Build captions ---
    progress(0.45, desc="Building word-synced captions...")
    caption_events = create_caption_clips(word_timestamps, script_segments, audio_duration)

    # --- Step 5: Find or download music ---
    progress(0.50, desc="Getting background music...")
    music_path = find_background_music()
    if not music_path:
        music_path = download_background_music()

    # --- Step 6: Assemble video ---
    progress(0.55, desc="Assembling video (color grading + captions + music)...")
    output_path = os.path.join(config.OUTPUT_DIR, f"{video_name}.mp4")

    assemble_video(
        clip_paths=clip_paths,
        voiceover_path=voiceover_path,
        caption_events=caption_events,
        script_segments=script_segments,
        music_path=music_path,
        output_path=output_path,
    )

    # --- Cleanup temp files ---
    progress(0.95, desc="Cleaning up...")
    shutil.rmtree(video_temp, ignore_errors=True)

    elapsed = time.time() - start_time
    progress(1.0, desc=f"Done! ({elapsed:.0f}s)")

    return output_path, f"**{topic}**\n\nGenerated in {elapsed:.0f} seconds | {len(script_segments)} segments | {audio_duration:.0f}s voiceover"


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

    def on_generate(dropdown_topic, custom, progress=gr.Progress()):
        # --- Use custom topic if provided, else dropdown ---
        topic = custom.strip() if custom and custom.strip() else None
        if topic is None and dropdown_topic and dropdown_topic != "(Random)":
            topic = dropdown_topic
        return generate_video(topic, progress)

    generate_btn.click(
        fn=on_generate,
        inputs=[topic_dropdown, custom_topic],
        outputs=[video_output, info_output],
    )

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch()
