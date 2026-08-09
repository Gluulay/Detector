"""
OCR extraction + light template checks.

Pulls text out of the receipt with Tesseract, guesses whether it's a KPay
or WavePay receipt from keywords, and checks that a transaction ID and an
amount pattern are actually present. A real receipt has a structured,
predictable layout, so a missing transaction ID or amount is itself a
signal something's off (cropped, faked from scratch, or a non-receipt
image entirely).

Note: for Burmese-language OCR, install the 'mya' tesseract language pack
(see README). Falls back to English-only if it isn't installed.
"""

import io
import os
import platform
import re

import pytesseract
from PIL import Image

# Windows terminals/IDEs often cache an old PATH even after it's been
# updated, which makes pytesseract fail to find tesseract.exe even though
# it's installed. Point straight at the default install location as a
# fallback so the app doesn't depend on the running process's PATH being
# fresh.
if platform.system() == "Windows":
    _default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_default_win_path):
        pytesseract.pytesseract.tesseract_cmd = _default_win_path

KPAY_KEYWORDS = ["kbz", "kpay", "k pay", "kbzpay"]
WAVEPAY_KEYWORDS = ["wave", "wavepay", "wave money", "wavemoney"]

TXN_ID_PATTERN = re.compile(r"\b[A-Z0-9]{8,20}\b")
AMOUNT_PATTERN = re.compile(r"\b([0-9][0-9,]{2,})\s*(MMK|Ks)?\b", re.IGNORECASE)


def _ocr_text(image: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(image, lang="eng+mya")
    except pytesseract.TesseractError:
        # 'mya' language pack not installed — fall back to English only.
        return pytesseract.image_to_string(image, lang="eng")


def extract_receipt_text(image_bytes: bytes) -> dict:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    text = _ocr_text(image)
    lower = text.lower()

    provider = None
    if any(k in lower for k in KPAY_KEYWORDS):
        provider = "kpay"
    elif any(k in lower for k in WAVEPAY_KEYWORDS):
        provider = "wavepay"

    txn_ids = TXN_ID_PATTERN.findall(text)
    amounts = [m[0] for m in AMOUNT_PATTERN.findall(text)]

    return {
        "raw_text": text.strip(),
        "provider_guess": provider,
        "txn_id_candidates": txn_ids[:5],
        "amount_candidates": amounts[:5],
    }
