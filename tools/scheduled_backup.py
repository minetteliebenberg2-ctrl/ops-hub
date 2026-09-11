"""Daily scheduled backup for Ops Hub.

Run by Windows Task Scheduler at 18:00 SAST every day.
Keeps the last 7 days of backups; older ones are deleted automatically.
Logs result to logs\\scheduled_backup.log inside the Ops Hub folder.
"""

import shutil
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.app_paths import get_project_root
from modules.backup.services import BackupService

ROOT = get_project_root()
LOG_FILE = ROOT / "logs" / "scheduled_backup.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger(__name__)

RETENTION_DAYS = 7


def main():
    log.info("Scheduled backup started")
    service = BackupService(retention_days=RETENTION_DAYS)

    # Create today's backup
    result = service.create_backup()
    if result.success:
        log.info("Backup succeeded: %s", result.backup_path)
    else:
        log.error("Backup failed: %s", result.message)
        sys.exit(1)

    # Delete backups older than RETENTION_DAYS
    candidates = service.cleanup_candidates()
    for old in candidates:
        try:
            shutil.rmtree(old.path)
            log.info("Deleted old backup: %s", old.path)
        except Exception as exc:
            log.warning("Could not delete old backup %s: %s", old.path, exc)

    log.info("Done. Kept backups from the last %d days.", RETENTION_DAYS)


if __name__ == "__main__":
    main()
