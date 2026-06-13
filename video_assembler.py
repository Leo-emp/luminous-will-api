import os
import numpy as np
from PIL import Image
from moviepy import (
    VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip,
    CompositeAudioClip, concatenate_videoclips, vfx, afx
)
import config
from color_grading import apply_dark_grade
from captions import render_caption_frame

# ============================================================
# VIDEO ASSEMBLER
# Assembles the final video from all components:
# - Stock footage clips (color graded)
# - Voiceover audio
# - Word-synced captions with highlights
# - Background music (encouraging but never overpowering voice)
# - Logo outro
#
# CRITICAL: Each visual clip is synced to its matching script
# segment so visuals always match what's being said at that
# exact moment in the voiceover.
# ============================================================


def assemble_video(
    clip_paths,
    voiceover_path,
    caption_events,
    script_segments,
    music_path,
    output_path,
    video_format=None,
):
    """
    # Main assembly function - builds the complete video
    # Format-aware: uses profile settings for resolution, bitrate,
    # transitions, and music mixing mode.
    """

    from config import VideoFormat, get_format_profile

    if video_format is None:
        video_format = VideoFormat.VERTICAL_SHORT

    profile = get_format_profile(video_format)
    print(f"[ASSEMBLER] Format: {video_format.value} ({profile['width']}x{profile['height']})")
    print("[ASSEMBLER] Starting video assembly...")

    # --- Step 1: Load voiceover and get total duration ---
    voiceover = AudioFileClip(voiceover_path)
    total_duration = voiceover.duration
    print(f"[ASSEMBLER] Voiceover duration: {total_duration:.1f}s")

    # --- Step 2: Build the visual timeline ---
    visual_timeline = build_visual_timeline(
        clip_paths, script_segments, caption_events, total_duration
    )

    # --- Step 3: Create base video ---
    base_video = create_base_video(visual_timeline, total_duration, profile)
    print(f"[ASSEMBLER] Base video created: {base_video.duration:.1f}s")

    # --- Step 4: Burn captions on-the-fly ---
    print(f"[ASSEMBLER] {len(caption_events)} captions will be burned on-the-fly")
    _caption_render_cache = {}
    frame_w = profile["width"]
    frame_h = profile["height"]

    def burn_captions(get_frame, t):
        frame = get_frame(t)
        for i, event in enumerate(caption_events):
            if event["start"] <= t < event["end"]:
                if i not in _caption_render_cache:
                    _caption_render_cache.clear()
                    rgba = render_caption_frame(
                        event["text"],
                        event.get("highlight_word"),
                        frame_w,
                        frame_h,
                        font_size=profile["caption_font_size"],
                        position_y=profile["caption_position_y"],
                        stroke_width=profile["caption_stroke_width"],
                    )
                    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
                    rgb = rgba[:, :, :3].astype(np.float32)
                    _caption_render_cache[i] = (alpha, rgb)
                a, rgb = _caption_render_cache[i]
                result = frame.astype(np.float32)
                result = result * (1.0 - a) + rgb * a
                return result.astype(np.uint8)
        return frame

    composited = base_video.transform(burn_captions)
    composited = composited.with_duration(total_duration)

    # --- Step 5: Add logo outro ---
    logo_clip = create_logo_outro(profile)
    if logo_clip:
        final_video = concatenate_videoclips([composited, logo_clip], method="chain")
    else:
        final_video = composited

    # --- Step 6: Mix audio ---
    final_audio = mix_audio(voiceover, music_path, total_duration, profile)
    final_video = final_video.with_audio(final_audio)

    # --- Step 7: Export ---
    print(f"[ASSEMBLER] Exporting final video to: {output_path}")
    final_video.write_videofile(
        output_path,
        fps=profile["fps"],
        codec="libx264",
        audio_codec="aac",
        bitrate=profile["bitrate"],
        preset="slow",
        threads=4,
    )

    # --- Cleanup ---
    voiceover.close()
    base_video.close()
    final_video.close()

    print(f"[ASSEMBLER] Video exported successfully: {output_path}")
    return output_path


