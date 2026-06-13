import os
import requests
import time
import random
import re
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

# --- Words to ignore when scoring relevance (too common to be meaningful) ---
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "because", "as", "until", "while", "of",
    "at", "by", "for", "with", "about", "against", "between", "through",
    "during", "before", "after", "above", "below", "to", "from", "up",
    "down", "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "i", "me", "my", "myself", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "it", "its", "they", "them", "their",
}

# --- Brand-relevant words that get bonus scoring weight ---
BRAND_BONUS_WORDS = {
    "dark", "cinematic", "dramatic", "moody", "noir", "shadow", "silhouette",
    "night", "storm", "rain", "lightning", "fire", "smoke", "fog", "mist",
    "wolf", "lion", "eagle", "predator", "warrior", "fighter", "chess",
    "city", "skyline", "skyscraper", "highway", "bridge", "tunnel",
    "ocean", "mountain", "desert", "forest", "cliff", "peak",
    "gym", "boxing", "training", "athlete", "running", "strength",
    "suit", "businessman", "luxury", "power", "solitary", "alone",
}


def _extract_content_words(text):
    """
    # Extracts meaningful words from text for relevance scoring
    # Strips punctuation, lowercases, removes stop words
    # Returns a set of content words
    """
    words = re.findall(r'[a-z]+', text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def _score_video_relevance(video_meta, script_text, keywords, source="pexels"):
    """
    # Scores how well a stock video matches the script segment
    # Higher score = better match
    #
    # Scoring factors:
    #   - Keyword overlap with video tags/URL (primary signal)
    #   - Script text word overlap with video metadata (semantic signal)
    #   - Brand bonus for dark/cinematic content
    #   - Penalty for avoid-keyword matches
    #
    # Args:
    #   video_meta: Pexels or Pixabay video result dict
    #   script_text: the spoken sentence for this segment
    #   keywords: the visual_keywords string for this segment
    #   source: "pexels" or "pixabay" (different metadata structures)
    #
    # Returns: float score (0.0 to ~10.0)
    """
    score = 0.0

    # --- Extract searchable text from video metadata ---
    if source == "pexels":
        # Pexels: video URL contains descriptive slugs
        video_text = str(video_meta.get("url", "")).lower()
        video_text += " " + str(video_meta.get("image", "")).lower()
        # Pexels user info sometimes has relevant tags
        user_name = str(video_meta.get("user", {}).get("name", "")).lower()
        video_text += " " + user_name
    else:
        # Pixabay: has explicit tags field
        video_text = str(video_meta.get("tags", "")).lower()
        video_text += " " + str(video_meta.get("pageURL", "")).lower()

    # --- Clean the video text into a set of words ---
    video_words = set(re.findall(r'[a-z]+', video_text))

    # --- Score 1: Keyword overlap (strongest signal, up to 5 points) ---
    keyword_words = _extract_content_words(keywords)
    keyword_matches = keyword_words & video_words
    if keyword_words:
        score += (len(keyword_matches) / len(keyword_words)) * 5.0

    # --- Score 2: Script text overlap (semantic signal, up to 3 points) ---
    script_words = _extract_content_words(script_text)
    script_matches = script_words & video_words
    if script_words:
        score += (len(script_matches) / len(script_words)) * 3.0

    # --- Score 3: Brand bonus (up to 2 points) ---
    brand_matches = BRAND_BONUS_WORDS & video_words
    score += min(len(brand_matches) * 0.4, 2.0)

    # --- Penalty: avoid keywords reduce score ---
    for bad in AVOID_KEYWORDS:
        if bad in video_text:
            score -= 1.0

    return max(score, 0.0)


def _search_pexels_candidates(query, used_ids, orientation=None):
    """
    # Searches Pexels and returns candidate videos (without downloading)
    # Returns list of (video_meta, video_file) tuples
    """
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": config.PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": orientation or config.PEXELS_ORIENTATION,
        "size": config.PEXELS_SIZE,
        "per_page": config.PEXELS_PER_PAGE,
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        videos = data.get("videos", [])
        if not videos:
            return []

        # --- Filter out used and unwanted videos ---
        available = _filter_videos(videos, used_ids)
        if not available:
            available = [v for v in videos if v["id"] not in used_ids] or videos

        return available

    except Exception as e:
        print(f"[VISUALS] Pexels candidates error: {e}")
        return []


def _search_pixabay_candidates(query, used_ids):
    """
    # Searches Pixabay and returns candidate videos (without downloading)
    # Returns list of video_meta dicts
    """
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": config.PIXABAY_API_KEY,
        "q": query,
        "video_type": "film",
        "per_page": 10,
        "safesearch": "true",
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        hits = data.get("hits", [])
        if not hits:
            return []

        # --- Filter out used and unwanted videos ---
        available = []
        for v in hits:
            vid_id = v.get("id", 0)
            if vid_id in used_ids:
                continue
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
            available = [v for v in hits if v.get("id", 0) not in used_ids] or hits

        return available

    except Exception as e:
        print(f"[VISUALS] Pixabay candidates error: {e}")
        return []


def _download_pexels_video(video_meta, output_dir, index):
    """
    # Downloads a specific Pexels video by its metadata
    # Returns file path or None
    """
    video_file = _get_best_pexels_file(video_meta)
    if not video_file:
        return None

    download_url = video_file["link"]
    file_path = os.path.join(output_dir, f"clip_{index:03d}.mp4")

    print(f"[VISUALS] Pexels downloading: {video_file.get('quality', '?')} "
          f"({video_file.get('width', '?')}x{video_file.get('height', '?')})")

    try:
        video_response = requests.get(download_url, stream=True)
        with open(file_path, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)
        return file_path
    except Exception as e:
        print(f"[VISUALS] Download error: {e}")
        return None


def _download_pixabay_video(video_meta, output_dir, index):
    """
    # Downloads a specific Pixabay video by its metadata
    # Returns file path or None
    """
    download_url, width, height = _get_best_pixabay_file(video_meta)
    if not download_url:
        return None

    file_path = os.path.join(output_dir, f"clip_{index:03d}.mp4")

    print(f"[VISUALS] Pixabay downloading: {width}x{height}")

    try:
        video_response = requests.get(download_url, stream=True)
        with open(file_path, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)
        return file_path
    except Exception as e:
        print(f"[VISUALS] Download error: {e}")
        return None


def search_and_download_videos(script_segments, output_dir, profile=None):
    """
    # For each script segment, searches Pexels + Pixabay with SEMANTIC MATCHING
    # Uses multi-query search (primary + alt keywords) and relevance scoring
    # to pick the best-matching footage instead of random selection
    #
    # Flow per segment:
    #   1. Build query list: primary keywords + alt keywords + simplified fallback
    #   2. Search both Pexels and Pixabay with each query
    #   3. Score ALL candidates against the script text for relevance
    #   4. Download the highest-scoring result
    #
    # Args:
    #   script_segments: list of script dicts with 'visual_keywords' and optional 'visual_keywords_alt'
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

    # --- Context-aware fallback queries (used when all else fails) ---
    if orientation == "landscape":
        generic_fallbacks = [
            "dark cityscape night skyline", "mountain peak dark clouds dramatic",
            "ocean waves dark cinematic", "dark highway driving night",
            "storm clouds dramatic sky", "dark forest aerial cinematic",
            "modern architecture night dark", "dark desert landscape cinematic",
            "river dark moody cinematic", "dark stadium empty cinematic",
            "dark bridge night lights", "rain dark street cinematic",
        ]
    else:
        generic_fallbacks = [
            "businessman suit dark", "luxury car night", "man walking alone city night",
            "dark gym workout", "boxing training dark", "running athlete dark",
            "modern skyscraper night", "dark cinematic portrait", "chess dark dramatic",
            "wolf dark forest", "dark ocean waves", "man rooftop city night",
        ]

    for i, segment in enumerate(script_segments):
        keywords = segment["visual_keywords"]
        script_text = segment.get("text", "")
        alt_keywords = segment.get("visual_keywords_alt", [])

        print(f"[VISUALS] ({i+1}/{len(script_segments)}) Searching: {keywords}")

        # --- Build the query list: primary + alts + simplified ---
        queries = [keywords]
        for alt in alt_keywords[:3]:
            if alt and alt != keywords:
                queries.append(alt)
        # --- Add a simplified 2-word version as last resort ---
        simple_words = keywords.split()[:2]
        simple_query = " ".join(simple_words)
        if simple_query != keywords:
            queries.append(simple_query)

        # --- Collect all candidates from all queries, both sources ---
        # Each candidate: (score, video_meta, source_str)
        all_candidates = []

        for q_idx, query in enumerate(queries):
            # --- Search Pexels ---
            if has_pexels:
                pexels_results = _search_pexels_candidates(query, used_pexels_ids, orientation)
                for video_meta in pexels_results[:5]:
                    score = _score_video_relevance(video_meta, script_text, keywords, source="pexels")
                    all_candidates.append((score, video_meta, "pexels"))

            # --- Search Pixabay ---
            if has_pixabay:
                pixabay_results = _search_pixabay_candidates(query, used_pixabay_ids)
                for video_meta in pixabay_results[:5]:
                    score = _score_video_relevance(video_meta, script_text, keywords, source="pixabay")
                    all_candidates.append((score, video_meta, "pixabay"))

            # --- Rate limit between queries ---
            if q_idx < len(queries) - 1:
                time.sleep(0.5)

        # --- Sort candidates by relevance score (highest first) ---
        all_candidates.sort(key=lambda x: x[0], reverse=True)

        video_path = None

        if all_candidates:
            best_score = all_candidates[0][0]
            print(f"[VISUALS] Found {len(all_candidates)} candidates, best score: {best_score:.1f}")

            # --- Try downloading the highest-scored candidates ---
            for score, video_meta, source in all_candidates[:5]:
                if source == "pexels":
                    used_pexels_ids.add(video_meta["id"])
                    video_path = _download_pexels_video(video_meta, output_dir, i)
                else:
                    used_pixabay_ids.add(video_meta["id"])
                    video_path = _download_pixabay_video(video_meta, output_dir, i)

                if video_path:
                    print(f"[VISUALS] Selected ({source}, score={score:.1f}): {os.path.basename(video_path)}")
                    break

        # --- Last resort: cycle through generic brand-safe fallbacks ---
        if not video_path:
            print(f"[VISUALS] All queries missed, trying brand fallbacks...")
            for fallback in generic_fallbacks:
                if has_pexels:
                    candidates = _search_pexels_candidates(fallback, used_pexels_ids, orientation)
                    if candidates:
                        video_meta = candidates[0]
                        used_pexels_ids.add(video_meta["id"])
                        video_path = _download_pexels_video(video_meta, output_dir, i)
                if not video_path and has_pixabay:
                    candidates = _search_pixabay_candidates(fallback, used_pixabay_ids)
                    if candidates:
                        video_meta = candidates[0]
                        used_pixabay_ids.add(video_meta["id"])
                        video_path = _download_pixabay_video(video_meta, output_dir, i)
                if video_path:
                    break

        if video_path:
            downloaded_clips.append(video_path)
        else:
            print(f"[VISUALS] WARNING: No clip found for segment {i+1}")

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
