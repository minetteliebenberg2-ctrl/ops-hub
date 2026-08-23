"""Tests for ImageProcessingService - real resize/rename/EXIF handling
for site photos, mapped out with Minette 2026-08-07."""

import tempfile
import unittest
from pathlib import Path

from PIL import ExifTags, Image

from core.image_processing_service import MAX_DIMENSION, ImageProcessingService


def _make_source_image(path, size, exif_datetime=None):
    image = Image.new("RGB", size, color="red")
    save_kwargs = {}
    if exif_datetime:
        exif = Image.Exif()
        tag = next(t for t, n in ExifTags.TAGS.items() if n == "DateTimeOriginal")
        exif[ExifTags.IFD.Exif] = {tag: exif_datetime}
        save_kwargs["exif"] = exif.tobytes()
    image.save(path, "JPEG", **save_kwargs)


class ImageProcessingServiceTests(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.temp_path = Path(self._temp.name)
        self.service = ImageProcessingService()

    def test_downscales_a_large_image(self):
        source = self.temp_path / "source.jpg"
        _make_source_image(source, (4000, 3000))

        stored_filename, width, height, _taken_at, _hash = self.service.process(
            source, "CAV-001", self.temp_path / "out",
        )

        self.assertLessEqual(width, MAX_DIMENSION)
        self.assertLessEqual(height, MAX_DIMENSION)
        # Aspect ratio preserved (4:3).
        self.assertAlmostEqual(width / height, 4000 / 3000, places=2)

    def test_never_upscales_a_small_image(self):
        source = self.temp_path / "source.jpg"
        _make_source_image(source, (200, 100))

        _stored_filename, width, height, _taken_at, _hash = self.service.process(
            source, "CAV-001", self.temp_path / "out",
        )

        self.assertEqual((width, height), (200, 100))

    def test_stored_file_is_actually_saved_and_readable(self):
        source = self.temp_path / "source.jpg"
        _make_source_image(source, (800, 600))
        out_dir = self.temp_path / "out"

        stored_filename, _w, _h, _taken_at, _hash = self.service.process(source, "CAV-001", out_dir)

        saved_path = out_dir / stored_filename
        self.assertTrue(saved_path.is_file())
        with Image.open(saved_path) as reopened:
            self.assertEqual(reopened.format, "JPEG")

    def test_filename_is_renamed_not_copied_verbatim(self):
        source = self.temp_path / "IMG_20260315_original name.jpg"
        _make_source_image(source, (100, 100))

        stored_filename, _w, _h, _taken_at, _hash = self.service.process(
            source, "CAV-001", self.temp_path / "out",
        )

        self.assertNotEqual(stored_filename, source.name)
        self.assertTrue(stored_filename.startswith("CAV-001_"))
        self.assertTrue(stored_filename.endswith(".jpg"))

    def test_extracts_real_exif_datetime_original(self):
        source = self.temp_path / "source.jpg"
        _make_source_image(source, (100, 100), exif_datetime="2026:03:15 10:30:00")

        _stored_filename, _w, _h, taken_at, _hash = self.service.process(
            source, "CAV-001", self.temp_path / "out",
        )

        self.assertEqual(taken_at, "2026-03-15T10:30:00")

    def test_missing_exif_gives_blank_taken_at_not_a_guess(self):
        source = self.temp_path / "source.jpg"
        _make_source_image(source, (100, 100))

        _stored_filename, _w, _h, taken_at, _hash = self.service.process(
            source, "CAV-001", self.temp_path / "out",
        )

        self.assertEqual(taken_at, "")

    def test_stored_copy_has_exif_stripped_for_privacy(self):
        source = self.temp_path / "source.jpg"
        _make_source_image(source, (100, 100), exif_datetime="2026:03:15 10:30:00")
        out_dir = self.temp_path / "out"

        stored_filename, _w, _h, _taken_at, _hash = self.service.process(source, "CAV-001", out_dir)

        with Image.open(out_dir / stored_filename) as reopened:
            self.assertEqual(len(reopened.getexif()), 0)


if __name__ == "__main__":
    unittest.main()