def build_visual_timeline(clip_paths, script_segments, caption_events, total_duration):
    """
    # Maps each visual clip to the EXACT time range of its matching
    # script segment so the visual always matches the storyline.
    #
    # How it works:
    #   - Each script segment has a corresponding downloaded clip
    #   - We use word timestamps from captions to find when each
    #     segment starts and ends in the voiceover
    #   - The clip plays during that exact time window
    #
    # Example:
    #   Script segment: "A lion doesn't lose sleep over the opinion of sheep"
    #   Visual keywords: "lion portrait dark dramatic"
    #   Voiceover says this at: 28.5s - 32.1s
    #   -> Lion footage plays from 28.5s to 32.1s
    #
    # Returns: list of {path, start, end, duration}
    """

    num_clips = len(clip_paths)
    num_segments = len(script_segments)
    if num_clips == 0:
        return []

    # --- Calculate time boundaries for each script segment ---
    # Use caption events (which have word timestamps) to find when
    # each segment of the script is being spoken
    segment_times = calculate_segment_times(
        script_segments, caption_events, total_duration
    )

    timeline = []

    for i in range(num_clips):
        # Get the time window for this segment
        if i < len(segment_times):
            start = segment_times[i]["start"]
            end = segment_times[i]["end"]
        else:
            # More clips than segments: distribute remaining time evenly
            remaining_start = segment_times[-1]["end"] if segment_times else 0
            remaining_duration = total_duration - remaining_start
            extra_clips = num_clips - len(segment_times)
            clip_idx = i - len(segment_times)
            per_clip = remaining_duration / extra_clips if extra_clips > 0 else 0
            start = remaining_start + clip_idx * per_clip
            end = start + per_clip

        timeline.append({
            "path": clip_paths[i],
            "start": start,
            "end": end,
            "duration": end - start,
        })

        # Log what visual is playing during which part of the script
        segment_text = script_segments[i]["text"][:50] if i < num_segments else "..."
        print(f"[TIMELINE] {start:.1f}s-{end:.1f}s: \"{segment_text}...\"")

    return timeline


def calculate_segment_times(script_segments, caption_events, total_duration):
    """
    # Figures out WHEN each script segment is spoken in the voiceover
    # by matching segment text to caption event timestamps.
    #
    # This is what ensures visuals sync to the storyline:
    #   - When the voice says "lion", the lion clip is playing
    #   - When the voice says "chess", the chess clip is playing
    #
    # Returns: list of {start, end} times for each segment
    """

    segment_times = []
    num_segments = len(script_segments)

    if not caption_events:
        # Fallback: divide time equally if no timestamps available
        per_segment = total_duration / num_segments
        for i in range(num_segments):
            segment_times.append({
                "start": i * per_segment,
                "end": (i + 1) * per_segment,
            })
        return segment_times

    # --- Match each script segment to caption timestamps ---
    # Caption events contain word-level timing from ElevenLabs
    # We find which caption events belong to which script segment
    # by matching the words in each segment to the caption text

    # Build a flat list of all words with their timestamps
    all_words = []
    for event in caption_events:
        if event.get("words"):
            for w in event["words"]:
                all_words.append(w)
        else:
            # If no individual word timing, use event timing
            for word in event["text"].split():
                all_words.append({
                    "word": word,
                    "start": event["start"],
                    "end": event["end"],
                })

    if not all_words:
        # Fallback: divide time equally
        per_segment = total_duration / num_segments
        for i in range(num_segments):
            segment_times.append({
                "start": i * per_segment,
                "end": (i + 1) * per_segment,
            })
        return segment_times

    # --- Walk through script segments and find their time boundaries ---
    word_index = 0

    for seg_idx, segment in enumerate(script_segments):
        seg_words = segment["text"].split()
        seg_word_count = len(seg_words)

        # Find the start time: where this segment's first word begins
        if word_index < len(all_words):
            seg_start = all_words[word_index]["start"]
        else:
            # Past the end of timestamps, estimate from last known position
            seg_start = all_words[-1]["end"] if all_words else 0

        # Find the end time: where this segment's last word ends
        end_index = min(word_index + seg_word_count - 1, len(all_words) - 1)
        if end_index >= 0 and end_index < len(all_words):
            seg_end = all_words[end_index]["end"]
        else:
            seg_end = total_duration

        segment_times.append({
            "start": seg_start,
            "end": seg_end,
        })

        # Advance the word pointer past this segment's words
        word_index += seg_word_count

    # --- Make sure the last segment extends to the end of the audio ---
    if segment_times:
        segment_times[-1]["end"] = total_duration

    return segment_times


