# KPay / WavePay Receipt Fraud Detector

A FastAPI service that checks a KPay (KBZPay) or WavePay payment
screenshot for signs of tampering — e.g. someone editing the amount in an
image editor before sending it to you.

## How detection works

Three independent signals are combined into a single `fraud_score` (0–100):

1. **Error Level Analysis (`app/ela.py`)** — re-saves the image at a known
   JPEG quality and looks for regions whose compression error is
   inconsistent with the rest of the image. That inconsistency is a
   classic sign of a pasted-in or re-edited region (e.g. a changed digit).
2. **Metadata check (`app/metadata.py`)** — flags EXIF `Software` tags
   that mention an image editor (Photoshop, GIMP, Snapseed, etc). No EXIF
   at all is normal for a screenshot, so that alone is not flagged.
3. **OCR / template sanity (`app/ocr.py`)** — reads the text with
   Tesseract, confirms KPay/WavePay branding is present, and checks that a
   transaction ID and amount pattern actually appear, the way a real
   receipt's layout would produce.

`app/detector.py` weights and combines these into `fraud_score` plus a
`verdict`: `likely_genuine` (<30), `suspicious` (30–59), or `likely_fake`
(≥60), along with a list of human-readable `reasons`.

## Setup

```bash
# System dependency (OCR engine)
sudo apt-get install tesseract-ocr
# Optional, for Burmese-language text on the receipt:
sudo apt-get install tesseract-ocr-mya

# Python dependencies
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for interactive API docs.

## API

### `POST /detect`

Stateless check — analyzes the image and returns the result. Nothing is saved. Use this for a quick manual check.

Multipart form upload, field name `file` (jpeg/png/webp).

```bash
curl -X POST http://127.0.0.1:8000/detect \
  -F "file=@receipt.jpg"
```

Response:

```json
{
  "verdict": "likely_genuine",
  "fraud_score": 3.1,
  "reasons": [],
  "details": {
    "ela": { "...": "..." },
    "metadata": { "...": "..." },
    "ocr": { "...": "..." }
  }
}
```

### `POST /submit-proof` — the "submit as proof of payment" workflow

This is the endpoint your website's submit button should call. It runs
detection, **saves** the image and result, **auto-decides** a status
using your configured thresholds, and **notifies an admin** for anything
that isn't auto-approved.

Multipart form upload: `file` (required), `reference_id` (optional —
your own order/invoice ID, so you can match the submission back to it).

```bash
curl -X POST http://127.0.0.1:8000/submit-proof \
  -F "file=@receipt.jpg" \
  -F "reference_id=ORDER-1234"
