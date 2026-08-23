# ==========================================================
# FC Hub - Site Image Repository
# ----------------------------------------------------------
# Purpose:
# Persistence for site_images - mirrors SiteVisitRepository's pattern
# (core/site_visit_repository.py) exactly.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from datetime import datetime

from core.database import database
from core.site_image import SiteImage


class SiteImageRepository:

    def __init__(self, db=None):

        self.db = db or database
        self.db.initialize()

    # --------------------------------------------------

    def save(self, image):

        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO site_images (
                    id, customer_id, site_id, site_visit_id, stored_filename,
                    original_filename, caption, width, height, taken_at,
                    created_at, updated_at, created_by, tags, album,
                    file_hash, file_size
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    site_id = excluded.site_id,
                    site_visit_id = excluded.site_visit_id,
                    caption = excluded.caption,
                    tags = excluded.tags,
                    album = excluded.album,
                    updated_at = excluded.updated_at
                """,
                (
                    image.id,
                    image.customer_id,
                    image.site_id or None,
                    image.site_visit_id or None,
                    image.stored_filename,
                    image.original_filename,
                    image.caption,
                    image.width,
                    image.height,
                    image.taken_at,
                    image.created_at,
                    image.updated_at,
                    image.created_by,
                    image.tags,
                    image.album,
                    image.file_hash,
                    image.file_size,
                ),
            )

        return image

    # --------------------------------------------------

    def get(self, image_id):

        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM site_images WHERE id = ?", (image_id,),
            ).fetchone()

        return self._to_image(row) if row else None

    # --------------------------------------------------

    def list_for_customer(self, customer_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM site_images
                WHERE customer_id = ?
                ORDER BY created_at DESC
                """,
                (customer_id,),
            ).fetchall()

        return [self._to_image(row) for row in rows]

    # --------------------------------------------------

    def list_for_visit(self, site_visit_id):

        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM site_images
                WHERE site_visit_id = ?
                ORDER BY created_at DESC
                """,
                (site_visit_id,),
            ).fetchall()

        return [self._to_image(row) for row in rows]

    # --------------------------------------------------

    def archive(self, image_id, actor, reason):

        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE site_images
                SET archived_at = ?, archived_by = ?, archive_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (self._timestamp(), actor, reason, self._timestamp(), image_id),
            )

    # --------------------------------------------------

    def _timestamp(self):

        return datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def _to_image(self, row):

        return SiteImage(
            id=row["id"],
            customer_id=row["customer_id"],
            site_id=row["site_id"] or "",
            site_visit_id=row["site_visit_id"] or "",
            stored_filename=row["stored_filename"],
            original_filename=row["original_filename"],
            caption=row["caption"],
            width=row["width"],
            height=row["height"],
            taken_at=row["taken_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"] or "",
            archived_at=row["archived_at"] or "",
            archived_by=row["archived_by"] or "",
            archive_reason=row["archive_reason"] or "",
            tags=row["tags"] or "",
            album=row["album"] or "",
            file_hash=row["file_hash"] or "" if "file_hash" in row.keys() else "",
            file_size=row["file_size"] or 0 if "file_size" in row.keys() else 0,
        )
