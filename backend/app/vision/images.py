"""Upload checks and re-encoding of chart images (Y14). The image is never stored: only its
SHA-256, size and dimensions.

- The type comes from the **magic bytes** (PNG, JPEG, WebP), never from the client's header.
- Size at most ``CHART_IMAGE_MAX_BYTES`` (413), at least 200 x 200 px (422), at most
  ``MAX_PIXELS`` pixels before decoding (422; a decompression bomb never gets decoded, and
  Pillow's own ``MAX_IMAGE_PIXELS`` guard is set to the same limit).
- Re-encoded with Pillow: EXIF orientation applied, converted to RGB, longest side at most
  1568 px, every metadata entry dropped (no EXIF, ICC or text chunk survives), saved as PNG,
  or as a quality-90 JPEG when the PNG would be over 1 MB.
- Memory (backend: 544m for two workers): in-place steps, a reduced-scale JPEG decode, and the
  service runs this on **one thread per worker**, so one upload is decoded at a time.
"""

from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MIN_SIDE = 200
MAX_SIDE = 1568  # longest side sent to the model
MAX_PIXELS = 40_000_000  # ~ 8000 x 5000; larger is refused before decoding
PNG_MAX_BYTES = 1_000_000  # above: a JPEG (quality 90, 4:4:4) is sent instead
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow's own bomb guard (warns above, raises at 2x)

MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


class ImageRejected(Exception):
    """An upload that is refused: ``status`` 413, 415 or 422 and a stable ``code``."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class PreparedImage:
    data: bytes  # the re-encoded PNG sent to the model
    mime: str  # always image/png after re-encoding
    sha256: str  # of the uploaded bytes (duplicates)
    original_mime: str
    original_bytes: int
    width: int  # of the uploaded image
    height: int
    sent_width: int
    sent_height: int


def sniff(data: bytes) -> str | None:
    """The image type from the first bytes; None for anything else."""
    for magic, mime in MAGIC:
        if data.startswith(magic):
            return mime
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def prepare(data: bytes, max_bytes: int) -> PreparedImage:
    """Check and re-encode one upload (module docstring). Raises :class:`ImageRejected`."""
    if len(data) > max_bytes:
        raise ImageRejected(413, "image_too_large", f"the image is larger than {max_bytes} bytes")
    mime = sniff(data)
    if mime is None:
        raise ImageRejected(415, "unsupported_image", "only PNG, JPEG and WebP images are accepted")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))  # reads the header only
            width, height = img.size
            if width * height > MAX_PIXELS:
                raise ImageRejected(
                    422, "image_too_many_pixels", f"the image has more than {MAX_PIXELS} pixels"
                )
            if min(width, height) < MIN_SIDE:
                raise ImageRejected(
                    422,
                    "image_too_small",
                    f"the image must be at least {MIN_SIDE} x {MIN_SIDE} pixels",
                )
            # memory: a JPEG is decoded at a reduced scale when it is 2x+ the target, every
            # step works in place where Pillow allows it, and nothing is copied for metadata
            img.draft("RGB", (MAX_SIDE, MAX_SIDE))
            img.load()
            ImageOps.exif_transpose(img, in_place=True)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            img.info.clear()  # EXIF, ICC profile, text chunks: never written back
            sent, sent_mime = _encode(img)
    except ImageRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageRejected(
            422, "image_too_many_pixels", f"the image has more than {MAX_PIXELS} pixels"
        ) from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageRejected(
            422, "invalid_image", f"the image cannot be read: {exc}"[:200]
        ) from None
    return PreparedImage(
        data=sent,
        mime=sent_mime,
        sha256=hashlib.sha256(data).hexdigest(),
        original_mime=mime,
        original_bytes=len(data),
        width=width,
        height=height,
        sent_width=img.width,
        sent_height=img.height,
    )


def _encode(img: Image.Image) -> tuple[bytes, str]:
    """PNG (lossless: sharp axis labels), or a high-quality JPEG when the PNG would be over
    ``PNG_MAX_BYTES`` (a photo of a screen, a noisy chart): a smaller request, and fewer bytes
    held while the model answers."""
    out = io.BytesIO()
    img.save(out, format="PNG")
    if out.tell() <= PNG_MAX_BYTES:
        return out.getvalue(), "image/png"
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, subsampling=0)  # 4:4:4 keeps text edges
    return out.getvalue(), "image/jpeg"
