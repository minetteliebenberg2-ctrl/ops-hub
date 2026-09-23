"""Migration 0058: deposit percentage becomes a business setting.

The split deposit / balance invoice pair was hardcoded at 65/35 by a
DEPOSIT_PERCENT constant in core/quote_document.py. The owner wants to
change that split without a code change, so it moves onto
business_settings as a single editable integer. Balance is always
100 - deposit, so only one number is stored. Valid range 1-99,
enforced in BusinessSettingsService.save_settings.
"""

from core.migrations.runner import Migration, migration_checksum


VERSION = 58
NAME = "deposit_percent_setting"

PAYLOAD = (
    "ALTER TABLE business_settings ADD COLUMN deposit_percent INTEGER NOT NULL DEFAULT 65",
)


def apply(connection):
    for sql in PAYLOAD:
        connection.execute(sql)


def verify(connection):
    cols = {row[1] for row in connection.execute("PRAGMA table_info(business_settings)")}
    assert "deposit_percent" in cols, "Column deposit_percent missing from business_settings"


MIGRATION = Migration(
    version=VERSION,
    name=NAME,
    checksum=migration_checksum("\n".join(PAYLOAD)),
    apply=apply,
    verify=verify,
)
