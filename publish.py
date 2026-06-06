#!/usr/bin/env python3
"""
publish.py — Calibre to PHP library publisher

Usage:
    python publish.py config.json

Reads a config file, queries Calibre via calibredb, copies EPUB/PDF files,
extracts plain text for full-text search, generates books.json, and copies
the PHP template files to the output directory.
"""

import json
import os
import os.path
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []

    def handle_data(self, data):
        self._chunks.append(data)

    def get_text(self):
        return " ".join(self._chunks)


def strip_html(html: str) -> str:
    p = _StripHTML()
    p.feed(html)
    return re.sub(r"\s+", " ", p.get_text()).strip()


def extract_epub_text(epub_path: Path, max_chars: int = 500_000) -> str:
    """Extract plain text from an EPUB file (best-effort)."""
    chunks = []
    try:
        with zipfile.ZipFile(epub_path) as zf:
            # Sort by name so chapters come out in rough order
            names = sorted(n for n in zf.namelist()
                           if n.endswith((".html", ".htm", ".xhtml")))
            for name in names:
                try:
                    html = zf.read(name).decode("utf-8", errors="replace")
                    chunks.append(strip_html(html))
                except Exception:
                    pass
                if sum(len(c) for c in chunks) >= max_chars:
                    break
    except Exception:
        pass
    return " ".join(chunks)[:max_chars]


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


# ---------------------------------------------------------------------------
# Calibre helpers
# ---------------------------------------------------------------------------

CALIBREDB_FIELDS = (
    "id,title,authors,series,series_index,tags,publisher,pubdate,timestamp,"
    "cover,formats,comments"
)


