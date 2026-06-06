#!/usr/bin/env python3
"""
publish.py — Calibre to PHP library publisher

Usage:
    python publish.py config.json

Reads a config file, queries Calibre via calibredb, copies EPUB/PDF files,
extracts plain text for full-text search, generates books.json, and copies
the PHP template files to the output directory.
"""

import ftplib
import json
import os
import os.path
import re
import sqlite3
from urllib.parse import urlparse
import shutil
import subprocess
import sys
import uuid as uuid_mod
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

def load_calibre_data(library_path: str, book_ids: list) -> tuple[dict, dict]:
    """
    Returns:
      book_data  — {book_id: {series_id, author_ids, publisher_id}}
      id_to_name — {series_by_id, authors_by_id, publishers_by_id}
    """
    db_path = os.path.join(library_path, "metadata.db")
    book_data  = {}
    id_to_name = {"series_by_id": {}, "authors_by_id": {}, "publishers_by_id": {}}

    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # Global id→name maps for PHP lookups
        for table, key in [("series", "series_by_id"),
                            ("authors", "authors_by_id"),
                            ("publishers", "publishers_by_id")]:
            for row in cur.execute(f"SELECT id, name FROM {table}"):
                id_to_name[key][str(row[0])] = row[1]

        # Per-book IDs via link tables (no name matching needed)
        for bid in book_ids:
            row = cur.execute(
                "SELECT series FROM books_series_link WHERE book=?", (bid,)
            ).fetchone()
            series_id = row[0] if row else 0

            author_rows = cur.execute(
                "SELECT author FROM books_authors_link WHERE book=? ORDER BY id", (bid,)
            ).fetchall()
            author_ids = [r[0] for r in author_rows]

            row = cur.execute(
                "SELECT publisher FROM books_publishers_link WHERE book=?", (bid,)
            ).fetchone()
            publisher_id = row[0] if row else 0

            book_data[bid] = {
                "series_id":    series_id,
                "author_ids":   author_ids,
                "publisher_id": publisher_id,
            }

        con.close()
    except Exception as e:
        print(f"[WARN] Could not read metadata.db: {e}", file=sys.stderr)

    return book_data, id_to_name


CALIBREDB_FIELDS = (
    "id,title,authors,series,series_index,tags,publisher,pubdate,timestamp,"
    "cover,formats,comments"
)


