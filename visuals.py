import os
import requests
import time
import random
import config

# ============================================================
# VISUAL SOURCER
# Downloads free vertical stock footage from Pexels + Pixabay APIs
# Filters for dark, cinematic, high-quality clips
#
# BRAND RULES (from analyzing real Luminous Will videos):
#   - Always prefer portrait/vertical (9:16) footage
#   - Dark, moody, cinematic tone ONLY
#   - Preferred subjects: lions, chess, suited men, dark cityscapes,
#     solitary figures, rain, shadows, wolves, gym, boxing, running,
#     modern city architecture
#   - NEVER use bright, colorful, happy, sunny footage
#   - Each clip should be unique (no reuse within same video)
#   - Prefer HD (1920x1080) or higher resolution
#
# SOURCES:
#   1. Pexels API (primary) - great dark/cinematic footage
#   2. Pixabay API (secondary) - additional variety + fallback
#   Alternates between sources for each clip to maximize variety
# ============================================================

# --- Keywords to AVOID in search results ---
# These don't match the dark premium sigma aesthetic
AVOID_KEYWORDS = [
    "bright", "colorful", "happy", "sunny", "beach",
    "party", "celebration", "cartoon", "comedy", "funny",
    "cub", "cubs", "baby", "kitten", "puppy", "cute",
    "kid", "kids", "child", "children", "boy", "girl",
    "toddler", "infant", "family", "playground",
    "face", "portrait", "closeup", "close-up", "headshot",
]


def search_and_download_videos(script_segments, output_dir, profile=None):
    """
    # For each script segment, searches Pexels + Pixabay for matching footage
    # Alternates between sources for variety, uses the other as fallback
    # Downloads the best vertical (9:16) or landscape (16:9) clip per segment
    #
    # Args:
    #   script_segments: list of script dicts with 'visual_keywords'
    #   output_dir: directory to save downloaded clips
    #   profile: optional format profile dict (contains pexels_orientation, etc.)
    #
    # Returns:
    #   list of file paths to downloaded video clips
    """

    os.makedirs(output_dir, exist_ok=True)
    downloaded_clips = []
    # --- Track used video IDs per source so we don't reuse clips ---
    used_pexels_ids = set()
    used_pixabay_ids = set()

    # --- Check which APIs are available ---
    has_pexels = bool(config.PEXELS_API_KEY)
    has_pixabay = bool(config.PIXABAY_API_KEY)

    if not has_pexels and not has_pixabay:
        print("[VISUALS] ERROR: No API keys configured for Pexels or Pixabay!")
        return []

    # Format-specific search orientation
    orientation = profile["pexels_orientation"] if profile else config.PEXELS_ORIENTATION

    # Expanded fallback queries for landscape
    if orientation == "landscape":
        landscape_fallbacks = [
            "dark cityscape night skyline", "mountain peak dark clouds dramatic",
            "ocean waves dark cinematic", "dark highway driving night",
            "storm clouds dramatic sky", "dark forest aerial cinematic",
            "modern architecture night dark", "dark desert landscape cinematic",
            "river dark moody cinematic", "dark stadium empty cinematic",
            "dark bridge night lights", "rain dark street cinematic",
        ]
    else:
        landscape_fallbacks = None

    for i, segment in enumerate(script_segments):
        keywords = segment["visual_keywords"]
        print(f"[VISUALS] ({i+1}/{len(script_segments)}) Searching: {keywords}")

        video_path = None

        # --- Alternate primary source: even=Pexels, odd=Pixabay ---
        # This gives maximum variety across both stock libraries
        if i % 2 == 0 and has_pexels:
            # --- Try Pexels first, then Pixabay fallback ---
            video_path = search_pexels_one(keywords, output_dir, i, used_pexels_ids, orientation)
            if not video_path and has_pixabay:
                print(f"[VISUALS] Pexels miss, trying Pixabay...")
                video_path = search_pixabay_one(keywords, output_dir, i, used_pixabay_ids)
        elif has_pixabay:
            # --- Try Pixabay first, then Pexels fallback ---
            video_path = search_pixabay_one(keywords, output_dir, i, used_pixabay_ids)
            if not video_path and has_pexels:
                print(f"[VISUALS] Pixabay miss, trying Pexels...")
                video_path = search_pexels_one(keywords, output_dir, i, used_pexels_ids, orientation)
        elif has_pexels:
            # --- Only Pexels available ---
            video_path = search_pexels_one(keywords, output_dir, i, used_pexels_ids, orientation)

        # --- Fallback: try simpler keywords on both sources ---
        if not video_path:
            simple_keywords = keywords.split()[:2]
            fallback_query = " ".join(simple_keywords)
            print(f"[VISUALS] Trying simpler query: {fallback_query}")
            if has_pexels:
                video_path = search_pexels_one(fallback_query, output_dir, i, used_pexels_ids, orientation)
            if not video_path and has_pixabay:
                video_path = search_pixabay_one(fallback_query, output_dir, i, used_pixabay_ids)

        # --- Last resort: format-specific fallback queries ---
        if not video_path:
            fallbacks = landscape_fallbacks if landscape_fallbacks else [
                "businessman suit dark", "luxury car night", "man walking alone city night",
                "dark gym workout", "boxing training dark", "running athlete dark",
                "modern skyscraper night", "dark cinematic portrait", "chess dark dramatic",
                "wolf dark forest", "dark ocean waves", "man rooftop city night",
            ]
            for fallback in fallbacks:
                if has_pexels:
                    video_path = search_pexels_one(fallback, output_dir, i, used_pexels_ids, orientation)
                if not video_path and has_pixabay:
                    video_path = search_pixabay_one(fallback, output_dir, i, used_pixabay_ids)
                if video_path:
                    break

        if video_path:
            downloaded_clips.append(video_path)
            print(f"[VISUALS] Downloaded: {os.path.basename(video_path)}")

        # --- Respect API rate limits ---
        time.sleep(1)

    print(f"[VISUALS] Downloaded {len(downloaded_clips)} clips total")
    return downloaded_clips


