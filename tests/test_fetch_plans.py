"""Offline tests for the study-plan downloader (no network: urlopen is replaced)."""
import json
from pathlib import Path

import pytest

from scripts import fetch_gju_plans as fp

MANIFEST = Path(__file__).parent.parent / "datasets" / "gju" / "study_plan_sources.json"


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_is_consistent(manifest):
    ids = [p["id"] for p in manifest["plans"]]
    assert len(ids) == len(set(ids))
    for plan in manifest["plans"]:
        assert plan["path"].startswith(fp.ALLOWED_PREFIX) and " " not in plan["path"]
        assert plan["kind"] in ("regular", "dual") and plan["status"] in ("todo", "loaded")
        assert Path(plan["path"]).suffix.lower() in (".pdf", ".docx")
    assert {p["school"] for p in manifest["plans"]} == {"SC", "SATS", "SABE", "SSSE", "BS", "SAHSS", "SAMS", "SN"}
    assert manifest["gaps"]  # known gaps are written down, not hidden


def test_content_check_and_url_fallback():
    assert fp.looks_right(b"%PDF-1.7 ...", ".pdf") and not fp.looks_right(b"<html>404", ".pdf")
    assert fp.looks_right(b"PK\x03\x04", ".docx")
    assert fp.candidates("/sites/default/files/a%20%26amp%3B%20b/x.pdf") == [
        "/sites/default/files/a%20%26amp%3B%20b/x.pdf", "/sites/default/files/a%20%26%20b/x.pdf"]
    assert fp.candidates("/sites/default/files/x.pdf") == ["/sites/default/files/x.pdf"]


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_download_tries_plain_ampersand_and_rejects_html(monkeypatch):
    monkeypatch.setattr(fp.time, "sleep", lambda s: None)
    asked = []

    def fake_urlopen(request, timeout):
        asked.append(request.full_url)
        if "%26amp%3B" in request.full_url:
            return FakeResponse(b"<html>not found</html>")
        return FakeResponse(b"%PDF-1.4 real")

    monkeypatch.setattr(fp.urllib.request, "urlopen", fake_urlopen)
    body, message = fp.download("/sites/default/files/A%20%26amp%3B%20B/p.pdf", ".pdf")
    assert body == b"%PDF-1.4 real" and message == "ok" and len(asked) == 2

    monkeypatch.setattr(fp.urllib.request, "urlopen", lambda r, timeout: FakeResponse(b"<html>"))
    body, message = fp.download("/sites/default/files/p.pdf", ".pdf")
    assert body is None and "not a real PDF" in message


def test_paths_outside_the_files_folder_are_refused():
    assert fp.download("/admin/secret.pdf", ".pdf") == (None, "refused: path outside /sites/default/files/")


def test_main_skips_loaded_and_existing_files_and_writes_a_zip(monkeypatch, tmp_path):
    monkeypatch.setattr(fp, "OUT", tmp_path / "plans")
    monkeypatch.setattr(fp.time, "sleep", lambda s: None)
    calls = []

    def fake_download(path, suffix):
        calls.append(path)
        return (b"%PDF-1" if suffix == ".pdf" else b"PK"), "ok"

    monkeypatch.setattr(fp, "download", fake_download)
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "ce_2023-2024.pdf").write_bytes(b"%PDF-already")
    assert fp.main(make_zip=True) == 0
    todo = [p for p in json.loads(MANIFEST.read_text(encoding="utf-8"))["plans"] if p["status"] != "loaded"]
    assert len(calls) == len(todo) - 1  # the file we already had is not requested again
    assert not any("study_plan_all_tracks_2023-2024_updated" in c for c in calls)  # CS is already loaded
    assert (tmp_path / "plans.zip").exists() and (tmp_path / "plans" / "_report.txt").exists()
