# ==========================================================
# FC Hub - Gallery Services
# ----------------------------------------------------------
# Purpose:
# Image management, EXIF metadata extraction, project galleries.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import json

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class ImageMetadata:
    """Image metadata including EXIF"""

    filename: str
    filepath: str
    project_id: str = ""
    phase: str = ""  # Before, During, After
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # EXIF data
    date_taken: str = ""
    camera_model: str = ""
    camera_make: str = ""
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    focal_length: str = ""
    iso_speed: str = ""
    f_number: str = ""
    exposure_time: str = ""

    # Management
    uploaded_date: str = ""
    last_modified: str = ""
    file_size: int = 0
    dimensions: str = ""  # WIDTHxHEIGHT

    def to_dict(self):
        return {
            "filename": self.filename,
            "filepath": self.filepath,
            "project_id": self.project_id,
            "phase": self.phase,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "date_taken": self.date_taken,
            "camera_model": self.camera_model,
            "camera_make": self.camera_make,
            "gps": {
                "latitude": self.gps_latitude,
                "longitude": self.gps_longitude,
                "altitude": self.gps_altitude,
            },
            "camera_settings": {
                "focal_length": self.focal_length,
                "iso": self.iso_speed,
                "f_number": self.f_number,
                "exposure_time": self.exposure_time,
            },
            "uploaded_date": self.uploaded_date,
            "file_size": self.file_size,
            "dimensions": self.dimensions,
        }


class EXIFExtractor:
    """Extract EXIF metadata from images"""

    def __init__(self):
        self.available = PIL_AVAILABLE

    # --------------------------------------------------

    def extract(self, filepath: str) -> Dict:
        """Extract EXIF data from image file"""
        exif_data = {}

        if not self.available:
            return exif_data

        try:
            image = Image.open(filepath)
            exif_raw = image._getexif()

            if exif_raw:
                for tag_id, value in exif_raw.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    exif_data[tag_name] = str(value)[:100]  # Limit value length

            # Get image dimensions
            exif_data["ImageWidth"] = image.width
            exif_data["ImageHeight"] = image.height

        except Exception:
            pass

        return exif_data

    # --------------------------------------------------

    def get_date_taken(self, exif_data: Dict) -> str:
        """Extract date taken from EXIF"""
        for key in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
            if key in exif_data:
                return exif_data[key]
        return ""

    # --------------------------------------------------

    def get_camera_info(self, exif_data: Dict) -> tuple:
        """Extract camera make and model"""
        make = exif_data.get("Make", "")
        model = exif_data.get("Model", "")
        return (make, model)

    # --------------------------------------------------

    def get_gps_coords(self, exif_data: Dict) -> tuple:
        """Extract GPS coordinates"""
        lat = exif_data.get("GPSInfo", {}).get("Latitude")
        lon = exif_data.get("GPSInfo", {}).get("Longitude")
        alt = exif_data.get("GPSInfo", {}).get("Altitude")
        return (lat, lon, alt)

    # --------------------------------------------------

    def get_camera_settings(self, exif_data: Dict) -> Dict:
        """Extract camera settings"""
        return {
            "focal_length": exif_data.get("FocalLength", ""),
            "iso_speed": exif_data.get("ISOSpeedRatings", ""),
            "f_number": exif_data.get("FNumber", ""),
            "exposure_time": exif_data.get("ExposureTime", ""),
        }


class GalleryService:
    """Service for managing image galleries"""

    def __init__(self):
        self.images: Dict[str, ImageMetadata] = {}
        self.projects: Dict[str, Dict] = {}
        self.exif_extractor = EXIFExtractor()

    # --------------------------------------------------

    def add_image(self, metadata: ImageMetadata) -> bool:
        """Add image to gallery"""
        try:
            if not Path(metadata.filepath).exists():
                return False

            # Extract EXIF if available
            exif_data = self.exif_extractor.extract(metadata.filepath)

            if exif_data:
                metadata.date_taken = self.exif_extractor.get_date_taken(exif_data)
                metadata.camera_make, metadata.camera_model = self.exif_extractor.get_camera_info(exif_data)

                settings = self.exif_extractor.get_camera_settings(exif_data)
                metadata.focal_length = settings.get("focal_length", "")
                metadata.iso_speed = settings.get("iso_speed", "")
                metadata.f_number = settings.get("f_number", "")
                metadata.exposure_time = settings.get("exposure_time", "")

                if "ImageWidth" in exif_data and "ImageHeight" in exif_data:
                    metadata.dimensions = f"{exif_data['ImageWidth']}x{exif_data['ImageHeight']}"

            # File info
            metadata.file_size = Path(metadata.filepath).stat().st_size
            metadata.uploaded_date = datetime.now().isoformat(timespec="seconds")
            metadata.last_modified = datetime.now().isoformat(timespec="seconds")

            self.images[metadata.filepath] = metadata

            # Track in project
            if metadata.project_id:
                if metadata.project_id not in self.projects:
                    self.projects[metadata.project_id] = {
                        "Before": [],
                        "During": [],
                        "After": [],
                    }
                self.projects[metadata.project_id][metadata.phase].append(metadata.filepath)

            return True

        except Exception:
            return False

    # --------------------------------------------------

    def get_images_by_project(self, project_id: str, phase: str = None) -> List[ImageMetadata]:
        """Get images for a project"""
        if project_id not in self.projects:
            return []

        images = []

        if phase:
            filepaths = self.projects[project_id].get(phase, [])
            images = [self.images[fp] for fp in filepaths if fp in self.images]
        else:
            for phase_images in self.projects[project_id].values():
                images.extend([self.images[fp] for fp in phase_images if fp in self.images])

        return images

    # --------------------------------------------------

    def get_images_by_tag(self, tag: str) -> List[ImageMetadata]:
        """Get images with specific tag"""
        return [img for img in self.images.values() if tag in img.tags]

    # --------------------------------------------------

    def update_image_metadata(self, filepath: str, **kwargs):
        """Update image metadata"""
        if filepath in self.images:
            for key, value in kwargs.items():
                if hasattr(self.images[filepath], key):
                    setattr(self.images[filepath], key, value)
            self.images[filepath].last_modified = datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def export_project_gallery(self, project_id: str, filepath: str):
        """Export project gallery metadata to JSON"""
        images = self.get_images_by_project(project_id)

        data = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "project_id": project_id,
            "image_count": len(images),
            "images": [img.to_dict() for img in images],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # --------------------------------------------------

    def get_gallery_summary(self, project_id: str) -> Dict:
        """Get summary of project gallery"""
        project_images = self.projects.get(project_id, {})

        return {
            "project_id": project_id,
            "total_images": sum(len(images) for images in project_images.values()),
            "before": len(project_images.get("Before", [])),
            "during": len(project_images.get("During", [])),
            "after": len(project_images.get("After", [])),
            "cameras": list(set(
                img.camera_make for img in self.get_images_by_project(project_id)
                if img.camera_make
            )),
            "date_range": self._get_date_range(project_id),
        }

    # --------------------------------------------------

    def _get_date_range(self, project_id: str) -> tuple:
        """Get date range of images in project"""
        images = self.get_images_by_project(project_id)
        if not images:
            return (None, None)

        dates = [img.date_taken for img in images if img.date_taken]
        if dates:
            return (min(dates), max(dates))
        return (None, None)