def create_base_video(visual_timeline, total_duration, profile):
    """
    # Creates the base video processing clips one at a time.
    # Uses profile for resolution, bitrate, color grading, and transitions.
    """
    import subprocess
    from color_grading import create_grader

    temp_clip_dir = os.path.join(config.TEMP_DIR, "_graded_clips")
    os.makedirs(temp_clip_dir, exist_ok=True)

    grader = create_grader(profile)
    frame_w = profile["width"]
    frame_h = profile["height"]
    bitrate = profile["bitrate"]

    graded_paths = []
    actual_duration = 0.0

    for idx, entry in enumerate(visual_timeline):
        needed = entry["duration"]
        if needed <= 0:
            continue

        graded_path = os.path.join(temp_clip_dir, f"graded_{idx:03d}.mp4")
        try:
            clip = VideoFileClip(entry["path"])
            clip = fit_clip(clip, profile)

            if clip.duration >= needed:
                clip = clip.subclipped(0, needed)
            else:
                loops_needed = int(needed / clip.duration) + 1
                clip = concatenate_videoclips([clip] * loops_needed, method="chain")
                clip = clip.subclipped(0, needed)

            clip = clip.image_transform(grader)

            clip.write_videofile(
                graded_path, fps=profile["fps"], codec="libx264",
                bitrate=bitrate, preset="fast", threads=2,
                audio=False, logger=None,
            )
            clip.close()
            del clip
            actual_duration += needed
            graded_paths.append(graded_path)
            print(f"[ASSEMBLER] Graded clip {idx+1}/{len(visual_timeline)}")

        except Exception as e:
            print(f"[ASSEMBLER] Error on clip {idx}: {e}")
            black = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
            blk = ImageClip(black).with_duration(needed)
            blk.write_videofile(
                graded_path, fps=profile["fps"], codec="libx264",
                audio=False, logger=None,
            )
            blk.close()
            actual_duration += needed
            graded_paths.append(graded_path)

    # --- Extend if too short ---
    if actual_duration < total_duration and graded_paths:
        gap = total_duration - actual_duration
        print(f"[ASSEMBLER] Extending last clip by {gap:.1f}s to fill duration")
        last_path = visual_timeline[-1]["path"]
        filler_path = os.path.join(temp_clip_dir, "graded_filler.mp4")
        clip = VideoFileClip(last_path)
        clip = fit_clip(clip, profile)
        if clip.duration < gap:
            clip = concatenate_videoclips([clip] * (int(gap / clip.duration) + 1), method="chain")
        clip = clip.subclipped(0, gap)
        clip = clip.image_transform(grader)
        clip.write_videofile(
            filler_path, fps=profile["fps"], codec="libx264",
            bitrate=bitrate, preset="fast", threads=2,
            audio=False, logger=None,
        )
        clip.close()
        graded_paths.append(filler_path)

    # --- Concatenate via ffmpeg ---
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    concat_list = os.path.join(temp_clip_dir, "concat_list.txt")
    with open(concat_list, "w") as f:
        for p in graded_paths:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")

    base_path = os.path.join(temp_clip_dir, "base_video.mp4")
    subprocess.run([
        ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", base_path,
    ], capture_output=True)

    return VideoFileClip(base_path)


