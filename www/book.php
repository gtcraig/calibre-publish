<?php
require_once __DIR__ . '/_lib.php';

$id   = isset($_GET['id']) ? (int)$_GET['id'] : 0;
$book = $id ? book_by_id($id) : null;
$site = load_site();

if (!$book) {
    http_response_code(404);
    $title = site_title();
    echo "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Not found &mdash; {$title}</title>"
       . "<link rel='stylesheet' href='assets/style.css'></head><body>"
       . "<header class='site-header'><div class='site-header-inner'>"
       . "<a class='site-name' href='index.php'>{$title}</a></div></header>"
       . "<main class='main-content'><h1>Book not found</h1><p><a href='index.php'>&larr; Home</a></p></main></body></html>";
    exit;
}

$title_str  = $book['title'];
$authors    = implode(', ', $book['authors'] ?? []);
$tags       = $book['tags'] ?? [];
$series     = $book['series'] ?? '';
$si         = (float)($book['series_index'] ?? 0);
$pubdate    = $book['pubdate'] ?? '';
$comments   = $book['comments'] ?? '';
$cover      = $book['cover'] ?? '';
$epub       = $book['epub']  ?? '';
$pdf        = $book['pdf']   ?? '';
$page_title = h($title_str) . ' — ' . site_title();
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title><?= $page_title ?></title>
  <link rel="stylesheet" href="assets/style.css">
  <link rel="stylesheet" href="assets/theme.css">
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <a class="site-name" href="index.php"><?= site_title() ?></a>
    <nav class="main-nav">
      <a href="index.php?view=recent">Recent</a>
      <a href="index.php?view=series">Series</a>
      <a href="index.php?view=publishers">Publishers</a>
      <a href="index.php?view=authors">Authors</a>
      <a href="index.php?view=tags">Tags</a>
    </nav>
  </div>
  <div class="search-bar">
    <div class="search-wrap">
      <input id="quick-search" type="search" placeholder="Search titles &amp; authors…" autocomplete="off" aria-label="Search titles and authors">
      <div id="search-results" class="search-dropdown" hidden></div>
    </div>
    <a href="fulltext.php" class="btn-fulltext">Full-text search</a>
  </div>
</header>

<main class="main-content">
  <p class="back"><a href="javascript:history.back()">&larr; Back</a></p>

  <div class="book-detail">
    <div class="book-cover-col">
      <?php if ($cover): ?>
        <img class="book-cover-lg" src="<?= h($cover) ?>" alt="<?= h($title_str) ?>"
             onerror="this.src='assets/no-cover.svg'">
      <?php endif; ?>

      <?php $dl_name = preg_replace('/[^\w\s\-]/u', '', $title_str); ?>
      <div class="dl-buttons">
        <?php if ($epub): ?>
          <a class="btn-dl epub" href="<?= h($epub) ?>" download="<?= h($dl_name) ?>.epub" target="_blank">⬇ Download EPUB</a>
        <?php endif; ?>
        <?php if ($pdf): ?>
          <a class="btn-dl pdf" href="<?= h($pdf) ?>" download="<?= h($dl_name) ?>.pdf" target="_blank">⬇ Download PDF</a>
        <?php endif; ?>
      </div>
    </div>

    <div class="book-meta-col">
      <h1 class="book-title"><?= h($title_str) ?></h1>

      <?php if ($authors): ?>
        <p class="book-author">
          by
          <?php foreach ($book['authors'] as $i => $a): ?>
            <?= $i > 0 ? ', ' : '' ?>
            <a href="index.php?view=authors&filter=<?= urlencode($a) ?>"><?= h($a) ?></a>
          <?php endforeach; ?>
        </p>
      <?php endif; ?>

      <?php if ($series): ?>
        <p class="book-series">
          Series:
          <a href="index.php?view=series&filter=<?= urlencode($series) ?>"><?= h($series) ?></a>
          #<?= $si ?>
        </p>
      <?php endif; ?>

      <?php if (!empty($book['publisher'])): ?>
        <p class="book-publisher">
          Publisher: <a href="index.php?view=publishers&filter=<?= urlencode($book['publisher']) ?>"><?= h($book['publisher']) ?></a>
        </p>
      <?php endif; ?>
      <?php if ($pubdate): ?>
        <p class="book-pubdate">Published: <?= h($pubdate) ?></p>
      <?php endif; ?>

      <?php if ($tags): ?>
        <p class="book-tags">
          <?php foreach ($tags as $tag): ?>
            <a class="tag" href="index.php?view=tags&filter=<?= urlencode($tag) ?>"><?= h($tag) ?></a>
          <?php endforeach; ?>
        </p>
      <?php endif; ?>

      <?php if ($comments): ?>
        <div class="book-description">
          <h2>Description</h2>
          <p><?= nl2br(h($comments)) ?></p>
        </div>
      <?php endif; ?>
    </div>
  </div>
</main>

<footer class="site-footer">
  <p><?= (int)($site['book_count'] ?? 0) ?> books &middot; generated <?= h($site['generated'] ?? '') ?></p>
</footer>

<script src="assets/app.js"></script>
</body>
</html>
