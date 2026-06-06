<?php
/**
 * search.php — AJAX endpoint for as-you-type title/author lookup.
 *
 * GET ?q=<query>[&limit=20]
 * Returns JSON array of book objects (lightweight subset).
 */

require_once __DIR__ . '/_lib.php';

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

$q     = strtolower(trim($_GET['q'] ?? ''));
$limit = min((int)($_GET['limit'] ?? 20), 100);

if (strlen($q) < 2) {
    echo json_encode([]);
    exit;
}

// Tokenise query so multi-word searches work (all tokens must match)
$tokens = preg_split('/\s+/', $q, -1, PREG_SPLIT_NO_EMPTY);

$results = [];
foreach (load_books() as $book) {
    $haystack = strtolower(
        $book['title'] . ' ' . implode(' ', $book['authors'] ?? [])
    );
    foreach ($tokens as $t) {
        if (strpos($haystack, $t) === false) continue 2;
    }
    $results[] = [
        'id'      => $book['id'],
        'title'   => $book['title'],
        'authors' => $book['authors'],
        'cover'   => $book['cover'],
        'series'  => $book['series'],
        'series_index' => $book['series_index'],
    ];
    if (count($results) >= $limit) break;
}

echo json_encode($results, JSON_UNESCAPED_UNICODE);
