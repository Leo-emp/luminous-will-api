import numpy as np
import config

# ============================================================
# COLOR GRADING
# Applies dark, cinematic aesthetic to stock footage
# Matches the Luminous Will brand: moody, desaturated, high contrast
#
# CALIBRATED from real video analysis:
#   - Target brightness: 24% (V channel ~61/255)
#   - Target saturation: 28% (mix of B&W and warm tones)
#   - Cool shadow tints, warm highlight tints
#   - High contrast with crushed blacks
#
# Reference videos analyzed:
#   - "The quiet leader vs the loud victim" (brightness 24%, sat 10%)
#   - "High value solitude" (brightness 25%, sat 47%)
# ============================================================


def apply_dark_grade(frame):
    """
    # Applies dark cinematic color grading to a single frame
    # Calibrated to match actual Luminous Will video look
    #
    # Processing chain:
    #   1. Reduce brightness -> dark overall tone
    #   2. Reduce saturation -> moody/desaturated
    #   3. Boost contrast -> punchy darks and lights
    #   4. Crush blacks -> deep shadows (no milky grays)
    #   5. Split toning -> cool shadows + warm highlights
    #
    # Args:
    #   frame: numpy array (H, W, 3) RGB uint8
    #
    # Returns:
    #   graded frame as numpy array (H, W, 3) RGB uint8
    """

    # --- Convert to float32 (half the memory of float64) ---
    img = frame.astype(np.float32) / 255.0

    # --- Step 1: Reduce brightness ---
    img *= config.BRIGHTNESS_FACTOR

    # --- Step 2: Desaturate ---
    # Blend between grayscale and original color (in-place to save memory)
    lum = np.float32(0.299) * img[:,:,0] + np.float32(0.587) * img[:,:,1] + np.float32(0.114) * img[:,:,2]
    for c in range(3):
        img[:,:,c] = lum + np.float32(config.SATURATION_FACTOR) * (img[:,:,c] - lum)
    del lum

    # --- Step 3: Boost contrast ---
    midpoint = np.float32(0.25)
    img = midpoint + np.float32(config.CONTRAST_FACTOR) * (img - midpoint)

    # --- Step 4: Crush blacks ---
    mask = img < 0.08
    img[mask] *= np.float32(0.3)

    # --- Step 5: Split toning ---
    avg = img.mean(axis=-1)
    # Shadows: add subtle blue tint
    shadow_px = avg < 0.25
    img[:,:,2][shadow_px] += np.float32(0.04)
    # Highlights: add subtle warm/amber tint
    hi_px = avg > 0.5
    img[:,:,0][hi_px] += np.float32(0.03)
    img[:,:,1][hi_px] += np.float32(0.015)
    del avg, shadow_px, hi_px

    # --- Step 6: Subtle vignette ---
    h, w = img.shape[:2]
    Y = np.linspace(-1, 1, h, dtype=np.float32)
    X = np.linspace(-1, 1, w, dtype=np.float32)
    dist = np.sqrt(Y[:,None]**2 + X[None,:]**2)
    vignette = np.float32(1.0) - np.float32(0.3) * np.clip(dist - 0.5, 0, 1)
    for c in range(3):
        img[:,:,c] *= vignette
    del dist, vignette

    # --- Clamp and return ---
    np.clip(img, 0, 1, out=img)
    return (img * 255).astype(np.uint8)


def apply_dark_grade_filter(get_frame, t):
    """
    # MoviePy-compatible filter function
    # Use with clip.transform(apply_dark_grade_filter)
    """
    return apply_dark_grade(get_frame(t))


def create_grader(profile):
    """
    # Returns a grading function calibrated to the format profile's
    # brightness and saturation settings
    """
    brightness = profile.get("brightness_factor", config.BRIGHTNESS_FACTOR)
    saturation = profile.get("saturation_factor", config.SATURATION_FACTOR)

    def grade_frame(frame):
        img = frame.astype(np.float32) / 255.0

        img *= brightness

        lum = np.float32(0.299) * img[:,:,0] + np.float32(0.587) * img[:,:,1] + np.float32(0.114) * img[:,:,2]
        for c in range(3):
            img[:,:,c] = lum + np.float32(saturation) * (img[:,:,c] - lum)
        del lum

        midpoint = np.float32(0.25)
        img = midpoint + np.float32(config.CONTRAST_FACTOR) * (img - midpoint)

        mask = img < 0.08
        img[mask] *= np.float32(0.3)

        avg = img.mean(axis=-1)
        shadow_px = avg < 0.25
        img[:,:,2][shadow_px] += np.float32(0.04)
        hi_px = avg > 0.5
        img[:,:,0][hi_px] += np.float32(0.03)
        img[:,:,1][hi_px] += np.float32(0.015)
        del avg, shadow_px, hi_px

        h, w = img.shape[:2]
        Y = np.linspace(-1, 1, h, dtype=np.float32)
        X = np.linspace(-1, 1, w, dtype=np.float32)
        dist = np.sqrt(Y[:,None]**2 + X[None,:]**2)
        vignette = np.float32(1.0) - np.float32(0.3) * np.clip(dist - 0.5, 0, 1)
        for c in range(3):
            img[:,:,c] *= vignette
        del dist, vignette

        np.clip(img, 0, 1, out=img)
        return (img * 255).astype(np.uint8)

    return grade_frame
