# ==========================================================
# FC Hub - Image Processing Service
# ----------------------------------------------------------
# Purpose:
# Auto rename/resize/strip-EXIF for site photos on upload, mapped out
# with Minette 2026-08-07 - she shouldn't have to do this by hand
# before a photo goes into a Site Visit or (later) her own website.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import ExifTags, Image

MAX_DIMENSION = 1000
JPEG_QUALITY = 85

# The EXIF tag ID for "DateTimeOriginal" - resolved by name once at
# import time rather than hardcoding the numeric tag (36867), so this
# stays readable and correct if Pillow's tag table ever changes.
_DATETIME_ORIGINAL_TAG = next(
    (tag_id for tag_id, name in ExifTags.TAGS.items() if name == "DateTimeOriginal"), None,
)


class ImageProcessingService:
    """Pure processing - takes a source file, returns a saved, resized,
    EXIF-stripped JPEG plus the metadata worth keeping. No database or
    customer-folder knowledge here; SiteImageService orchestrates
    those on top of this."""

    def process(self, source_path, filename_prefix, destination_dir):
        """Resize (never upscale), strip EXIF (privacy - this may end
        up on her public website later), rename, and save into
        destination_dir.

        Returns (stored_filename, width, height, taken_at) - taken_at
        is "" when the source has no readable DateTimeOriginal tag,
        never a guess.
        """

        source_path = Path(source_path)
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        file_hash = hashlib.md5(source_path.read_bytes()).hexdigest()

        with Image.open(source_path) as image:
            taken_at = self._extract_taken_at(image)
            image = image.convert("RGB")  # drop alpha/palette weirdness before a JPEG save
            image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            width, height = image.size

            stored_filename = (
                f"{filename_prefix}_{datetime.now().strftime('%Y%m%d')}_{uuid4().hex[:8]}.jpg"
            )
            target_path = destination_dir / stored_filename
            # exif=b"" strips all EXIF (including GPS) from the saved copy.
            image.save(target_path, "JPEG", quality=JPEG_QUALITY, exif=b"")

        return stored_filename, width, height, taken_at, file_hash

    # --------------------------------------------------

    def _extract_taken_at(self, image):

        if _DATETIME_ORIGINAL_TAG is None:
            return ""
        try:
            exif = image.getexif()
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif) if exif else {}
            raw = exif_ifd.get(_DATETIME_ORIGINAL_TAG, "") or exif.get(_DATETIME_ORIGINAL_TAG, "")
        except Exception:
            return ""
        if not raw:
            return ""
        try:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").isoformat(timespec="seconds")
        except ValueError:
            return ""
