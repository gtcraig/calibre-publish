<?php
require_once __DIR__ . '/_lib.php';

$site   = load_site();
$title  = site_title();
$view   = $_GET['view'] ?? 'recent';  // recent | authors | series | tags
$filter = trim($_GET['filter'] ?? '');

// Build the page content depending on view
$heading = '';
$content_html = '';

ob_start();

switch ($view) {
    // ------------------------------------------------------------------ recent
    case 'recent':
        $heading = 'Recently Added';
        $n = (int)($site['recent_count'] ?? 20);
        $books = recent_books($n);
        echo '<div class="card-grid">';
        foreach ($books as $b) render_card($b);
        echo '</div>';
        break;

    // ------------------------------------------------------------------ authors
    case 'authors':
        $heading = 'Browse by Author';
        $index = build_index('authors');
        if ($filter === '') {
            echo '<ul class="pill-list pill-authors">';
            foreach ($index as $author => $books) {
                $a  = h($author);
                $af = urlencode($author);
                $n  = count($books);
                echo "<li><a href=\"?view=authors&amp;filter={$af}\">{$a} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            $books = $index[$filter] ?? [];
            echo '<p class="back"><a href="?view=authors">&larr; All Authors</a></p>';
            echo '<h2 class="filter-heading">' . h($filter) . '</h2>';
            echo '<div class="card-grid">';
            foreach ($books as $b) render_card($b);
            echo '</div>';
        }
        break;

    // ------------------------------------------------------------------ series
    case 'series':
        $heading = 'Browse by Series';
        $index = build_index('series');
        if ($filter === '') {
            echo '<ul class="pill-list pill-series">';
            foreach ($index as $series => $books) {
                if ($series === '') continue;
                $s  = h($series);
                $sf = urlencode($series);
                $n  = count($books);
                echo "<li><a href=\"?view=series&amp;filter={$sf}\">{$s} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            $books = $index[$filter] ?? [];
            usort($books, fn($a, $b) => ($a['series_index'] ?? 0) <=> ($b['series_index'] ?? 0));
            echo '<p class="back"><a href="?view=series">&larr; All Series</a></p>';
            echo '<h2 class="filter-heading">' . h($filter) . '</h2>';
            echo '<div class="card-grid">';
            foreach ($books as $b) render_card($b);
            echo '</div>';
        }
        break;

    // ------------------------------------------------------------------ tags
    case 'tags':
        $heading = 'Browse by Tag';
        $index = build_index('tags');
        if ($filter === '') {
            echo '<ul class="pill-list pill-tags">';
            foreach ($index as $tag => $books) {
                $t  = h($tag);
                $tf = urlencode($tag);
                $n  = count($books);
                echo "<li><a href=\"?view=tags&amp;filter={$tf}\">{$t} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            $books = $index[$filter] ?? [];
            echo '<p class="back"><a href="?view=tags">&larr; All Tags</a></p>';
            echo '<h2 class="filter-heading">' . h($filter) . '</h2>';
            echo '<div class="card-grid">';
            foreach ($books as $b) render_card($b);
            echo '</div>';
        }
        break;

    // ------------------------------------------------------------------ publishers
    case 'publishers':
        $heading = 'Browse by Publisher';
        $index = build_index('publisher');
        if ($filter === '') {
            echo '<ul class="pill-list pill-publishers">';
            foreach ($index as $pub => $books) {
                if ($pub === '') continue;
                $p  = h($pub);
                $pf = urlencode($pub);
                $n  = count($books);
                echo "<li><a href=\"?view=publishers&amp;filter={$pf}\">{$p} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            $books = $index[$filter] ?? [];
            usort($books, fn($a, $b) => strcmp($a['title'], $b['title']));
            echo '<p class="back"><a href="?view=publishers">&larr; All Publishers</a></p>';
            echo '<h2 class="filter-heading">' . h($filter) . '</h2>';
            echo '<div class="card-grid">';
            foreach ($books as $b) render_card($b);
            echo '</div>';
        }
        break;
}

$content_html = ob_get_clean();
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title><?= $title ?></title>
  <link rel="stylesheet" href="assets/style.css">
  <link rel="stylesheet" href="assets/theme.css">
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <a class="site-name" href="index.php"><?= $title ?></a>
    <nav class="main-nav">
      <a href="?view=recent"     <?= $view==='recent'     ? 'class="active"' : '' ?>>Recent</a>
      <a href="?view=series"     <?= $view==='series'     ? 'class="active"' : '' ?>>Series</a>
      <a href="?view=publishers" <?= $view==='publishers' ? 'class="active"' : '' ?>>Publishers</a>
      <a href="?view=authors"    <?= $view==='authors'    ? 'class="active"' : '' ?>>Authors</a>
      <a href="?view=tags"       <?= $view==='tags'       ? 'class="active"' : '' ?>>Tags</a>
    </nav>
  </div>
  <!-- Title / Author search -->
  <div class="search-bar">
    <div class="search-wrap">
      <input id="quick-search" type="search" placeholder="Search titles &amp; authors…" autocomplete="off" aria-label="Search titles and authors">
      <div id="search-results" class="search-dropdown" hidden></div>
    </div>
    <a href="fulltext.php" class="btn-fulltext">Full-text search</a>
  </div>
</header>

<main class="main-content">
  <?php if ($heading): ?>
    <h1 class="page-heading"><?= h($heading) ?></h1>
  <?php endif; ?>
  <?= $content_html ?>
</main>

<footer class="site-footer">
  <p><?= (int)($site['book_count'] ?? 0) ?> books &middot; generated <?= h($site['generated'] ?? '') ?></p>
</footer>

<script src="assets/app.js"></script>
</body>
</html>
