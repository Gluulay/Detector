"""
Brand-color based provider detection.

Hue ranges below are measured from real receipts, not guessed:
  - KBZPay: ~99% of colorful pixels fall in hue 200-220 (blue) —
    its card border and "Pay" button chrome are blue, even though the
    small logo text is red.
  - WavePay: ~94% of colorful pixels fall in hue 40-60 (yellow/gold).
This is a cheap, training-free signal that complements the OCR text
check in ocr.py. Caveat: calibrated on one real receipt per provider
so far — if you see misclassifications on other receipt templates
(e.g. WavePay's own "E-Receipt" style vs. a personal-transfer
confirmation screen), collect more samples and adjust the ranges
below (see README "Calibrating provider color detection").
"""

import io

import numpy as np
from PIL import Image

MIN_SATURATION = 60  # out of 255 — filters out white/gray/black background
MIN_VALUE = 60  # out of 255
MIN_RATIO_TO_COUNT = 0.05  # a color band needs at least 5% of colorful pixels to matter
DOMINANCE_RATIO = 1.5  # how much more one band needs vs the other to "win"

KPAY_HUE_RANGE = (195, 228)  # blue
WAVEPAY_HUE_RANGE = (35, 68)  # yellow/gold


def detect_provider_by_color(image_bytes: bytes) -> dict:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image.thumbnail((200, 200))  # color proportions don't need full resolution

    hsv = np.array(image.convert("HSV")).astype(np.int32)
    hue = hsv[:, :, 0].astype(np.float32) * (360.0 / 255.0)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    colorful = (sat >= MIN_SATURATION) & (val >= MIN_VALUE)
    total_colorful = int(colorful.sum())

    if total_colorful == 0:
        return {
            "provider_guess": None,
            "kpay_blue_ratio": 0.0,
            "wavepay_gold_ratio": 0.0,
            "confidence": "none",
        }

    kpay_mask = colorful & (hue >= KPAY_HUE_RANGE[0]) & (hue <= KPAY_HUE_RANGE[1])
    wavepay_mask = colorful & (hue >= WAVEPAY_HUE_RANGE[0]) & (hue <= WAVEPAY_HUE_RANGE[1])

    kpay_ratio = round(float(kpay_mask.sum()) / total_colorful, 3)
    wavepay_ratio = round(float(wavepay_mask.sum()) / total_colorful, 3)

    provider_guess = None
    if kpay_ratio >= MIN_RATIO_TO_COUNT and kpay_ratio >= wavepay_ratio * DOMINANCE_RATIO:
        provider_guess = "kpay"
    elif wavepay_ratio >= MIN_RATIO_TO_COUNT and wavepay_ratio >= kpay_ratio * DOMINANCE_RATIO:
        provider_guess = "wavepay"

    if provider_guess:
        dominant_ratio = max(kpay_ratio, wavepay_ratio)
        confidence = "high" if dominant_ratio > 0.3 else "medium"
    else:
        confidence = "none"

    return {
        "provider_guess": provider_guess,
        "kpay_blue_ratio": kpay_ratio,
        "wavepay_gold_ratio": wavepay_ratio,
        "confidence": confidence,
    }