```

Response:

```json
{
  "id": "f441d0bc-da5c-4abe-9d2c-3570477312c3",
  "status": "needs_review",
  "fraud_score": 45.0,
  "verdict": "suspicious",
  "reasons": ["..."]
}
```

`status` is one of:
- `"approved"` — score was low enough to auto-accept
- `"needs_review"` — in between; an admin should look at it
- `"rejected"` — score was high enough to auto-reject

**Set your own thresholds** via environment variables before starting the server:

```bash
# score < 15  -> approved
# score >= 70 -> rejected
# everything in between -> needs_review
export APPROVE_BELOW_THRESHOLD=15
export REJECT_ABOVE_THRESHOLD=70
uvicorn app.main:app --reload
```

Defaults if unset: `APPROVE_BELOW_THRESHOLD=20`, `REJECT_ABOVE_THRESHOLD=60`.

**Admin notifications**: anything not `"approved"` calls `notify_admin()`
(`app/notifications.py`), which always logs to the server console. To
also post to Slack, set a webhook URL:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

To notify by email or something else instead, edit `notify_admin()` —
it's the only function that needs to change.

### Admin review endpoints

- `GET /submissions` — list all submissions. Filter with
  `?status=needs_review`, `?status=approved`, or `?status=rejected`.
- `GET /submissions/{id}` — full detail for one submission.
- `GET /submissions/{id}/image` — the actual uploaded image.
- `PATCH /submissions/{id}/review?status=approved&note=looked fine` —
  manually override the auto-decision after reviewing a flagged one.

### Storage

Submissions are saved to a local SQLite database (`submissions.db` by
default) and the images to a local `uploads/` folder. Both paths are
configurable via `DB_PATH` and `UPLOAD_DIR` env vars. If you deploy with
Docker/Render, note that the filesystem is typically **not persistent**
across redeploys — for production use, mount a persistent volume or swap
`app/storage.py` for a real database/object storage.

## Provider color detection

`app/color_detect.py` detects KPay vs WavePay from the receipt's
dominant color, as a training-free complement to the OCR text check.
It's calibrated from real receipts (not guessed):

- **KBZPay**: ~99% of colorful pixels fall in hue 200–220° (blue) —
  its card border and "Pay" button chrome are blue, even though the
  small logo text is red.
- **WavePay**: ~94% of colorful pixels fall in hue 40–60° (yellow/gold).

OCR text is still tried first (`details.ocr.provider_guess`); color
is the fallback when OCR can't find an English branding keyword —
which matters more than it sounds, since some receipt screens (e.g.
personal-transfer confirmations) are entirely in Burmese with no
English "KPay"/"Wave" text at all, so OCR alone misses the provider
on those. Color caught it correctly in that case during testing.

**Caveat:** calibrated on one real receipt screenshot per provider so
far. If you see misclassifications on other receipt templates (e.g. a
different WavePay screen style than the one tested), collect a few
more real samples, check `details.color` in the `/detect` response
for the actual `kpay_blue_ratio` / `wavepay_gold_ratio`, and adjust
`KPAY_HUE_RANGE` / `WAVEPAY_HUE_RANGE` in `color_detect.py` accordingly.

## Calibrating the score

The weights in `detector.py` are reasonable starting points, not ground
truth. Once you have a small batch of receipts you know are real and a
batch you know are faked, run them through `/detect`, look at the
`details` block, and tune:

- `ela.py`'s `block` size and the `suspicious_score` formula
- the point values in `detector.py` (currently ELA≤55, metadata≤25,
  OCR/template≤25)
- the `likely_genuine` / `suspicious` / `likely_fake` cutoffs

## Deploying (Render / Railway)

The app needs the `tesseract-ocr` system binary, not just Python
packages, so deploy it using the included `Dockerfile` rather than a
plain buildpack — that's the only way to guarantee tesseract is actually
installed on the server.

**Steps (same shape on both Render and Railway):**

1. Push this project to a GitHub repo.
2. On Render: New → Web Service → connect the repo → it will
   auto-detect the `Dockerfile` and build from it.
   On Railway: New Project → Deploy from GitHub repo → it also
   auto-detects the `Dockerfile`.
3. No build/start command needed — the `Dockerfile`'s `CMD` handles
   startup, and both platforms inject the `$PORT` environment variable
   automatically (already wired up in the Dockerfile).
4. Once deployed you'll get a permanent URL like
   `https://your-app.onrender.com`. Your endpoint is
   `https://your-app.onrender.com/detect`, and docs are at
   `https://your-app.onrender.com/docs`.

**Free tier note:** Render's free web services sleep after ~15 minutes
of inactivity; the next request wakes it up but takes 30-60s. Fine for
a demo/side project, not for something latency-sensitive — upgrade the
plan if that matters.

## Known limitations

- ELA is a heuristic, not a proof of tampering — heavy re-compression
  (e.g. sending an image through multiple chat apps) can also raise the
  score. Treat `suspicious` as "worth a second look," not certain fraud.
- OCR quality depends on image resolution; very compressed or blurry
  screenshots will produce weaker `txn_id`/`amount` matches.
- This does not verify the transaction against KBZPay/Wave's own systems
  — it only inspects the image itself. For real certainty, cross-check
  the transaction ID against the payment provider if you have API access.
