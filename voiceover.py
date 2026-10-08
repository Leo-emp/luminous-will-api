import os
import json
import time
import requests
import config

# ============================================================
# VOICEOVER GENERATOR
# Uses ElevenLabs API to generate speech with word timestamps
# Voice: Adam (deep English story voice)
#
# RETRY LOGIC (added for operational resilience):
# ElevenLabs calls are the single most expensive step in the pipeline.
# A transient network blip or a 429 rate-limit response would kill the
# entire video generation without retry logic. We retry up to 3 times
# with exponential backoff (2s -> 4s -> 8s) on:
#   - Network errors (ConnectionError, Timeout) — transient by nature
#   - 429 Too Many Requests — rate limit, wait and retry
#   - 500/502/503/504 — server-side hiccups that usually self-heal
# We do NOT retry on 400/401/403 — those are client errors (bad key,
# bad request) that won't fix themselves no matter how long we wait.
# ============================================================

# --- Retry configuration ---
# MAX_RETRIES: how many times to retry after the first failure (3 retries = 4 total attempts)
MAX_RETRIES = 3
# RETRY_BASE_DELAY: starting delay in seconds, doubles each retry (2s, 4s, 8s)
RETRY_BASE_DELAY = 2
# REQUEST_TIMEOUT: seconds before we give up waiting for ElevenLabs to respond
# 30s is generous — typical response is 5-15s, but large scripts can take longer
REQUEST_TIMEOUT = 30
# RETRYABLE_STATUS_CODES: HTTP status codes that are worth retrying
# 429 = rate limited, 500/502/503/504 = server errors (transient)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _generate_edge_tts(text, output_path):
    """
    # Free fallback TTS using Microsoft Edge's engine
    # No API key needed, decent quality, generates word timestamps
    # Voice: en-US-GuyNeural (deep male, closest to ElevenLabs Adam)
    """
    import asyncio
    import edge_tts

    voice = "en-US-GuyNeural"
    communicate = edge_tts.Communicate(text, voice, rate="-10%")

    word_timestamps = []
    audio_chunks = []

    async def _run():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_sec = chunk["offset"] / 10_000_000
                duration_sec = chunk["duration"] / 10_000_000
                word_timestamps.append({
                    "word": chunk["text"],
                    "start": start_sec,
                    "end": start_sec + duration_sec,
                })

    asyncio.run(_run())

    with open(output_path, "wb") as f:
        for chunk in audio_chunks:
            f.write(chunk)

    print(f"[VOICEOVER] Edge TTS: generated {len(word_timestamps)} words")
    return word_timestamps


def generate_voiceover(script_text, output_path, profile=None):
    """
    # Generates voiceover using ElevenLabs (primary) or Edge TTS (fallback)
    # Caches voiceover: if output file already exists from a previous run, reuses it
    #
    # Args:
    #   script_text: full script as a single string
    #   output_path: where to save the .mp3 file
    #   profile: optional dict with format-specific voice settings (e.g. voice_stability)
    #
    # Returns:
    #   list of dicts with keys: word, start, end (times in seconds)
    """

    # --- CACHE CHECK: reuse voiceover from a previous failed run ---
    timestamps_path = output_path.replace(".mp3", "_timestamps.json")
    trimmed_path = output_path.replace(".mp3", "_trimmed.mp3")

    for cached_audio in [trimmed_path, output_path]:
        if os.path.exists(cached_audio) and os.path.exists(timestamps_path):
            try:
                with open(timestamps_path, "r") as f:
                    cached_words = json.load(f)
                if cached_words and len(cached_words) > 5:
                    print(f"[VOICEOVER] CACHED — reusing {os.path.basename(cached_audio)} ({len(cached_words)} words)")
                    return cached_words
            except Exception:
                pass

    print("[VOICEOVER] Generating speech with ElevenLabs...")

    # --- Build the API request ---
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}/with-timestamps"

    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    voice_settings = dict(config.VOICE_SETTINGS)
    if profile and "voice_stability" in profile:
        voice_settings["stability"] = profile["voice_stability"]

    payload = {
        "text": script_text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": voice_settings,
        "speed": config.VOICE_SPEED,
    }

    response = _call_elevenlabs_with_retry(url, headers, payload)

    if response.status_code != 200:
        print(f"[VOICEOVER] ERROR: ElevenLabs API returned {response.status_code}")
        print(f"[VOICEOVER] Response: {response.text}")
        # --- FALLBACK: use free Edge TTS instead of crashing ---
        print("[VOICEOVER] Falling back to Edge TTS (free, no credits needed)...")
        word_timestamps = _generate_edge_tts(script_text, output_path)
        ts_path = output_path.replace(".mp3", "_timestamps.json")
        with open(ts_path, "w") as f:
            json.dump(word_timestamps, f, indent=2)
        print(f"[VOICEOVER] Audio saved: {output_path}")
        return word_timestamps

    # --- Parse the response ---
    # The response contains base64 audio and alignment data
    result = response.json()

    # --- Save the audio file ---
    import base64
    audio_bytes = base64.b64decode(result["audio_base64"])

    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    print(f"[VOICEOVER] Audio saved to: {output_path}")

    # --- Extract word timestamps ---
    # ElevenLabs returns character-level alignment
    # We need to convert to word-level timestamps
    word_timestamps = extract_word_timestamps(result.get("alignment", {}))

    # --- Save timestamps to JSON for reference ---
    timestamps_path = output_path.replace(".mp3", "_timestamps.json")
    with open(timestamps_path, "w") as f:
        json.dump(word_timestamps, f, indent=2)

    print(f"[VOICEOVER] Found {len(word_timestamps)} words with timestamps")

    return word_timestamps


