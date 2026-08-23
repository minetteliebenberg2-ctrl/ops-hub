# ==========================================================
# FC Hub - Application Paths
# ----------------------------------------------------------
# Purpose:
# Resolve the persistent application root (database, backups,
# exports, logs). Source-tree code and read-only bundled
# assets keep resolving paths via their own __file__; this is
# only for data that must survive between separate app runs.
#
# A PyInstaller --onefile build extracts to a fresh temporary
# directory (sys._MEIPASS) every launch and deletes it on
# exit, so __file__-based resolution there would silently
# reset the database on every run. When frozen, the root is
# the folder containing the executable instead.
# ==========================================================

from pathlib import Path
import sys


def get_project_root():

    if getattr(sys, "frozen", False):

        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def get_assets_dir():
    """Read-only bundled assets: logo, fonts, application icon.

    These are NOT persistent data, so they must not resolve through
    get_project_root(). In a --onefile build PyInstaller extracts the
    bundle to sys._MEIPASS while get_project_root() deliberately points at
    the executable's own folder (so the database survives between runs) -
    resolving assets there finds nothing.

    That failed silently and cosmetically, which is why it went unnoticed:
    a frozen build rendered PDFs with no logo and fell back from Lato to
    Helvetica rather than raising. Falls back to the project root so
    running from source is unchanged.
    """

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        bundled = Path(bundle_dir) / "assets"
        if bundled.is_dir():
            return bundled

    return get_project_root() / "assets"
