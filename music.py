import os
import random
import requests
import config

# ============================================================
# MUSIC SELECTOR
# Picks the best background music for each video based on mood
#
# TRACK ORGANIZATION:
#   Option A — Mood subfolders:
#     assets/music/dark/       → brooding, noir, suspenseful
#     assets/music/intense/    → aggressive, powerful, battle-ready
#     assets/music/reflective/ → thoughtful, stoic, contemplative
#     assets/music/powerful/   → triumphant, epic, commanding
#     assets/music/general/    → works for any mood
#
#   Option B — Mood tags in filename:
#     assets/music/track_name__dark.mp3
#     assets/music/epic_orchestral__intense.mp3
#     (double underscore before mood tag)
#
#   Option C — Flat folder (no mood info):
#     assets/music/any_track.mp3
#     → treated as "general", picked randomly
#
# HOW MOOD IS DETERMINED:
#   1. Count mood tags from all script segments
#   2. Pick the dominant mood
#   3. Select a track from that mood's pool
#   4. If no mood-specific tracks exist, use general/any pool
#   5. If no local tracks at all, fall back to Freesound API
# ============================================================

# --- Valid mood categories (must match script_generator output) ---
VALID_MOODS = {"dark", "intense", "reflective", "powerful"}

# --- Freesound search queries per mood ---
# Used only as last-resort fallback when no local tracks exist
FREESOUND_MOOD_QUERIES = {
    "dark": [
        "dark ambient cinematic suspense",
        "noir dramatic tension dark",
        "dark cinematic brooding orchestra",
    ],
    "intense": [
        "intense epic cinematic trailer",
        "powerful dramatic orchestral dark",
        "epic battle cinematic orchestra",
    ],
    "reflective": [
        "reflective cinematic piano dark",
        "contemplative orchestral ambient",
        "stoic calm cinematic dark piano",
    ],
    "powerful": [
        "powerful epic triumphant orchestra",
        "commanding cinematic dramatic buildup",
        "epic motivational orchestral dark",
    ],
}


def get_dominant_mood(script_segments):
    """
    # Counts mood tags across all segments and returns the most common one
    # Falls back to "intense" if no moods found (safest for dark motivation)
    """
    mood_counts = {m: 0 for m in VALID_MOODS}

    for seg in script_segments:
        mood = seg.get("mood", "").lower().strip()
        if mood in mood_counts:
            mood_counts[mood] += 1

    if not any(mood_counts.values()):
        return "intense"

    return max(mood_counts, key=mood_counts.get)


def scan_local_tracks(music_dir=None):
    """
    # Scans assets/music/ for tracks and organizes them by mood
    # Supports both subfolder and filename-tag organization
    #
    # Returns: dict of {mood: [file_path, ...]}
    """
    if music_dir is None:
        music_dir = config.MUSIC_DIR

    tracks_by_mood = {m: [] for m in VALID_MOODS}
    tracks_by_mood["general"] = []

    if not os.path.exists(music_dir):
        return tracks_by_mood

    audio_extensions = (".mp3", ".wav", ".m4a", ".ogg", ".flac")

    # --- Scan mood subfolders ---
    for mood in VALID_MOODS:
        mood_dir = os.path.join(music_dir, mood)
        if os.path.isdir(mood_dir):
            for f in os.listdir(mood_dir):
                if f.lower().endswith(audio_extensions):
                    path = os.path.join(mood_dir, f)
                    if os.path.getsize(path) > 50000:
                        tracks_by_mood[mood].append(path)

    # --- Scan general subfolder ---
    general_dir = os.path.join(music_dir, "general")
    if os.path.isdir(general_dir):
        for f in os.listdir(general_dir):
            if f.lower().endswith(audio_extensions):
                path = os.path.join(general_dir, f)
                if os.path.getsize(path) > 50000:
                    tracks_by_mood["general"].append(path)

    # --- Scan root music dir for tagged and untagged files ---
    for f in os.listdir(music_dir):
        full_path = os.path.join(music_dir, f)
        if not os.path.isfile(full_path):
            continue
        if not f.lower().endswith(audio_extensions):
            continue
        if os.path.getsize(full_path) < 50000:
            continue

        # --- Check for mood tag in filename (double underscore separator) ---
        name_lower = f.lower()
        tagged = False
        for mood in VALID_MOODS:
            if f"__{mood}" in name_lower:
                tracks_by_mood[mood].append(full_path)
                tagged = True
                break

        if not tagged:
            tracks_by_mood["general"].append(full_path)

    return tracks_by_mood


