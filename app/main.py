from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import storage
from .decision import decide_status
from .detector import run_detection
from .notifications import notify_admin

app = FastAPI(
    title="KPay / WavePay Receipt Fraud Detector",
    description="Upload a KPay or WavePay payment screenshot to check it for signs of tampering.",
    version="0.2.0",
)

# Allows a browser-based frontend (your website, or the test page) hosted
# on a different origin to call this API. Locked down to "*" (any origin)
# for now since this is a testing/demo setup — tighten to your actual
# website's domain before treating this as production-hardened.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.on_event("startup")
def _startup() -> None:
    storage.init_db()


@app.get("/")
def root():
    return {"status": "ok", "service": "kpay-wavepay-detector"}


@app.post("/detect")
async def detect(file: UploadFile = File(...)):
    """Stateless check — analyzes the image and returns the result. Nothing is saved."""
    image_bytes = await _read_validated(file)
    try:
        result = run_detection(image_bytes)
    except Exception as exc:  # noqa: BLE001 - surface as a clean 422 to the client
        raise HTTPException(status_code=422, detail=f"Could not process image: {exc}")
    return result


@app.post("/submit-proof")
async def submit_proof(
    file: UploadFile = File(...),
    reference_id: Optional[str] = Form(
        None, description="Your own order/invoice ID, so you can match this submission back to it"
    ),
):
    """
    The endpoint your website's 'submit proof of payment' button should
    call. Runs detection, saves the submission, auto-decides a status
    using your configured thresholds (see app/config.py), and notifies
    an admin for anything that isn't auto-approved.
    """
    image_bytes = await _read_validated(file)

    try:
        detection = run_detection(image_bytes)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Could not process image: {exc}")

    status = decide_status(detection["fraud_score"])
    record = storage.save_submission(image_bytes, reference_id, detection, status)

    if status != "approved":
        notify_admin(record)

    return {
        "id": record["id"],
        "status": status,  # "approved" | "needs_review" | "rejected"
        "fraud_score": detection["fraud_score"],
        "verdict": detection["verdict"],
        "reasons": detection["reasons"],
    }


@app.get("/submissions")
def list_submissions(status: Optional[str] = None, provider: Optional[str] = None, reference_id: Optional[str] = None):
    """
    Admin view: list submissions.
    Filter with ?status=needs_review, ?provider=kpay (or wavepay), and/or
    ?reference_id=... to see one customer/order's submission history.
    """
    records = storage.list_submissions(status=status, provider=provider)
    if reference_id:
        records = [r for r in records if r.get("reference_id") == reference_id]
    return records


@app.get("/submissions/{submission_id}")
def get_submission(submission_id: str):
    record = storage.get_submission(submission_id)
    if not record:
        raise HTTPException(status_code=404, detail="Submission not found")
    return record


@app.get("/submissions/{submission_id}/image")
def get_submission_image(submission_id: str):
    record = storage.get_submission(submission_id)
    if not record:
        raise HTTPException(status_code=404, detail="Submission not found")
    return FileResponse(record["image_path"])


@app.patch("/submissions/{submission_id}/review")
def review_submission(submission_id: str, status: str, note: Optional[str] = None):
    """Admin manually overrides the auto-decision after looking at a flagged submission."""
    if status not in {"approved", "rejected", "needs_review"}:
        raise HTTPException(status_code=400, detail="status must be approved, rejected, or needs_review")
    record = storage.mark_reviewed(submission_id, status, note)
    if not record:
        raise HTTPException(status_code=404, detail="Submission not found")
    return record


async def _read_validated(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    return image_bytes
