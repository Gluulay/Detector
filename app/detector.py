"""
Combines ELA, metadata, OCR/template, and brand-color signals into one
fraud score and verdict. Scoring weights are heuristic starting points —
tune them once you have a batch of known-real and known-fake receipts to
test against (see README "Calibrating the score").
"""

from .color_detect import detect_provider_by_color
from .ela import compute_ela
from .metadata import analyze_metadata
from .ocr import extract_receipt_text


def _resolve_provider(ocr_provider, color: dict):
    """
    OCR text is the primary signal — it correctly identified the
    provider in testing. Color is kept as a secondary, informational
    signal only: an initial test against a real KBZPay receipt showed
    its overall template uses blue chrome (not red) outside the small
    logo text, so the naive "KBZ=red, Wave=blue" assumption doesn't
    reliably hold yet. Color is NOT used to adjust the fraud score
    until it's been validated against a real batch of both providers'
    receipts — see README "Calibrating provider color detection".
    """
    if ocr_provider:
        return ocr_provider, "high"
    if color["provider_guess"]:
        return color["provider_guess"], color["confidence"]
    return None, "none"


def run_detection(image_bytes: bytes) -> dict:
    ela = compute_ela(image_bytes)
    meta = analyze_metadata(image_bytes)
    ocr = extract_receipt_text(image_bytes)
    color = detect_provider_by_color(image_bytes)

    provider, confidence = _resolve_provider(ocr["provider_guess"], color)

    score = 0.0
    reasons = []

    # --- ELA: up to 45 points ---
    ela_contribution = min(45.0, ela["suspicious_score"] * 0.45)
    score += ela_contribution
    if ela["suspicious_score"] > 40:
        reasons.append(
            "Uneven compression pattern detected — possible pasted or edited region"
        )

    # --- Metadata: up to 20 points ---
    if meta["flags"]:
        score += 20.0
        reasons.extend(meta["flags"])

    # --- OCR / template sanity: up to 20 points ---
    if provider is None:
        score += 10.0
        reasons.append("Could not confirm KPay or WavePay branding in the image")
    if not ocr["txn_id_candidates"]:
        score += 5.0
        reasons.append("No transaction ID pattern found")
    if not ocr["amount_candidates"]:
        score += 5.0
        reasons.append("No amount found")

    score = round(min(100.0, score), 1)

    if score >= 60:
        verdict = "likely_fake"
    elif score >= 30:
        verdict = "suspicious"
    else:
        verdict = "likely_genuine"

    return {
        "verdict": verdict,
        "fraud_score": score,
        "reasons": reasons,
        "details": {
            "ela": ela,
            "metadata": meta,
            "ocr": ocr,
            "color": color,
            "provider": {"guess": provider, "confidence": confidence},
        },
    }