# ============================================================
# PEXELS SEARCH + DOWNLOAD
# ============================================================

def search_pexels_one(query, output_dir, index, used_ids, orientation=None):
    """
    # Searches Pexels and downloads one matching video clip
    # Orientation is format-aware: portrait (9:16) or landscape (16:9)
    #
    # Args:
    #   orientation: "portrait" or "landscape" (falls back to config default)
    #
    # Returns: file path of downloaded clip, or None
    """

    # --- Search the Pexels API ---
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": config.PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": orientation or config.PEXELS_ORIENTATION,  # format-aware
        "size": config.PEXELS_SIZE,                               # large/high quality
        "per_page": config.PEXELS_PER_PAGE,
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print(f"[VISUALS] Pexels API error: {response.status_code}")
            return None

        data = response.json()
        videos = data.get("videos", [])

        if not videos:
            print(f"[VISUALS] Pexels: no results for '{query}'")
            return None

        # --- Filter out already-used videos and unwanted content ---
        available = _filter_videos(videos, used_ids)
        if not available:
            available = [v for v in videos if v["id"] not in used_ids] or videos

        # --- Pick a random one from top results for variety ---
        video = random.choice(available[:5])
        used_ids.add(video["id"])

        # --- Find the best quality video file ---
        # Prefer HD (1920x1080) or higher portrait files
        video_file = _get_best_pexels_file(video)

        if not video_file:
            print(f"[VISUALS] Pexels: no suitable file found")
            return None

        # --- Download the video ---
        download_url = video_file["link"]
        file_path = os.path.join(output_dir, f"clip_{index:03d}.mp4")

        print(f"[VISUALS] Pexels downloading: {video_file.get('quality', '?')} "
              f"({video_file.get('width', '?')}x{video_file.get('height', '?')})")

        video_response = requests.get(download_url, stream=True)
        with open(file_path, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)

        return file_path

    except Exception as e:
        print(f"[VISUALS] Pexels error: {e}")
        return None


# ============================================================
# PIXABAY SEARCH + DOWNLOAD
# ============================================================

