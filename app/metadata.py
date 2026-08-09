"""
EXIF / metadata sanity checks.

A genuine KPay or WavePay receipt is normally a raw phone screenshot: it
either has no EXIF at all, or EXIF from the phone's screenshot tool. If the
metadata mentions a photo editor (Photoshop, GIMP, Snapseed, PicsArt...),
that's a meaningful red flag that the image passed through an editing tool.
Missing EXIF on its own is NOT suspicious — most screenshots never had any.
"""

import io

from PIL import ExifTags, Image

SUSPICIOUS_SOFTWARE_TAGS = [
    "photoshop",
    "gimp",
    "snapseed",
    "picsart",
    "lightroom",
    "pixlr",
    "canva",
    "paint.net",
    "affinity photo",
]


def analyze_metadata(image_bytes: bytes) -> dict:
    image = Image.open(io.BytesIO(image_bytes))
    exif_raw = image._getexif() if hasattr(image, "_getexif") else None

    flags = []
    software = None

    if exif_raw:
        exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
        software = str(exif.get("Software", "") or "")
        software_lower = software.lower()
        if any(tag in software_lower for tag in SUSPICIOUS_SOFTWARE_TAGS):
            flags.append(f"EXIF 'Software' tag mentions an image editor: '{software}'")

    return {
        "has_exif": exif_raw is not None,
        "software_tag": software,
        "flags": flags,
    }