def fit_to_vertical(clip):
    """
    # Resizes and crops a clip to 1080x1920 (9:16 portrait)
    # If clip is landscape, we crop the center
    # If clip is portrait, we just resize
    """

    target_w = config.VIDEO_WIDTH   # 1080
    target_h = config.VIDEO_HEIGHT  # 1920
    target_ratio = target_w / target_h  # 0.5625

    clip_w, clip_h = clip.size
    clip_ratio = clip_w / clip_h

    if clip_ratio > target_ratio:
        # Clip is wider than needed (landscape) -> crop sides
        new_h = target_h
        new_w = int(clip_w * (target_h / clip_h))
        clip = clip.resized(height=new_h)
        # Crop center
        x_center = new_w // 2
        x1 = x_center - target_w // 2
        clip = clip.cropped(x1=x1, y1=0, x2=x1 + target_w, y2=target_h)
    else:
        # Clip is taller or matches -> crop top/bottom
        new_w = target_w
        new_h = int(clip_h * (target_w / clip_w))
        clip = clip.resized(width=new_w)
        # Crop center vertically
        y_center = new_h // 2
        y1 = y_center - target_h // 2
        y1 = max(0, y1)
        clip = clip.cropped(x1=0, y1=y1, x2=target_w, y2=y1 + target_h)

    return clip


def fit_to_horizontal(clip, profile):
    """
    # Resizes and crops a clip to 1920x1080 (16:9 landscape)
    # Landscape footage fills perfectly; portrait is center-cropped
    """
    target_w = profile["width"]    # 1920
    target_h = profile["height"]   # 1080
    target_ratio = target_w / target_h  # 1.7778

    clip_w, clip_h = clip.size
    clip_ratio = clip_w / clip_h

    if clip_ratio > target_ratio:
        # Clip is wider than needed -> crop sides
        new_h = target_h
        new_w = int(clip_w * (target_h / clip_h))
        clip = clip.resized(height=new_h)
        x_center = new_w // 2
        x1 = x_center - target_w // 2
        clip = clip.cropped(x1=x1, y1=0, x2=x1 + target_w, y2=target_h)
    else:
        # Clip is taller or matches -> crop top/bottom
        new_w = target_w
        new_h = int(clip_h * (target_w / clip_w))
        clip = clip.resized(width=new_w)
        y_center = new_h // 2
        y1 = y_center - target_h // 2
        y1 = max(0, y1)
        clip = clip.cropped(x1=0, y1=y1, x2=target_w, y2=y1 + target_h)

    return clip


def fit_clip(clip, profile):
    """
    # Routes to the correct fit function based on format profile
    """
    if profile["width"] > profile["height"]:
        return fit_to_horizontal(clip, profile)
    else:
        return fit_to_vertical(clip)


def create_caption_overlay(caption_events, total_duration, profile=None):
    """
    # Creates transparent caption overlay clips
    """
    frame_w = profile["width"] if profile else config.VIDEO_WIDTH
    frame_h = profile["height"] if profile else config.VIDEO_HEIGHT

    caption_clips = []
    for event in caption_events:
        caption_frame = render_caption_frame(
            event["text"],
            event.get("highlight_word"),
            frame_w,
            frame_h,
            font_size=profile["caption_font_size"] if profile else None,
            position_y=profile["caption_position_y"] if profile else None,
            stroke_width=profile["caption_stroke_width"] if profile else None,
        )
        caption_clip = (
            ImageClip(caption_frame)
            .with_duration(event["end"] - event["start"])
            .with_start(event["start"])
        )
        caption_clips.append(caption_clip)

    return caption_clips


