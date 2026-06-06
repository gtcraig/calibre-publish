#!/usr/bin/env python3
"""Diagnostic: check Calibre DB IDs for a specific book."""
import sqlite3, sys, json

config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
with open(config_file) as f:
    cfg = json.load(f)

library_path = cfg["library_path"]
db_path = library_path.rstrip("/\\") + "/metadata.db"
print(f"DB: {db_path}\n")

con = sqlite3.connect(db_path)
cur = con.cursor()

# Check tables exist
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", ", ".join(sorted(tables)), "\n")

# Check link tables
for t in ["books_authors_link", "books_series_link", "books_publishers_link"]:
    if t in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        sample = cur.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
        print(f"{t}: {count} rows, sample: {sample}")
    else:
        print(f"MISSING TABLE: {t}")

print()

# Check book 2909 specifically
bid = 2909
print(f"--- Book {bid} ---")
print("books_authors_link:", cur.execute("SELECT * FROM books_authors_link WHERE book=?", (bid,)).fetchall())
print("books_series_link: ", cur.execute("SELECT * FROM books_series_link WHERE book=?", (bid,)).fetchall())
print("books_publishers_link:", cur.execute("SELECT * FROM books_publishers_link WHERE book=?", (bid,)).fetchall())

print()
print("Author names:")
for row in cur.execute("SELECT id, name FROM authors LIMIT 5"):
    print(" ", row)

con.close()
