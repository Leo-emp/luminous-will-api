import os
import requests
import random
import config

# ============================================================
# MUSIC DOWNLOADER
# Downloads dramatic/motivational background music from Freesound
# Freesound has a proper API that supports audio search + download
# Tracks are Creative Commons licensed - free to use
#
# Searches for dark cinematic, dramatic, epic, motivational
# tracks that match the Luminous Will brand aesthetic
# ============================================================

# --- Search queries to find on-brand background music ---
# These are tried in order until a suitable track is found
# --- Prioritize intense, powerful, dramatic tracks ---
MUSIC_SEARCH_QUERIES = [
    "intense epic cinematic trailer",
    "powerful dramatic orchestral dark",
    "epic battle cinematic orchestra",
    "dark intense motivational cinematic",
    "dramatic powerful trailer music",
    "epic cinematic war orchestral",
    "intense dark orchestral dramatic",
    "powerful epic motivational orchestra",
]


def download_background_music(output_dir=None):
    """
    # Searches Freesound for a dramatic/motivational background track
    # Downloads it to the assets/music/ folder
    #
    # Returns: path to the downloaded .mp3 file, or None
    """

    # --- Use the assets/music folder by default ---
    if output_dir is None:
        output_dir = config.MUSIC_DIR
    os.makedirs(output_dir, exist_ok=True)

    # --- Check if we already have music downloaded ---
    existing = find_existing_music(output_dir)
    if existing:
        print(f"[MUSIC] Using existing track: {os.path.basename(existing)}")
        return existing

    # --- Check for Freesound API key ---
    if not config.FREESOUND_API_KEY or config.FREESOUND_API_KEY == "your_freesound_api_key_here":
        print("[MUSIC] WARNING: No Freesound API key set. Skipping music download.")
        print("[MUSIC] Add FREESOUND_API_KEY to your .env file for auto music")
        return None

    print("[MUSIC] Searching Freesound for dramatic background music...")

    # --- Try each search query until we find a good track ---
    for query in MUSIC_SEARCH_QUERIES:
        result = search_and_download(query, output_dir)
        if result:
            return result

    print("[MUSIC] Could not find suitable music from Freesound")
    return None


def search_and_download(query, output_dir):
    """
    # Searches Freesound API and downloads a matching track
    #
    # Freesound API search endpoint:
    #   https://freesound.org/apiv2/search/text/
    #
    # We use the preview-hq-mp3 field to download the track
    # (previews don't require OAuth, just the API token)
    #
    # Returns: file path of downloaded track, or None
    """

    # --- Search for tracks ---
    url = "https://freesound.org/apiv2/search/text/"
    params = {
        "query": query,
        "token": config.FREESOUND_API_KEY,
        # Only return tracks longer than 60 seconds (good for background music)
        "filter": "duration:[60 TO 300]",
        # Request the preview URLs and metadata we need
        "fields": "id,name,duration,previews,tags,avg_rating,num_downloads",
        "page_size": 15,
        "sort": "rating_desc",
    }

    try:
        response = requests.get(url, params=params, timeout=15)

        if response.status_code != 200:
            print(f"[MUSIC] Freesound API error: {response.status_code}")
            if response.status_code == 401:
                print("[MUSIC] Invalid API key - check your FREESOUND_API_KEY in .env")
            return None

        data = response.json()
        results = data.get("results", [])

        if not results:
            print(f"[MUSIC] No results for: {query}")
            return None

        # --- Pick a good track from the top results ---
        # Prefer tracks with higher ratings and more downloads
        track = random.choice(results[:5])

        track_name = track.get("name", "unknown")
        duration = track.get("duration", 0)
        previews = track.get("previews", {})

        # --- Get the high quality preview URL ---
        # "preview-hq-mp3" is the best quality preview (~128kbps mp3)
        # This doesn't require OAuth authentication
        download_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")

        if not download_url:
            print(f"[MUSIC] No preview URL for: {track_name}")
            return None

        print(f"[MUSIC] Found: \"{track_name}\" ({duration:.0f}s)")
        print(f"[MUSIC] Downloading...")

        # --- Download the track ---
        audio_response = requests.get(download_url, timeout=30)
        if audio_response.status_code != 200:
            print(f"[MUSIC] Download failed: {audio_response.status_code}")
            return None

        # --- Save to music folder ---
        # Clean up the filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in track_name)
        safe_name = safe_name.strip()[:50] or "background_music"
        file_path = os.path.join(output_dir, f"{safe_name}.mp3")

        with open(file_path, "wb") as f:
            f.write(audio_response.content)

        # --- Verify the file is a real audio file ---
        file_size = os.path.getsize(file_path)
        if file_size < 50000:  # less than 50KB is probably an error
            print(f"[MUSIC] File too small ({file_size} bytes), removing")
            os.remove(file_path)
            return None

        print(f"[MUSIC] Saved: {os.path.basename(file_path)} ({file_size/1024:.0f} KB)")
        return file_path

    except Exception as e:
        print(f"[MUSIC] Error: {e}")
        return None


def find_existing_music(music_dir):
    """
    # Checks if there's already a music file in the folder
    # Returns the path to the first .mp3/.wav found, or None
    """
    if not os.path.exists(music_dir):
        return None

    for f in os.listdir(music_dir):
        if f.endswith((".mp3", ".wav", ".m4a")):
            path = os.path.join(music_dir, f)
            # Make sure it's a real file, not empty
            if os.path.getsize(path) > 50000:
                return path

    return None


# --- Quick test ---
if __name__ == "__main__":
    print("Testing Freesound music download...")
    result = download_background_music()
    if result:
        print(f"\nSuccess: {result}")
    else:
        print("\nFailed - check your FREESOUND_API_KEY in .env")