def select_music(script_segments, music_dir=None):
    """
    # Selects the best background music for a video based on script mood
    #
    # Priority:
    #   1. Local track matching the dominant mood
    #   2. Local track from "general" pool
    #   3. Freesound API download (mood-specific search)
    #
    # Returns: file path to the selected track, or None
    """
    if music_dir is None:
        music_dir = config.MUSIC_DIR

    # --- Determine the video's dominant mood ---
    dominant_mood = get_dominant_mood(script_segments)
    print(f"[MUSIC] Dominant mood: {dominant_mood}")

    # --- Scan local library ---
    tracks = scan_local_tracks(music_dir)

    total_local = sum(len(v) for v in tracks.values())
    print(f"[MUSIC] Local library: {total_local} tracks "
          f"(dark={len(tracks['dark'])}, intense={len(tracks['intense'])}, "
          f"reflective={len(tracks['reflective'])}, powerful={len(tracks['powerful'])}, "
          f"general={len(tracks['general'])})")

    # --- Priority 1: mood-matched track ---
    if tracks[dominant_mood]:
        selected = random.choice(tracks[dominant_mood])
        print(f"[MUSIC] Selected ({dominant_mood}): {os.path.basename(selected)}")
        return selected

    # --- Priority 2: general pool ---
    if tracks["general"]:
        selected = random.choice(tracks["general"])
        print(f"[MUSIC] No {dominant_mood} tracks, using general: {os.path.basename(selected)}")
        return selected

    # --- Priority 3: any local track from any mood ---
    all_tracks = [t for pool in tracks.values() for t in pool]
    if all_tracks:
        selected = random.choice(all_tracks)
        print(f"[MUSIC] Using available track: {os.path.basename(selected)}")
        return selected

    # --- Priority 4: Freesound fallback ---
    print(f"[MUSIC] No local tracks found, trying Freesound...")
    return _freesound_fallback(dominant_mood, music_dir)


def _freesound_fallback(mood, output_dir):
    """
    # Downloads a track from Freesound API matched to the mood
    # Only used when no local tracks are available
    """
    if not config.FREESOUND_API_KEY or config.FREESOUND_API_KEY == "your_freesound_api_key_here":
        print("[MUSIC] No Freesound API key set. Video will have voiceover only.")
        return None

    queries = FREESOUND_MOOD_QUERIES.get(mood, FREESOUND_MOOD_QUERIES["intense"])

    for query in queries:
        result = _freesound_search_download(query, output_dir)
        if result:
            return result

    print("[MUSIC] Freesound fallback failed — no suitable tracks found")
    return None


def _freesound_search_download(query, output_dir):
    """
    # Searches Freesound and downloads the best-rated match
    """
    url = "https://freesound.org/apiv2/search/text/"
    params = {
        "query": query,
        "token": config.FREESOUND_API_KEY,
        "filter": "duration:[60 TO 300]",
        "fields": "id,name,duration,previews,tags,avg_rating,num_downloads",
        "page_size": 15,
        "sort": "rating_desc",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return None

        data = response.json()
        results = data.get("results", [])
        if not results:
            return None

        track = random.choice(results[:5])
        track_name = track.get("name", "unknown")
        previews = track.get("previews", {})
        download_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")

        if not download_url:
            return None

        print(f"[MUSIC] Freesound: \"{track_name}\" ({track.get('duration', 0):.0f}s)")

        audio_response = requests.get(download_url, timeout=30)
        if audio_response.status_code != 200:
            return None

        os.makedirs(output_dir, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in track_name)
        safe_name = safe_name.strip()[:50] or "background_music"
        file_path = os.path.join(output_dir, f"{safe_name}.mp3")

        with open(file_path, "wb") as f:
            f.write(audio_response.content)

        if os.path.getsize(file_path) < 50000:
            os.remove(file_path)
            return None

        print(f"[MUSIC] Downloaded: {os.path.basename(file_path)}")
        return file_path

    except Exception as e:
        print(f"[MUSIC] Freesound error: {e}")
        return None


# --- Quick test ---
if __name__ == "__main__":
    # Test with sample segments
    test_segments = [
        {"text": "Silence is power.", "mood": "dark"},
        {"text": "The wolf walks alone.", "mood": "intense"},
        {"text": "Your strength is in stillness.", "mood": "reflective"},
        {"text": "Rise above them all.", "mood": "powerful"},
        {"text": "They will never understand.", "mood": "dark"},
    ]

    print("=== Music Selector Test ===")
    result = select_music(test_segments)
    if result:
        print(f"\nSelected: {result}")
    else:
        print("\nNo music found")