def search_pixabay_one(query, output_dir, index, used_ids):
    """
    # Searches Pixabay and downloads one matching video clip
    # Pixabay API: https://pixabay.com/api/videos/
    # Free tier: 100 requests/minute
    #
    # Returns: file path of downloaded clip, or None
    """

    # --- Search the Pixabay Video API ---
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": config.PIXABAY_API_KEY,
        "q": query,
        "video_type": "film",       # real footage only, no animations
        "per_page": 10,              # max results per query
        "safesearch": "true",        # family-safe content
    }

    try:
        response = requests.get(url, params=params)

        if response.status_code != 200:
            print(f"[VISUALS] Pixabay API error: {response.status_code}")
            return None

        data = response.json()
        hits = data.get("hits", [])

        if not hits:
            print(f"[VISUALS] Pixabay: no results for '{query}'")
            return None

        # --- Filter out already-used videos and unwanted content ---
        available = []
        for v in hits:
            vid_id = v.get("id", 0)
            if vid_id in used_ids:
                continue
            # --- Check tags against avoid keywords ---
            tags = str(v.get("tags", "")).lower()
            page_url = str(v.get("pageURL", "")).lower()
            skip = False
            for bad in AVOID_KEYWORDS:
                if bad in tags or bad in page_url:
                    skip = True
                    break
            if not skip:
                available.append(v)

        if not available:
            # --- Relax filter: just skip used IDs ---
            available = [v for v in hits if v.get("id", 0) not in used_ids] or hits

        # --- Pick a random one from top results for variety ---
        video = random.choice(available[:5])
        used_ids.add(video["id"])

        # --- Get the best quality video URL from Pixabay response ---
        # Pixabay returns: large (1920), medium (1280), small (960), tiny (640)
        download_url, width, height = _get_best_pixabay_file(video)

        if not download_url:
            print(f"[VISUALS] Pixabay: no suitable file found")
            return None

        file_path = os.path.join(output_dir, f"clip_{index:03d}.mp4")

        print(f"[VISUALS] Pixabay downloading: {width}x{height}")

        video_response = requests.get(download_url, stream=True)
        with open(file_path, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)

        return file_path

    except Exception as e:
        print(f"[VISUALS] Pixabay error: {e}")
        return None


# ============================================================
# SHARED HELPERS
# ============================================================

def _filter_videos(videos, used_ids):
    """
    # Filters Pexels video results: removes used IDs and unwanted content
    # Checks video URL and thumbnail URL against AVOID_KEYWORDS
    """
    available = []
    for v in videos:
        if v["id"] in used_ids:
            continue
        # --- Reject clips with avoid keywords in URL or metadata ---
        video_url = str(v.get("url", "")).lower()
        video_image = str(v.get("image", "")).lower()
        skip = False
        for bad in AVOID_KEYWORDS:
            if bad in video_url or bad in video_image:
                skip = True
                break
        if not skip:
            available.append(v)
    return available


def _get_best_pexels_file(video_data):
    """
    # Picks the best quality video file from Pexels response
    # Prefers: portrait orientation, HD or higher, mp4 format
    """

    video_files = video_data.get("video_files", [])

    if not video_files:
        return None

    # --- Sort by quality: prefer HD portrait files ---
    portrait_files = []
    landscape_files = []

    for vf in video_files:
        w = vf.get("width", 0)
        h = vf.get("height", 0)
        # --- Portrait = height > width ---
        if h > w:
            portrait_files.append(vf)
        else:
            landscape_files.append(vf)

    # --- Prefer portrait, fall back to landscape ---
    candidates = portrait_files if portrait_files else landscape_files

    # --- Sort by resolution (higher is better) ---
    candidates.sort(key=lambda x: x.get("height", 0) * x.get("width", 0), reverse=True)

    # --- Return best quality (but not unnecessarily huge) ---
    for vf in candidates:
        h = vf.get("height", 0)
        # Prefer 1920 height or close to it
        if 720 <= h <= 3840:
            return vf

    # --- Fallback: just return the first one ---
    return candidates[0] if candidates else video_files[0]


def _get_best_pixabay_file(video_data):
    """
    # Picks the best quality video file from Pixabay response
    # Pixabay structure: video_data["videos"] = {"large": {...}, "medium": {...}, ...}
    # Each size has: url, width, height
    # Prefers large (1920px) > medium (1280px) > small (960px)
    #
    # Returns: (download_url, width, height) or (None, 0, 0)
    """

    videos = video_data.get("videos", {})

    if not videos:
        return None, 0, 0

    # --- Try sizes from best to worst ---
    # "large" is typically 1920px wide, great quality
    for size_key in ["large", "medium", "small"]:
        vf = videos.get(size_key, {})
        url = vf.get("url", "")
        width = vf.get("width", 0)
        height = vf.get("height", 0)
        if url and width > 0:
            return url, width, height

    # --- Fallback: tiny ---
    tiny = videos.get("tiny", {})
    if tiny.get("url"):
        return tiny["url"], tiny.get("width", 0), tiny.get("height", 0)

    return None, 0, 0


# --- Quick test ---
if __name__ == "__main__":
    test_segments = [
        {"visual_keywords": "lion dark dramatic portrait"},
        {"visual_keywords": "man walking alone night city"},
        {"visual_keywords": "dark gym workout training"},
    ]
    clips = search_and_download_videos(test_segments, config.TEMP_DIR)
    print(f"\nDownloaded {len(clips)} test clips")
