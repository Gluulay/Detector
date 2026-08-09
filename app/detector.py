"""
Combines the individual signals (ELA, metadata, OCR/template) into one
fraud score and verdict. Scoring weights are heuristic starting points —
tune them once you have a batch of known-real and known-fake receipts to
test against (see README "Calibrating the score").
"""

from .ela import compute_ela
from .metadata import analyze_metadata
from .ocr import extract_receipt_text


def run_detection(image_bytes: bytes) -> dict:
    ela = compute_ela(image_bytes)
    meta = analyze_metadata(image_bytes)
    ocr = extract_receipt_text(image_bytes)

    score = 0.0
    reasons = []

    # --- ELA: up to 55 points ---
    ela_contribution = min(55.0, ela["suspicious_score"] * 0.55)
    score += ela_contribution
    if ela["suspicious_score"] > 40:
        reasons.append(
            "Uneven compression pattern detected — possible pasted or edited region"
        )

    # --- Metadata: up to 25 points ---
    if meta["flags"]:
        score += 25.0
        reasons.extend(meta["flags"])

    # --- OCR / template sanity: up to 25 points ---
    if ocr["provider_guess"] is None:
        score += 15.0
        reasons.append("Could not confirm KPay or WavePay branding in the extracted text")
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
        },
    }