def _call_elevenlabs_with_retry(url, headers, payload):
    """
    # Makes the ElevenLabs API call with retry logic for resilience.
    #
    # WHY: ElevenLabs is an external API — network hiccups, rate limits (429),
    # and server errors (500-504) are all common in production. Without retries,
    # a single transient failure kills the entire video generation pipeline.
    #
    # HOW: Exponential backoff — each retry waits twice as long as the last:
    #   Attempt 1: immediate
    #   Attempt 2: wait 2 seconds
    #   Attempt 3: wait 4 seconds
    #   Attempt 4: wait 8 seconds
    # This pattern is industry standard because:
    #   - It gives the server time to recover
    #   - It avoids hammering a rate-limited endpoint
    #   - The exponential growth prevents long waits on quick recoveries
    #
    # WHAT WE DON'T RETRY:
    #   - 400 Bad Request — our payload is wrong, retrying won't help
    #   - 401 Unauthorized — bad API key, retrying won't help
    #   - 403 Forbidden — access denied, retrying won't help
    #
    # Returns:
    #   The requests.Response object (caller checks status_code)
    #
    # Raises:
    #   Exception if all retries exhausted on network errors (no response at all)
    """

    last_exception = None  # Track the last error so we can re-raise it if all retries fail

    # total_attempts = 1 (initial) + MAX_RETRIES (retries) = 4 attempts total
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            # --- Make the actual HTTP request ---
            # timeout=REQUEST_TIMEOUT (30s) prevents hanging forever if ElevenLabs
            # stops responding. Without this, requests.post() waits indefinitely.
            response = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )

            # --- Check if we got a successful response ---
            if response.status_code == 200:
                # Success! Return immediately, no need to retry
                if attempt > 1:
                    # Log that we recovered after retrying (useful for debugging)
                    print(f"[VOICEOVER] Succeeded on attempt {attempt} after {attempt - 1} retries")
                return response

            # --- Check if this error is worth retrying ---
            if response.status_code in RETRYABLE_STATUS_CODES:
                # This is a transient error (rate limit or server issue) — retry it
                if attempt <= MAX_RETRIES:
                    # Calculate exponential backoff delay: 2^(attempt-1) * base_delay
                    # attempt 1 -> 2s, attempt 2 -> 4s, attempt 3 -> 8s
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    print(
                        f"[VOICEOVER] Attempt {attempt}/{MAX_RETRIES + 1} failed "
                        f"(HTTP {response.status_code}). Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    continue  # Go to next attempt
                else:
                    # Exhausted all retries — return the last failed response
                    # so the caller can handle the error
                    print(
                        f"[VOICEOVER] All {MAX_RETRIES + 1} attempts failed. "
                        f"Last status: {response.status_code}"
                    )
                    return response
            else:
                # Non-retryable error (400/401/403/etc.) — return immediately
                # These are client errors that won't fix themselves on retry
                print(
                    f"[VOICEOVER] Non-retryable error (HTTP {response.status_code}). "
                    f"Not retrying."
                )
                return response

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # --- Network-level failure (no HTTP response at all) ---
            # ConnectionError = can't reach the server (DNS fail, network down, etc.)
            # Timeout = server didn't respond within REQUEST_TIMEOUT seconds
            # Both are transient and worth retrying
            last_exception = e

            if attempt <= MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(
                    f"[VOICEOVER] Attempt {attempt}/{MAX_RETRIES + 1} failed "
                    f"(network error: {type(e).__name__}). Retrying in {delay}s..."
                )
                time.sleep(delay)
                continue
            else:
                # All retries exhausted and we never got an HTTP response
                print(
                    f"[VOICEOVER] All {MAX_RETRIES + 1} attempts failed with "
                    f"network errors. Last error: {e}"
                )
                raise Exception(
                    f"ElevenLabs API unreachable after {MAX_RETRIES + 1} attempts: {e}"
                ) from last_exception

    # Safety fallback — should never reach here, but just in case
    raise Exception("ElevenLabs retry loop exited unexpectedly")


def extract_word_timestamps(alignment):
    """
    # Converts ElevenLabs character-level alignment to word-level
    #
    # ElevenLabs alignment format:
    #   characters: list of characters
    #   character_start_times_seconds: start time for each char
    #   character_end_times_seconds: end time for each char
    #
    # Returns:
    #   list of {word, start, end} dicts
    """

    if not alignment:
        print("[VOICEOVER] WARNING: No alignment data returned")
        return []

    characters = alignment.get("characters", [])
    start_times = alignment.get("character_start_times_seconds", [])
    end_times = alignment.get("character_end_times_seconds", [])

    if not characters or not start_times or not end_times:
        return []

    # --- Build words from characters ---
    words = []
    current_word = ""
    word_start = None

    for i, char in enumerate(characters):
        if char == " ":
            # Space = word boundary
            if current_word:
                words.append({
                    "word": current_word,
                    "start": word_start,
                    "end": end_times[i - 1],
                })
                current_word = ""
                word_start = None
        else:
            if word_start is None:
                word_start = start_times[i]
            current_word += char

    # --- Don't forget the last word ---
    if current_word:
        words.append({
            "word": current_word,
            "start": word_start,
            "end": end_times[-1],
        })

    return words


def get_audio_duration(audio_path):
    """
    # Returns the duration of an audio file in seconds
    """
    from moviepy import AudioFileClip
    clip = AudioFileClip(audio_path)
    duration = clip.duration
    clip.close()
    return duration


# --- Quick test ---
if __name__ == "__main__":
    test_text = "The most powerful people never raise their voice."
    output = os.path.join(config.TEMP_DIR, "test_voiceover.mp3")
    try:
        timestamps = generate_voiceover(test_text, output)
        print(f"\nTimestamps: {json.dumps(timestamps, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your ELEVENLABS_API_KEY is set in .env")
