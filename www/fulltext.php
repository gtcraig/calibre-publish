<?php
require_once __DIR__ . '/_lib.php';

$site  = load_site();
$base  = site_base();
$q     = trim($_GET['q'] ?? '');
$page  = max(1, (int)($_GET['page'] ?? 1));
$per   = 15;

$results    = [];
$total      = 0;
$error      = '';
$searched   = false;

if ($q !== '') {
    $searched = true;
    $text_dir = __DIR__ . '/text';

    if (!is_dir($text_dir)) {
        $error = 'Full-text index not found. Re-run publish.py with extract_text enabled.';
    } else {
        // Build a map of id => book for fast lookup
        $book_map = [];
        foreach (load_books() as $b) {
            $book_map[(int)$b['id']] = $b;
        }

        // Tokenise query — all tokens must appear in the text
        $tokens = preg_split('/\s+/', strtolower($q), -1, PREG_SPLIT_NO_EMPTY);

        foreach (glob($text_dir . '/*.txt') as $txt_file) {
            $id = (int)basename($txt_file, '.txt');
            if (!isset($book_map[$id])) continue;

            $text_orig  = file_get_contents($txt_file);
            $text_lower = strtolower($text_orig);
            foreach ($tokens as $t) {
                if (strpos($text_lower, $t) === false) continue 2;
            }

            // Build a snippet from the ORIGINAL (mixed-case) text
            $pos     = stripos($text_orig, $tokens[0]);
            $start   = max(0, $pos - 120);
            $snippet = substr($text_orig, $start, 300);
            // Trim to word boundaries
            if ($start > 0) $snippet = '…' . ltrim(substr($snippet, strpos($snippet, ' ') + 1));
            $snippet .= '…';

            // Highlight all tokens in snippet
            foreach ($tokens as $t) {
                $snippet = preg_replace(
                    '/' . preg_quote($t, '/') . '/i',
                    '<mark>$0</mark>',
                    $snippet
                );
            }

            $results[] = [
                'book'    => $book_map[$id],
                'snippet' => $snippet,
            ];
        }

        $total = count($results);
        // Sort by title
        usort($results, fn($a, $b) => strcmp($a['book']['title'], $b['book']['title']));
        $results = array_slice($results, ($page - 1) * $per, $per);
    }
}

$pages = $total ? (int)ceil($total / $per) : 0;
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <base href="<?= h($base) ?>">
  <title>Full-text search — <?= site_title() ?></title>
  <link rel="stylesheet" href="assets/style.css">
  <link rel="stylesheet" href="assets/theme.css">
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <a class="site-name" href="index.php"><?= site_title() ?></a>
    <nav class="main-nav">
      <a href="<?= h($base) ?>recent">Recent</a>
      <a href="<?= h($base) ?>series">Series</a>
      <a href="<?= h($base) ?>publishers">Publishers</a>
      <a href="<?= h($base) ?>authors">Authors</a>
      <a href="<?= h($base) ?>tags">Tags</a>
    </nav>
  </div>
  <div class="search-bar">
    <div class="search-wrap">
      <input id="quick-search" type="search" placeholder="Search titles &amp; authors…" autocomplete="off" aria-label="Search titles and authors">
      <div id="search-results" class="search-dropdown" hidden></div>
    </div>
    <a href="<?= h($base) ?>fulltext" class="btn-fulltext active">Full-text search</a>
  </div>
</header>

<main class="main-content fulltext-page">
  <h1 class="page-heading">Full-text Search</h1>

  <form class="fulltext-form" method="get" action="<?= h($base) ?>fulltext">
    <input class="fulltext-input" type="search" name="q"
           value="<?= h($q) ?>" placeholder="Search within books…" autofocus>
    <button class="btn-search" type="submit">Search</button>
  </form>

  <?php if ($error): ?>
    <p class="error"><?= h($error) ?></p>

  <?php elseif ($searched && $total === 0): ?>
    <p class="no-results">No books contain "<strong><?= h($q) ?></strong>".</p>

  <?php elseif ($searched): ?>
    <p class="result-count">
      <?= $total ?> book<?= $total !== 1 ? 's' : '' ?> contain
      "<strong><?= h($q) ?></strong>"
      <?php if ($pages > 1): ?>
        &mdash; page <?= $page ?> of <?= $pages ?>
      <?php endif; ?>
    </p>

    <div class="fulltext-results">
      <?php foreach ($results as $r):
        $b = $r['book'];
        $cover = h($b['cover'] ?? '');
        $title = h($b['title']);
        $auth  = h(implode(', ', $b['authors'] ?? []));
        $bid   = (int)$b['id'];
      ?>
      <div class="ft-result">
        <a href="book/<?= $bid ?>" class="ft-cover">
          <img src="<?= $cover ?>" alt="<?= $title ?>" loading="lazy"
               onerror="this.src='assets/no-cover.svg'">
        </a>
        <div class="ft-body">
          <h3><a href="book/<?= $bid ?>"><?= $title ?></a></h3>
          <p class="ft-author"><?= $auth ?></p>
          <p class="ft-snippet"><?= $r['snippet'] ?></p>
          <?php $dl_name = preg_replace('/[^\w\s\-]/u', '', $b['title']); ?>
          <div class="ft-dl">
            <?php if ($b['epub']): ?>
              <a class="dl epub" href="<?= h($b['epub']) ?>" download="<?= h($dl_name) ?>.epub" target="_blank">EPUB</a>
            <?php endif; ?>
            <?php if ($b['pdf']): ?>
              <a class="dl pdf" href="<?= h($b['pdf']) ?>" download="<?= h($dl_name) ?>.pdf" target="_blank">PDF</a>
            <?php endif; ?>
          </div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>

    <?php if ($pages > 1): ?>
    <nav class="pagination">
      <?php for ($p = 1; $p <= $pages; $p++): ?>
        <?php if ($p === $page): ?>
          <span class="page current"><?= $p ?></span>
        <?php else: ?>
          <a class="page" href="<?= h($base) ?>fulltext?q=<?= urlencode($q) ?>&page=<?= $p ?>"><?= $p ?></a>
        <?php endif; ?>
      <?php endfor; ?>
    </nav>
    <?php endif; ?>

  <?php endif; ?>
</main>

<footer class="site-footer">
  <p><?= (int)($site['book_count'] ?? 0) ?> books &middot; generated <?= h($site['generated'] ?? '') ?></p>
</footer>

<script src="assets/app.js"></script>
</body>
</html>
