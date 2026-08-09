"""
Error Level Analysis (ELA).

Idea: if we re-save an image at a known JPEG quality, genuine unedited
regions will compress predictably. Regions that were pasted in or edited
later (e.g. someone changed the amount in a screenshot) have usually been
compressed a different number of times, so they show a different error
level than the rest of the image after a re-save. We look for that
localized inconsistency rather than a single global brightness value.
"""

import io

import numpy as np
from PIL import Image, ImageChops


def compute_ela(image_bytes: bytes, quality: int = 90, block: int = 16) -> dict:
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    buffer = io.BytesIO()
    original.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)

    diff = ImageChops.difference(original, resaved)
    diff_array = np.array(diff).astype(np.float32)

    if diff_array.size == 0:
        return {
            "max_diff": 0.0,
            "mean_diff": 0.0,
            "block_std": 0.0,
            "block_max": 0.0,
            "suspicious_score": 0.0,
        }

    max_diff = float(diff_array.max())
    mean_diff = float(diff_array.mean())

    h, w, _ = diff_array.shape
    block_means = [
        diff_array[y : y + block, x : x + block].mean()
        for y in range(0, max(h - block, 1), block)
        for x in range(0, max(w - block, 1), block)
    ]
    block_means = np.array(block_means) if block_means else np.array([0.0])
    block_std = float(block_means.std())
    block_max = float(block_means.max())

    # Heuristic: a big spread between the "quietest" and "loudest" blocks,
    # plus a genuinely hot block, suggests localized tampering rather than
    # uniform recompression noise across the whole image.
    suspicious_score = round(min(100.0, block_std * 6 + block_max * 1.5), 2)

    return {
        "max_diff": round(max_diff, 2),
        "mean_diff": round(mean_diff, 2),
        "block_std": round(block_std, 2),
        "block_max": round(block_max, 2),
        "suspicious_score": suspicious_score,
    }
