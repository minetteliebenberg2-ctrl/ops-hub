"""Backing service for the Social Media poster studio.

The studio itself is a web page. It is served over a loopback HTTP
server rather than opened as a file:// document for two reasons:

  1. A file:// page cannot list the Gallery, so it could never offer
     her own job photos.
  2. Images loaded from file:// taint the canvas, and a tainted canvas
     refuses toDataURL(), which would break the export - the one thing
     the tool exists to do.

Everything is bound to 127.0.0.1 on an ephemeral port and dies with the
app. Nothing is exposed off the machine.
"""

import base64
import json
import mimetypes
import os
import re
import subprocess
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

from core.app_paths import get_project_root, get_assets_dir


SIZES = {
    "square": (1080, 1080),
    "vertical": (1080, 1920),
    "landscape": (1200, 627),
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9 _-]+")


def studio_dir():
    """Where the static studio files live (inside assets/, so the spec bundles them)."""

    return get_assets_dir() / "social_studio"


def exports_root():
    """C:\\FC_Hub\\Social - one folder per month underneath."""

    return get_project_root() / "Social"


def month_folder(today=None):

    today = today or date.today()
    folder = exports_root() / today.strftime("%Y-%m")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def safe_filename(stem, extension=".png"):
    """Strip anything Windows would refuse, and never return an empty name."""

    stem = _SAFE_NAME.sub("", (stem or "").strip())[:60].strip()
    if not stem:
        stem = "poster"
    return stem + extension


def unique_path(folder, filename):
    """Never overwrite an export she has already made."""

    path = folder / filename
    if not path.exists():
        return path
    stem, extension = os.path.splitext(filename)
    counter = 2
    while True:
        candidate = folder / "{} ({}){}".format(stem, counter, extension)
        if not candidate.exists():
            return candidate
        counter += 1



def brand():
    """The name, phone, website and handle printed on a poster.

    Ops Hub carries no hardcoded trading identity - every client-facing
    document reads it from Settings -> Business Settings, and the poster
    studio is no different. Anything left blank is simply not drawn.
    """

    values = {"name": "", "phone": "", "site": "", "handle": ""}
    try:
        from core.business_settings_service import BusinessSettingsService
        settings = BusinessSettingsService().get_settings()
    except Exception:
        return values

    values["name"] = (settings.trading_name or settings.legal_name or "").strip()
    values["phone"] = (settings.phone or "").strip()
    site = (settings.website or "").strip()
    for prefix in ("https://", "http://", "www."):
        if site.lower().startswith(prefix):
            site = site[len(prefix):]
    values["site"] = site.rstrip("/")
    return values


# ----------------------------------------------------------


class GalleryIndex:
    """A flat list of every photo in the Gallery, across all customers.

    Built once per studio launch. Paths are kept server-side and only
    ever referenced by index, so the page never handles a real path.
    """

    def __init__(self, crm_service=None, image_service=None):

        self.crm_service = crm_service
        self.image_service = image_service
        self.entries = []

    def build(self):

        self.entries = []
        if self.crm_service is None or self.image_service is None:
            return self.entries

        try:
            customers = self.crm_service.list_customers()
        except Exception:
            return self.entries

        for customer in customers:
            try:
                images = self.image_service.list_for_customer(customer.id)
            except Exception:
                continue
            for image in images:
                try:
                    path = Path(self.image_service.image_path(image, customer))
                except Exception:
                    continue
                if not path.exists():
                    continue
                self.entries.append({
                    "index": len(self.entries),
                    "customer": getattr(customer, "name", ""),
                    "caption": getattr(image, "caption", "") or "",
                    "album": getattr(image, "album", "") or "",
                    "path": path,
                })
        return self.entries

    def as_json(self):

        return [
            {
                "index": e["index"],
                "customer": e["customer"],
                "caption": e["caption"],
                "album": e["album"],
            }
            for e in self.entries
        ]

    def path_for(self, index):

        if 0 <= index < len(self.entries):
            return self.entries[index]["path"]
        return None