def calibredb_list(library_path: str, saved_search: str) -> list[dict]:
    """Return metadata list from calibredb for the given saved search."""
    cmd = [
        "calibredb", "list",
        "--library-path", library_path,
        "--fields", CALIBREDB_FIELDS,
        "--for-machine",
    ]
    if saved_search:
        cmd += ["--search", f"search:{saved_search}"]
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

    # ---- Load cache ----
    cache_path = output_dir / "cache.json"
    cache = {}
    if cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    # ---- Fetch metadata ---- (early, so we have book IDs for SQLite lookup)
    print("[publish] Querying calibredb…")
    raw_books = calibredb_list(library_path, saved_search)
    raw_books.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    print(f"[publish] Found {len(raw_books)} books.")

    # ---- Load Calibre IDs from metadata.db ----
    all_ids = [r["id"] for r in raw_books]
    calibre_book_data, id_to_name = load_calibre_data(library_path, all_ids)
    print(f"[publish] Loaded IDs for {len(calibre_book_data)} books from metadata.db")



    books = []
    new_cache = {}
    skipped = 0

    for raw in raw_books:
        book = normalise_book(raw)
        bid = book["id"]
        bid_str = str(bid)
        book_files_dir = files_dir / bid_str

        # ---- Cache check ----
        # A book is unchanged if: metadata matches the cache AND all expected
        # output files exist on disk.
        cached = cache.get(bid_str)
        if cached:
            meta_unchanged = (
                cached.get("timestamp") == book["timestamp"] and
                cached.get("title")     == book["title"]     and
                cached.get("authors")   == book["authors"]   and
                cached.get("has_epub")  == book["has_epub"]  and
                cached.get("has_pdf")   == book["has_pdf"]
            )
            epub_ok = (not book["has_epub"]) or (book_files_dir / "book.epub").is_file()
            pdf_ok  = (not book["has_pdf"])  or (book_files_dir / "book.pdf").is_file()
            cover_ok = (covers_dir / f"{bid}.jpg").is_file()

            if meta_unchanged and epub_ok and pdf_ok and cover_ok:
                # Always refresh IDs from metadata.db (cache may predate ID fix)
                cb = calibre_book_data.get(bid, {})
                cached["series_id"]    = cb.get("series_id",    0)
                cached["publisher_id"] = cb.get("publisher_id", 0)
                cached["author_ids"]   = cb.get("author_ids",   [])
                books.append(cached)
                new_cache[bid_str] = cached
                skipped += 1
                continue

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

        # ---- Add Calibre IDs (from link tables, not name matching) ----
        cb = calibre_book_data.get(bid, {})
        book["series_id"]    = cb.get("series_id",    0)
        book["publisher_id"] = cb.get("publisher_id", 0)
        book["author_ids"]   = cb.get("author_ids",   [])

        books.append(book)
        new_cache[bid_str] = book
        title_short = book["title"][:50]
        print(f"  [{bid}] {title_short}")

    if skipped:
        print(f"[publish] Skipped {skipped} unchanged books.")

    # ---- Save cache ----
    cache_path.write_text(json.dumps(new_cache, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    # ---- Write books.json ----
    books_json = output_dir / "books.json"
    with open(books_json, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)
    print(f"[publish] Wrote {books_json}")

    # ---- Write feed.xml ----
    if cfg.get("site_url"):
        generate_feed(books, cfg, output_dir)

    # ---- Write site config ----
    site_url   = cfg.get("site_url", "")
    base_path  = (urlparse(site_url).path.rstrip("/") + "/") if site_url else "/"

    site_cfg = {
        "title": site_title,
        "recent_count": books_per_page_recent,
        "generated": datetime.now().astimezone().strftime("%d %B %Y %H:%M"),
        "book_count": len(books),
        "base_path": base_path,
        "main_site_url":  cfg.get("main_site_url", ""),
        "main_site_name": cfg.get("main_site_name", ""),
        "series_by_id":     id_to_name["series_by_id"],
        "authors_by_id":    id_to_name["authors_by_id"],
        "publishers_by_id": id_to_name["publishers_by_id"],
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

    # ---- Write theme.css ----
    theme = cfg.get("theme", {})
    accent      = theme.get("accent",      "#4a7c59")
    accent_dark = theme.get("accent_dark", "#335a40")
    theme_css = f""":root {{
  --accent:    {accent};
  --accent-dk: {accent_dark};
}}
"""
    theme_path = output_dir / "assets" / "theme.css"
    theme_path.parent.mkdir(parents=True, exist_ok=True)
    theme_path.write_text(theme_css)
    print(f"[publish] Wrote theme.css (accent={accent})")

    print(f"\n[publish] Done. {len(books)} books published to {output_dir}")

    # ---- FTP deploy (optional) ----
    if cfg.get("ftp_host"):
        deploy(output_dir, cfg)


# ---------------------------------------------------------------------------
# Atom feed
# ---------------------------------------------------------------------------

def xml_esc(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# Stable UUID namespace — same book ID always produces the same UUID
_UUID_NS = uuid_mod.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def generate_feed(books: list, cfg: dict, output_dir: Path) -> None:
    site_url    = cfg["site_url"].rstrip("/")
    title       = cfg.get("site_title", "Library")
    subtitle    = cfg.get("feed_subtitle", "")
    now_iso     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sorted_books = sorted(books,
                          key=lambda b: b.get("timestamp") or "",
                          reverse=True)

    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">',
        f"  <title>{xml_esc(title)}</title>",
    ]
    if subtitle:
        lines.append(f"  <subtitle>{xml_esc(subtitle)}</subtitle>")
    lines += [
        f'  <link href="{site_url}" />',
        f"  <id>{site_url}</id>",
        f"  <updated>{now_iso}</updated>",
        "  <generator>publish.py</generator>",
    ]

    for book in sorted_books:
        bid         = book["id"]
        entry_uuid  = uuid_mod.uuid5(_UUID_NS, str(bid))
        t           = book.get("title", "")
        authors     = book.get("authors") or ["Unknown"]
        publisher   = book.get("publisher", "")
        tags        = book.get("tags") or []
        series      = book.get("series", "")
        series_idx  = book.get("series_index", 0)
        pubdate     = book.get("pubdate") or book.get("timestamp") or now_iso[:10]
        published   = pubdate + "T00:00:00Z" if len(pubdate) == 10 else pubdate

        epub_url = f"{site_url}/{book['epub']}" if book.get("epub") else ""
        pdf_url  = f"{site_url}/{book['pdf']}"  if book.get("pdf")  else ""

        content_parts = []
        if epub_url:
            content_parts.append(f'<p><a href="{epub_url}">⬇ Download EPUB</a></p>')
        if pdf_url:
            content_parts.append(f'<p><a href="{pdf_url}">⬇ Download PDF</a></p>')
        content_html = xml_esc("".join(content_parts))

        lines.append("  <entry>")
        lines.append(f"    <title>{xml_esc(t)}</title>")
        lines.append(f"    <id>urn:uuid:{entry_uuid}</id>")
        lines.append(f"    <published>{published}</published>")
        lines.append(f"    <updated>{published}</updated>")
        for author in authors:
            lines.append(f"    <author><name>{xml_esc(author)}</name></author>")
        if epub_url:
            lines.append(f'    <link rel="alternate" type="application/epub+zip" href="{epub_url}" title="{xml_esc(t)}" />')
            lines.append(f'    <link rel="enclosure" type="application/epub+zip" href="{epub_url}" title="{xml_esc(t)}" />')
        lines.append(f"    <content type=\"html\">{content_html}</content>")
        if publisher:
            lines.append(f"    <dc:publisher>{xml_esc(publisher)}</dc:publisher>")
        for tag in tags:
            lines.append(f'    <category term="{xml_esc(tag)}" />')
        if series:
            lines.append(f"    <dc:relation>{xml_esc(series)} [{series_idx}]</dc:relation>")
        lines.append("  </entry>")

    lines.append("</feed>")

    feed_path = output_dir / "feed.xml"
    feed_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[publish] Wrote feed.xml ({len(sorted_books)} entries)")


# ---------------------------------------------------------------------------
# FTP deploy
# ---------------------------------------------------------------------------

ALWAYS_UPLOAD = {".php", ".js", ".css", ".svg", ".json", ".xml"}
SIZE_CHECK     = {".epub", ".pdf", ".jpg", ".jpeg", ".txt"}


def _ftp_ensure_dir(ftp: ftplib.FTP, remote_dir: str, _made: set) -> None:
    """Create remote directory tree if needed (cached to avoid redundant MKD)."""
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
    path = ""
    for part in parts:
        path += "/" + part
        if path in _made:
            continue
        try:
            ftp.mkd(path)
        except ftplib.error_perm:
            pass  # already exists
        _made.add(path)


def _remote_size(ftp: ftplib.FTP, remote_path: str) -> int | None:
    """Get size of a single remote file via the SIZE command."""
    try:
        ftp.voidcmd("TYPE I")
        return ftp.size(remote_path)
    except Exception:
        return None


def deploy(local_dir: Path, cfg: dict) -> None:
    host        = cfg["ftp_host"]
    user        = cfg["ftp_user"]
    password    = cfg["ftp_pass"]
    remote_base = cfg["ftp_remote_dir"].rstrip("/")

    print(f"\n[deploy] Connecting to {host}…")
    ftp = ftplib.FTP(host, timeout=30)
    ftp.login(user, password)
    ftp.set_pasv(True)
    print(f"[deploy] Connected. Uploading → {remote_base}")

    uploaded = skipped = 0
    _made_dirs: set = set()
    all_files = sorted(local_dir.rglob("*"))
    print(f"[deploy] {len(all_files)} total paths to scan")

    for local_path in all_files:
        if not local_path.is_file():
            continue

        rel         = local_path.relative_to(local_dir)
        remote_path = remote_base + "/" + "/".join(rel.parts)
        ext         = local_path.suffix.lower()

        if ext not in ALWAYS_UPLOAD and ext not in SIZE_CHECK:
            continue

        if ext in SIZE_CHECK:
            remote_sz = _remote_size(ftp, remote_path)
            if remote_sz == local_path.stat().st_size:
                skipped += 1
                continue

        remote_dir = remote_path.rsplit("/", 1)[0]
        _ftp_ensure_dir(ftp, remote_dir, _made_dirs)
        with open(local_path, "rb") as f:
            ftp.storbinary(f"STOR {remote_path}", f)

        tag = "force" if ext in ALWAYS_UPLOAD else "changed"
        print(f"  [{tag}] {rel}")
        uploaded += 1

    ftp.quit()
    print(f"[deploy] Done. {uploaded} uploaded, {skipped} skipped.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} config.json", file=sys.stderr)
        sys.exit(1)
    publish(sys.argv[1])
