# Calibre → PHP Library Publisher

Publish a filtered subset of your Calibre library to a self-hosted PHP website.
Run once per site with a different config file. No database required — everything
is driven by a single `books.json` generated at publish time.

## Requirements

- Python 3.10+
- Calibre installed (the `calibredb` command must be on your PATH)
- A web host running PHP 8.0+ (standard shared hosting is fine)

## Quick start

```
# 1. Copy and edit a config for each site
cp config.example.json site1.json
# … edit site1.json …

# 2. Publish
python publish.py site1.json

# 3. Upload the output directory to your web host
rsync -av /path/to/output/site1/ user@host:/public_html/
```

## Config options

| Key | Required | Description |
|-----|----------|-------------|
| `library_path` | ✓ | Absolute path to your Calibre library folder |
| `saved_search` | ✓ | Name of the Calibre saved search to filter books |
| `output_dir` | ✓ | Directory where files are written (created if absent) |
| `site_title` | | Title shown in the browser and header (default: "My Library") |
| `recent_count` | | How many books to show on the Recent page (default: 20) |
| `extract_text` | | Extract plain text for full-text search (default: true) |
| `max_text_chars` | | Max characters extracted per book (default: 500000) |

## Output structure

```
output_dir/
  books.json          — all book metadata
  site.json           — site config (title, generated date, count)
  index.php           — homepage (Recent / Authors / Series / Tags)
  book.php            — individual book detail + download
  search.php          — AJAX endpoint for as-you-type title/author search
  fulltext.php        — full-text search (server-side PHP)
  _lib.php            — shared PHP helpers
  files/{id}/
    book.epub
    book.pdf
  covers/{id}.jpg
  text/{id}.txt       — extracted plain text (for full-text search)
  assets/
    style.css
    app.js
    no-cover.svg
```

## Features

- **Recent** — newest additions first
- **Browse by Author / Series / Tags** — click to filter, sorted alphabetically
- **As-you-type search** — searches title + author as you type, keyboard-navigable
  dropdown, press Enter to open the first result
- **Full-text search** — searches extracted EPUB text server-side; returns a snippet
  with the matched terms highlighted; paginated
- **Download links** — EPUB and PDF download badges on every card and detail page
- **Responsive** — works on mobile and desktop
- **No JS framework** — vanilla JS, no npm, no build step

## Publishing to two sites

```bash
python publish.py fiction.json
python publish.py nonfiction.json
```

Each config points to a different saved search and a different output directory.
Upload each output directory to its own web host or subdirectory.