# ----------------------------------------------------------


class StudioServer:
    """Serves the studio page and answers its handful of calls."""

    def __init__(self, gallery=None, root=None):

        self.gallery = gallery or GalleryIndex()
        self.root = Path(root) if root else studio_dir()
        self.httpd = None
        self.thread = None
        self.last_saved = None

    # --------------------------------------------------

    @property
    def port(self):

        return self.httpd.server_address[1] if self.httpd else None

    @property
    def url(self):

        return "http://127.0.0.1:{}/".format(self.port) if self.httpd else None

    # --------------------------------------------------

    def start(self):

        if self.httpd is not None:
            return self.url

        self.gallery.build()
        handler = _make_handler(self)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.url

    def stop(self):

        if self.httpd is None:
            return
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass
        self.httpd = None
        self.thread = None

    # --------------------------------------------------

    def save_png(self, data_url, stem):
        """Decode a data: URL from the page and file it under Social/YYYY-MM."""

        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        raw = base64.b64decode(data_url)
        path = unique_path(month_folder(), safe_filename(stem))
        path.write_bytes(raw)
        self.last_saved = path
        return path


def open_folder(path):
    """Show a folder (or a file's folder) in Explorer. Best effort."""

    path = Path(path)
    try:
        if path.is_file():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        return True
    except Exception:
        return False


# ----------------------------------------------------------


def _make_handler(server):

    logo_path = get_assets_dir() / "logo_placeholder.png"

    class Handler(BaseHTTPRequestHandler):

        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        # ----------------------------------------------

        def _send(self, status, body=b"", content_type="text/plain; charset=utf-8"):

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _send_json(self, payload, status=200):

            self._send(status, json.dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _send_file(self, path):

            path = Path(path)
            if not path.exists() or not path.is_file():
                self._send(404, b"not found")
                return
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self._send(200, path.read_bytes(), content_type)

        # ----------------------------------------------

        def do_GET(self):

            route = unquote(urlparse(self.path).path)

            if route in ("/", "/index.html"):
                self._send_file(server.root / "poster_studio.html")
                return

            if route == "/logo.png":
                self._send_file(logo_path)
                return

            if route == "/api/brand":
                self._send_json(brand())
                return

            if route == "/api/gallery":
                self._send_json(server.gallery.as_json())
                return

            if route.startswith("/photo/"):
                try:
                    index = int(route.rsplit("/", 1)[1])
                except ValueError:
                    self._send(400, b"bad index")
                    return
                path = server.gallery.path_for(index)
                if path is None:
                    self._send(404, b"no such photo")
                    return
                self._send_file(path)
                return

            if route.startswith("/static/"):
                name = route[len("/static/"):]
                # Refuse anything that tries to climb out of the studio folder.
                if "/" in name or "\\" in name or name.startswith("."):
                    self._send(403, b"forbidden")
                    return
                self._send_file(server.root / name)
                return

            self._send(404, b"not found")

        def do_HEAD(self):

            self.do_GET()

        # ----------------------------------------------

        def do_POST(self):

            route = unquote(urlparse(self.path).path)

            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            raw = self.rfile.read(length) if length else b"{}"

            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                self._send_json({"ok": False, "error": "bad request"}, 400)
                return

            if route == "/api/save":
                try:
                    path = server.save_png(payload.get("png", ""), payload.get("name", ""))
                except Exception as error:
                    self._send_json({"ok": False, "error": str(error)}, 500)
                    return
                self._send_json({"ok": True, "path": str(path), "folder": str(path.parent)})
                return

            if route == "/api/open-folder":
                target = payload.get("path") or str(month_folder())
                self._send_json({"ok": open_folder(target)})
                return

            self._send_json({"ok": False, "error": "unknown"}, 404)

    return Handler