def create_logo_outro(profile=None):
    """
    # Creates the logo outro clip sized to match the current format
    """

    if not os.path.exists(config.LOGO_PATH):
        print("[ASSEMBLER] WARNING: Logo not found, skipping outro")
        return None

    if profile is None:
        frame_w = config.VIDEO_WIDTH
        frame_h = config.VIDEO_HEIGHT
    else:
        frame_w = profile["width"]
        frame_h = profile["height"]

    logo_img = Image.open(config.LOGO_PATH).convert("RGBA")

    img_ratio = logo_img.width / logo_img.height
    target_ratio = frame_w / frame_h

    if img_ratio > target_ratio:
        new_w = frame_w
        new_h = int(new_w / img_ratio)
    else:
        new_h = frame_h
        new_w = int(new_h * img_ratio)

    logo_img = logo_img.resize((new_w, new_h), Image.LANCZOS)

    bg = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 255))
    x = (frame_w - new_w) // 2
    y = (frame_h - new_h) // 2
    bg.paste(logo_img, (x, y), logo_img)

    logo_array = np.array(bg.convert("RGB"))
    logo_clip = ImageClip(logo_array).with_duration(config.LOGO_DURATION)
    logo_clip = logo_clip.with_effects([vfx.CrossFadeIn(1.0)])

    return logo_clip


def mix_audio(voiceover, music_path, voiceover_duration, profile=None):
    """
    # Mixes voiceover with background music.
    # Two modes based on profile:
    #   - "flat": constant music volume (for short-form)
    #   - "ducking": dynamic volume — dips during voice, rises in pauses (for long-form)
    """

    total_duration = voiceover_duration + config.LOGO_DURATION
    audio_layers = [voiceover]

    if music_path and os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path)

            if music.duration < total_duration:
                loops = int(total_duration / music.duration) + 1
                music = music.looped(n=loops)

            music = music.subclipped(0, total_duration)

            music_mode = profile.get("music_mode", "flat") if profile else "flat"
            base_vol = profile.get("music_volume", 0.32) if profile else config.MUSIC_VOLUME

            if music_mode == "ducking":
                high_vol = profile.get("music_volume_high", 0.45)

                # Sample voiceover RMS in 0.5s windows to detect speech vs silence
                vo_audio = voiceover.to_soundarray(fps=22050)
                window_samples = int(22050 * 0.5)
                rms_values = []
                for start in range(0, len(vo_audio), window_samples):
                    chunk = vo_audio[start:start + window_samples]
                    rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0
                    rms_values.append(rms)

                # Threshold: below this RMS = silence/pause
                threshold = np.percentile(rms_values, 25) if rms_values else 0.01

                def duck_volume(get_frame, t):
                    window_idx = min(int(t / 0.5), len(rms_values) - 1)
                    if window_idx < 0:
                        window_idx = 0
                    rms = rms_values[window_idx] if window_idx < len(rms_values) else 0

                    if rms > threshold:
                        vol = base_vol
                    else:
                        vol = high_vol

                    frame = get_frame(t)
                    return (frame * vol).astype(frame.dtype)

                music = music.transform(duck_volume, keep_duration=True)
                print(f"[ASSEMBLER] Dynamic music ducking: {base_vol*100:.0f}% (voice) / {high_vol*100:.0f}% (pauses)")
            else:
                music = music.with_volume_scaled(base_vol)
                print(f"[ASSEMBLER] Flat music at {base_vol*100:.0f}% volume")

            music = music.with_effects([afx.AudioFadeIn(2.0), afx.AudioFadeOut(3.0)])
            audio_layers.append(music)

        except Exception as e:
            print(f"[ASSEMBLER] Could not load music: {e}")

    if len(audio_layers) > 1:
        return CompositeAudioClip(audio_layers)
    else:
        return voiceover


# --- Quick test ---
if __name__ == "__main__":
    print("Video assembler module loaded successfully")
    print(f"Output resolution: {config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}")
    print(f"FPS: {config.VIDEO_FPS}")
    print(f"Music volume: {config.MUSIC_VOLUME*100:.0f}% (voice is {1.0/config.MUSIC_VOLUME:.0f}x louder)")
