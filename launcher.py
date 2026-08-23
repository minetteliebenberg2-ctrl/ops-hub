"""
---------------------------------------------------------
FC Hub
launcher.py

Main application launcher.

Author: Minette & James
Version: 1.0.0
---------------------------------------------------------
"""

import sys

import customtkinter as ctk

from core.app_paths import get_assets_dir
from core.database import DATABASE_PATH, database
from core.font_loader import register_bundled_fonts
from core.migrations.runner import MigrationRunner
from gui import window_focus
from gui.main_window import MainWindow
from framework.module_manager import module_manager


ICON_PATH = get_assets_dir() / "fc_hub.ico"


def apply_window_icon(window):
    """Put the FC mark on the window and taskbar button.

    Only affects running from source - the frozen .exe carries the icon
    embedded by PyInstaller (see `icon=` in "FC Hub.spec"). Never fatal: a
    missing or unreadable icon must not stop the app launching.
    """

    if not ICON_PATH.is_file():
        return
    try:
        window.iconbitmap(str(ICON_PATH))
    except Exception:
        return

    if sys.platform == "win32":
        # Without an explicit AppUserModelID, Windows groups the window under
        # python.exe and shows Python's icon in the taskbar regardless of
        # iconbitmap.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "FacilitiesCo.FCHub"
            )
        except Exception:
            pass


def bootstrap_database():
    """Create the initial schema on a genuinely fresh install.

    database.initialize() deliberately never auto-migrates the production
    database (DEVELOPMENT_SPECIFICATION.md section 21) so an existing
    database is never modified silently. That guard should not apply to a
    database file that has never existed - there is nothing to protect -
    so first-run schema creation is authorised explicitly, once, here.
    """

    if DATABASE_PATH.exists():

        return

    MigrationRunner(database).migrate(
        allow_production=True,
        backup_verified=True,
    )


def main():

    ctk.set_appearance_mode("light")

    from gui.ctk_theme import apply_ctk_theme
    apply_ctk_theme()

    register_bundled_fonts()

    window_focus.install()

    bootstrap_database()

    report = module_manager.discover()

    if report.has_failures:
        print(
            "FC Hub startup warning: "
            f"{len(report.failures)} module discovery failure(s); "
            f"{len(report.registered_module_ids)} module(s) registered."
        )

    app = ctk.CTk()
    apply_window_icon(app)

    MainWindow(app, module_manager)

    app.mainloop()


if __name__ == "__main__":

    main()