def calibredb_list(library_path: str, saved_search: str) -> list[dict]:
    """Return metadata list from calibredb for the given saved search."""
    cmd = [
        "calibredb", "list",
        "--library-path", library_path,
        "--search", f"search:{saved_search}",
        "--fields", CALIBREDB_FIELDS,
        "--for-machine",
    ]
    result = run(cmd, check=False)
    if result.returncode != 0:
        print(f"[ERROR] calibredb list failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def calibredb_export(library_path: str, book_id: int, dest_dir: Path,
                     fmt: str) -> Path | None:
    """Export a single format from a book; return the output path or None."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "calibredb", "export",
        "--library-path", library_path,
        "--dont-save-cover",
        "--dont-write-opf",
        "--single-dir",
        "--to-dir", str(dest_dir),
        "--formats", fmt,
        str(book_id),
    ]
    result = run(cmd, check=False)
    if result.returncode != 0:
        return None
    # calibredb names the file after the book title; find it
    matches = list(dest_dir.glob(f"*.{fmt.lower()}"))
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def normalise_book(raw: dict) -> dict:
    """Normalise a raw calibredb record into our schema."""
    authors = raw.get("authors") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split("&")]

    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]

    # pubdate / timestamp arrive as ISO strings or None
    def clean_date(val):
        if not val:
            return None
        return val[:10]  # keep YYYY-MM-DD

    # formats may be:
    #   - a list of format names: ["EPUB", "PDF"]
    #   - a list of full paths:   ["/path/book.epub", "/path/book.pdf"]
    #   - a comma-separated string of either
    formats = raw.get("formats") or []
    if isinstance(formats, str):
        formats = [f.strip() for f in formats.split(",")]
    # Normalise to uppercase extensions regardless of whether we got names or paths
    fmt_exts = {os.path.splitext(f)[1].lstrip(".").upper() or f.upper() for f in formats}

    publisher = raw.get("publisher") or ""

    comments = raw.get("comments") or ""
    if comments:
        comments = strip_html(comments)

    return {
        "id": raw["id"],
        "title": raw.get("title", ""),
        "authors": authors,
        "series": raw.get("series") or "",
        "series_index": raw.get("series_index") or 0,
        "tags": tags,
        "publisher": publisher,
        "pubdate": clean_date(raw.get("pubdate")),
        "timestamp": clean_date(raw.get("timestamp")),
        "cover_src": raw.get("cover") or "",   # absolute path on disk
        "has_epub": "EPUB" in fmt_exts,
        "has_pdf": "PDF" in fmt_exts,
        "comments": comments,
    }


def publish(config_path: str) -> None:
    with open(config_path) as f:
        cfg = json.load(f)

    library_path = cfg["library_path"]
    saved_search = cfg["saved_search"]
    output_dir = Path(cfg["output_dir"])
    site_title = cfg.get("site_title", "My Library")
    books_per_page_recent = int(cfg.get("recent_count", 20))
    extract_text = cfg.get("extract_text", True)
    max_text_chars = int(cfg.get("max_text_chars", 500_000))

    print(f"[publish] Library : {library_path}")
    print(f"[publish] Search  : {saved_search}")
    print(f"[publish] Output  : {output_dir}")

    # Directories
    files_dir = output_dir / "files"
    covers_dir = output_dir / "covers"
    text_dir = output_dir / "text"
    assets_dir = output_dir / "assets"

    for d in [output_dir, files_dir, covers_dir, text_dir, assets_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ---- Fetch metadata ----
    print("[publish] Querying calibredb…")
    raw_books = calibredb_list(library_path, saved_search)
    print(f"[publish] Found {len(raw_books)} books.")

    books = []
    for raw in raw_books:
        book = normalise_book(raw)
        bid = book["id"]
        book_files_dir = files_dir / str(bid)
        book_files_dir.mkdir(parents=True, exist_ok=True)

        # ---- Copy cover ----
        cover_src = book.pop("cover_src")
        cover_web = f"covers/{bid}.jpg"
        if cover_src and Path(cover_src).is_file():
            shutil.copy2(cover_src, covers_dir / f"{bid}.jpg")
            book["cover"] = cover_web
        else:
            book["cover"] = ""

        # ---- Export EPUB ----
        epub_web = ""
        if book["has_epub"]:
            epub_tmp = book_files_dir / "_epub_tmp"
            epub_tmp.mkdir(exist_ok=True)
            exported = calibredb_export(library_path, bid, epub_tmp, "epub")
            if exported:
                dest = book_files_dir / "book.epub"
                shutil.move(str(exported), dest)
                shutil.rmtree(epub_tmp, ignore_errors=True)
                epub_web = f"files/{bid}/book.epub"
                # Extract text
                if extract_text:
                    txt = extract_epub_text(dest, max_text_chars)
                    if txt:
                        (text_dir / f"{bid}.txt").write_text(txt, encoding="utf-8")
            else:
                book["has_epub"] = False

        book["epub"] = epub_web

        # ---- Export PDF ----
        pdf_web = ""
        if book["has_pdf"]:
            pdf_tmp = book_files_dir / "_pdf_tmp"
            pdf_tmp.mkdir(exist_ok=True)
            exported = calibredb_export(library_path, bid, pdf_tmp, "pdf")
            if exported:
                dest = book_files_dir / "book.pdf"
                shutil.move(str(exported), dest)
                shutil.rmtree(pdf_tmp, ignore_errors=True)
                pdf_web = f"files/{bid}/book.pdf"
            else:
                book["has_pdf"] = False

        book["pdf"] = pdf_web

        books.append(book)
        title_short = book["title"][:50]
        print(f"  [{bid}] {title_short}")

    # ---- Write books.json ----
    books_json = output_dir / "books.json"
    with open(books_json, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)
    print(f"[publish] Wrote {books_json}")

    # ---- Write site config ----
    site_cfg = {
        "title": site_title,
        "recent_count": books_per_page_recent,
        "generated": datetime.now().astimezone().strftime("%d %B %Y %H:%M"),
        "book_count": len(books),
    }
    with open(output_dir / "site.json", "w") as f:
        json.dump(site_cfg, f, indent=2)

    # ---- Copy PHP template files ----
    template_dir = Path(__file__).parent / "www"
    if not template_dir.is_dir():
        print("[WARN] www/ template directory not found — skipping PHP copy.")
    else:
        for src in template_dir.rglob("*"):
            rel = src.relative_to(template_dir)
            dst = output_dir / rel
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                shutil.copy2(src, dst)
        print(f"[publish] Copied PHP templates from {template_dir}")

    print(f"\n[publish] Done. {len(books)} books published to {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} config.json", file=sys.stderr)
        sys.exit(1)
    publish(sys.argv[1])
