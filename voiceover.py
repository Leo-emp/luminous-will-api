import os
import json
import requests
import config

# ============================================================
# VOICEOVER GENERATOR
# Uses ElevenLabs API to generate speech with word timestamps
# Voice: Adam (deep English story voice)
# ============================================================


def generate_voiceover(script_text, output_path):
    """
    # Generates voiceover audio from script text using ElevenLabs
    # Returns word-level timestamps for caption syncing
    #
    # Args:
    #   script_text: full script as a single string
    #   output_path: where to save the .mp3 file
    #
    # Returns:
    #   list of dicts with keys: word, start, end (times in seconds)
    """

    print("[VOICEOVER] Generating speech with ElevenLabs...")

    # --- Build the API request ---
    # Using the "with timestamps" endpoint for word-level sync
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}/with-timestamps"

    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "text": script_text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": config.VOICE_SETTINGS,
        # Speed control: 0.83 as specified
        "speed": config.VOICE_SPEED,
    }

    # --- Make the API call ---
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        print(f"[VOICEOVER] ERROR: API returned {response.status_code}")
        print(f"[VOICEOVER] Response: {response.text}")
        raise Exception(f"ElevenLabs API error: {response.status_code}")

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
