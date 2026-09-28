"""Tests for the poster studio's file handling and gallery index."""

from datetime import date

import pytest

from core import social_studio as ss


class _Image:
    def __init__(self, caption="", album=""):
        self.caption = caption
        self.album = album


class _Customer:
    def __init__(self, cid, name):
        self.id = cid
        self.name = name


class _CRM:
    def __init__(self, customers):
        self._customers = customers

    def list_customers(self):
        return self._customers


class _Images:
    def __init__(self, mapping):
        self._mapping = mapping

    def list_for_customer(self, customer_id):
        return [image for image, _ in self._mapping.get(customer_id, [])]

    def image_path(self, image, customer):
        for candidate, path in self._mapping[customer.id]:
            if candidate is image:
                return path
        raise KeyError


# ----------------------------------------------------------- names


@pytest.mark.parametrize("raw, expected", [
    ('Bad/Name: "test"', "BadName test.png"),
    ("", "poster.png"),
    ("   ", "poster.png"),
    ("///", "poster.png"),
    ("Refit GHH 2026", "Refit GHH 2026.png"),
])
def test_safe_filename_strips_what_windows_refuses(raw, expected):
    assert ss.safe_filename(raw) == expected


def test_unique_path_never_overwrites(tmp_path):
    first = ss.unique_path(tmp_path, "poster.png")
    first.write_bytes(b"x")
    second = ss.unique_path(tmp_path, "poster.png")
    second.write_bytes(b"x")
    third = ss.unique_path(tmp_path, "poster.png")

    assert first.name == "poster.png"
    assert second.name == "poster (2).png"
    assert third.name == "poster (3).png"


def test_month_folder_is_named_for_the_month(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "exports_root", lambda: tmp_path / "Social")
    folder = ss.month_folder(date(2026, 9, 28))

    assert folder.name == "2026-09"
    assert folder.is_dir()


# ----------------------------------------------------------- gallery


def test_gallery_index_skips_missing_files(tmp_path):
    real = tmp_path / "real.jpg"
    real.write_bytes(b"jpeg")
    gone = tmp_path / "gone.jpg"

    here = _Image("Finished", "Boksburg")
    missing = _Image("Lost", "")
    customer = _Customer("c1", "GHH Mining Machines")

    index = ss.GalleryIndex(
        _CRM([customer]),
        _Images({"c1": [(here, real), (missing, gone)]}),
    )
    index.build()

    assert len(index.entries) == 1
    assert index.path_for(0) == real
    assert index.path_for(1) is None


def test_gallery_json_never_leaks_a_path(tmp_path):
    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"jpeg")
    customer = _Customer("c1", "Cavaleros")

    index = ss.GalleryIndex(_CRM([customer]), _Images({"c1": [(_Image("Block A"), photo)]}))
    index.build()
    payload = index.as_json()

    assert payload == [{"index": 0, "customer": "Cavaleros",
                        "caption": "Block A", "album": ""}]
    assert "path" not in payload[0]


def test_gallery_without_services_is_simply_empty():
    index = ss.GalleryIndex()
    assert index.build() == []
    assert index.as_json() == []


# ----------------------------------------------------------- saving


def test_save_png_decodes_and_files_by_month(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "exports_root", lambda: tmp_path / "Social")
    server = ss.StudioServer()

    path = server.save_png("data:image/png;base64,aGVsbG8=", "Refit GHH")

    assert path.read_bytes() == b"hello"
    assert path.name == "Refit GHH.png"
    assert path.parent.name == date.today().strftime("%Y-%m")
    assert server.last_saved == path


def test_save_png_accepts_a_bare_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "exports_root", lambda: tmp_path / "Social")
    server = ss.StudioServer()

    assert server.save_png("aGVsbG8=", "x").read_bytes() == b"hello"
