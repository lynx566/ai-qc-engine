"""Disposable QA page rendering stays scoped to one TaskRun."""

from __future__ import annotations

# ruff: noqa: E402

from importlib import import_module
from pathlib import Path
import sys

import pymupdf
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def render_pages():
    return import_module("scripts.tools.qc_report_pdf_qa").render_preview_pages


def make_pdf(path, pages=1):
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=72, height=72)
    doc.save(path)
    doc.close()


def test_qa_images_use_task_directory_stable_names_and_180_dpi(render_pages, tmp_path):
    pdf = tmp_path / "preview.pdf"
    make_pdf(pdf, 2)
    paths = render_pages("task_run_a", pdf, workspace_root=tmp_path)
    assert paths == (
        tmp_path / ".tmp/pdfs/qc_report/task_run_a/page-01.png",
        tmp_path / ".tmp/pdfs/qc_report/task_run_a/page-02.png",
    )
    for path in paths:
        pix = pymupdf.Pixmap(str(path))
        assert (pix.width, pix.height) == (180, 180)
        assert (pix.xres, pix.yres) == (180, 180)


def test_qa_rerender_removes_only_target_task_old_pages(render_pages, tmp_path):
    pdf = tmp_path / "preview.pdf"
    make_pdf(pdf, 3)
    previous = render_pages("task_run_a", pdf, workspace_root=tmp_path)
    other = tmp_path / ".tmp/pdfs/qc_report/task_run_b"
    other.mkdir()
    (other / "page-01.png").write_bytes(b"other task")
    keep = previous[0].parent / "notes.txt"
    keep.write_text("keep")
    fake = previous[0].parent / "page-not-a-number.png"
    fake.write_bytes(b"keep too")
    pdf.unlink()
    make_pdf(pdf, 1)
    current = render_pages("task_run_a", pdf, workspace_root=tmp_path)
    assert len(current) == 1
    assert not previous[1].exists() and not previous[2].exists()
    assert (other / "page-01.png").read_bytes() == b"other task"
    assert keep.read_text() == "keep" and fake.exists()


def test_qa_bad_pdf_preserves_old_pages(render_pages, tmp_path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a PDF")
    folder = tmp_path / ".tmp/pdfs/qc_report/task_run_a"
    folder.mkdir(parents=True)
    page = folder / "page-01.png"
    page.write_bytes(b"previous QA")
    with pytest.raises(Exception):
        render_pages("task_run_a", pdf, workspace_root=tmp_path)
    assert page.read_bytes() == b"previous QA"


@pytest.mark.parametrize("task_id", ["..", "../outside", "a/b", "a\\b", "C:escape"])
def test_qa_rejects_unsafe_task_path_components(render_pages, task_id, tmp_path):
    with pytest.raises(ValueError):
        render_pages(task_id, tmp_path / "absent.pdf", workspace_root=tmp_path)


def test_qa_rejects_redirected_target_before_cleanup(
    render_pages, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = tmp_path / "preview.pdf"
    make_pdf(pdf)
    task_dir = tmp_path / ".tmp/pdfs/qc_report/task_run_a"
    task_dir.mkdir(parents=True)
    page = task_dir / "page-01.png"
    page.write_bytes(b"keep")
    canonical_page = page.resolve()
    outside_resolved = (tmp_path / "outside_redirect" / "page-01.png").resolve()

    original_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        resolved = original_resolve(self, strict=strict)
        if resolved == canonical_page:
            return outside_resolved
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(ValueError, match="redirect"):
        render_pages("task_run_a", pdf, workspace_root=tmp_path)
    assert page.read_bytes() == b"keep"
