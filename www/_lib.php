<?php
/**
 * _lib.php — shared helpers loaded by every page.
 * Include with: require_once __DIR__ . '/_lib.php';
 */

function load_books(): array {
    static $books = null;
    if ($books === null) {
        $path = __DIR__ . '/books.json';
        $books = file_exists($path) ? json_decode(file_get_contents($path), true) : [];
    }
    return $books;
}

function load_site(): array {
    static $cfg = null;
    if ($cfg === null) {
        $path = __DIR__ . '/site.json';
        $cfg = file_exists($path) ? json_decode(file_get_contents($path), true) : [];
    }
    return $cfg;
}

function book_by_id(int $id): ?array {
    foreach (load_books() as $b) {
        if ((int)$b['id'] === $id) return $b;
    }
    return null;
}

function _lookup_by_id(string $map_key, int $id): ?string {
    $cfg = load_site();
    return $cfg[$map_key][(string)$id] ?? null;
}

function series_by_id(int $id): ?string    { return _lookup_by_id('series_by_id', $id); }
function author_by_id(int $id): ?string    { return _lookup_by_id('authors_by_id', $id); }
function publisher_by_id(int $id): ?string { return _lookup_by_id('publishers_by_id', $id); }

function site_base(): string {
    $cfg = load_site();
    return $cfg['base_path'] ?? '/';
}

function site_title(): string {
    $cfg = load_site();
    return htmlspecialchars($cfg['title'] ?? 'Library', ENT_QUOTES);
}

function h(string $s): string {
    return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Build sorted unique index: field => [value => [book, ...]] */
function build_index(string $field): array {
    $index = [];
    foreach (load_books() as $book) {
        $values = $book[$field] ?? [];
        if (!is_array($values)) $values = [$values];
        foreach ($values as $v) {
            $v = trim((string)$v);
            if ($v === '') continue;
            $index[$v][] = $book;
        }
    }
    ksort($index, SORT_NATURAL | SORT_FLAG_CASE);
    return $index;
}

function recent_books(int $n): array {
    $books = load_books();
    usort($books, fn($a, $b) => strcmp($b['timestamp'] ?? '', $a['timestamp'] ?? ''));
    return array_slice($books, 0, $n);
}

/** Render a small book card (used on index and search results). */
function render_card(array $book): void {
    $id      = (int)$book['id'];
    $title   = h($book['title']);
    $auth    = h(implode(', ', $book['authors'] ?? []));
    $cover   = h($book['cover'] ?? '');
    $series_html = '';
    if (!empty($book['series'])) {
        $s = h($book['series']) . ' #' . (float)$book['series_index'];
        $series_html = "<p class=\"card-series\">{$s}</p>";
    }
    $dl_name = preg_replace('/[^\w\s\-]/u', '', $book['title']);
    $epub = $book['epub'] ? '<a class="dl epub" href="' . h($book['epub']) . '" download="' . h($dl_name) . '.epub" target="_blank">EPUB</a>' : '';
    $pdf  = $book['pdf']  ? '<a class="dl pdf"  href="' . h($book['pdf'])  . '" download="' . h($dl_name) . '.pdf"  target="_blank">PDF</a>'  : '';
    echo "<article class=\"card\">\n";
    echo "  <a href=\"book/{$id}\">\n";
    echo "    <img class=\"cover\" src=\"{$cover}\" alt=\"{$title}\" loading=\"lazy\" onerror=\"this.src='assets/no-cover.svg'\">\n";
    echo "    <div class=\"card-body\">\n";
    echo "      <h3 class=\"card-title\">{$title}</h3>\n";
    echo "      <p class=\"card-author\">{$auth}</p>\n";
    echo "      {$series_html}\n";
    echo "    </div>\n";
    echo "  </a>\n";
    echo "  <div class=\"card-dl\">{$epub}{$pdf}</div>\n";
    echo "</article>\n";
}
