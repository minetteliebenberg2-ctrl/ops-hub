"""Regression tests for the first-run database bootstrap in launcher.py."""

import launcher
from core.database import Database


def test_bootstrap_creates_schema_when_database_file_is_missing(tmp_path, monkeypatch):

    db_path = tmp_path / "fc_hub.db"
    monkeypatch.setattr(launcher, "DATABASE_PATH", db_path)
    monkeypatch.setattr(launcher, "database", Database(db_path))

    assert not db_path.exists()

    launcher.bootstrap_database()

    assert db_path.exists()
    with launcher.database.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "customers" in tables
    assert "communication_candidates" in tables


def test_bootstrap_does_not_touch_an_existing_database_file(tmp_path, monkeypatch):

    db_path = tmp_path / "fc_hub.db"
    db_path.write_bytes(b"")

    monkeypatch.setattr(launcher, "DATABASE_PATH", db_path)
    monkeypatch.setattr(launcher, "database", Database(db_path))

    calls = []
    monkeypatch.setattr(
        launcher.MigrationRunner,
        "migrate",
        lambda _self, **kwargs: calls.append(kwargs),
    )

    launcher.bootstrap_database()

    assert calls == []
