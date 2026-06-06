<?php
require_once __DIR__ . '/_lib.php';

$site   = load_site();
$title  = site_title();
$base   = site_base();
$view   = $_GET['view'] ?? 'recent';
$filter = trim($_GET['filter'] ?? '');

function sort_books(array &$books): void {
    usort($books, function($a, $b) {
        // 1. pubdate descending
        $pd = strcmp($b['pubdate'] ?? '', $a['pubdate'] ?? '');
        if ($pd !== 0) return $pd;
        // 2. series name ascending
        $ps = strcmp($a['series'] ?? '', $b['series'] ?? '');
        if ($ps !== 0) return $ps;
        // 3. series index ascending
        return ($a['series_index'] ?? 0) <=> ($b['series_index'] ?? 0);
    });
}

ob_start();

switch ($view) {
    // ------------------------------------------------------------------ recent
    case 'recent':
        $heading = 'Recently Added';
        $n = (int)($site['recent_count'] ?? 20);
        $books = recent_books($n);
        sort_books($books);
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
                // Use the first book's author_ids to find this author's Calibre ID
                $aid = 0;
                foreach ($books as $b) {
                    $pos = array_search($author, $b['authors'] ?? []);
                    if ($pos !== false && isset($b['author_ids'][$pos])) {
                        $aid = (int)$b['author_ids'][$pos];
                        break;
                    }
                }
                $a = h($author);
                $n = count($books);
                echo "<li><a href=\"{$base}authors/{$aid}\">{$a} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            $author_name = is_numeric($filter) ? (author_by_id((int)$filter) ?? $filter) : $filter;
            $books = $index[$author_name] ?? [];
            sort_books($books);
            echo '<p class="back"><a href="' . $base . 'authors">&larr; All Authors</a></p>';
            echo '<h2 class="filter-heading">' . h($author_name) . '</h2>';
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
                $sid = (int)($books[0]['series_id'] ?? 0);
                $n  = count($books);
                echo "<li><a href=\"{$base}series/{$sid}\">{$s} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            // $filter may be a numeric ID or a legacy name
            $series_name = is_numeric($filter) ? (series_by_id((int)$filter) ?? $filter) : $filter;
            $books = $index[$series_name] ?? [];
            sort_books($books);
            echo '<p class="back"><a href="' . $base . 'series">&larr; All Series</a></p>';
            echo '<h2 class="filter-heading">' . h($series_name) . '</h2>';
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
                $tf = rawurlencode($tag);
                $n  = count($books);
                echo "<li><a href=\"{$base}tags/{$tf}\">{$t} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            $books = $index[$filter] ?? [];
            sort_books($books);
            echo '<p class="back"><a href="' . $base . 'tags">&larr; All Tags</a></p>';
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
                $pid = (int)($books[0]['publisher_id'] ?? 0);
                $p   = h($pub);
                $n   = count($books);
                echo "<li><a href=\"{$base}publishers/{$pid}\">{$p} <span class=\"count\">{$n}</span></a></li>";
            }
            echo '</ul>';
        } else {
            $pub_name = is_numeric($filter) ? (publisher_by_id((int)$filter) ?? $filter) : $filter;
            $books = $index[$pub_name] ?? [];
            sort_books($books);
            echo '<p class="back"><a href="' . $base . 'publishers">&larr; All Publishers</a></p>';
            echo '<h2 class="filter-heading">' . h($pub_name) . '</h2>';
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
  <base href="<?= h($base) ?>">
  <title><?= $title ?></title>
  <link rel="stylesheet" href="assets/style.css">
  <link rel="stylesheet" href="assets/theme.css">
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <a class="site-name" href="<?= h($base) ?>"><?= $title ?></a>
    <nav class="main-nav">
      <a href="<?= h($base) ?>recent"     <?= $view==='recent'     ? 'class="active"' : '' ?>>Recent</a>
      <a href="<?= h($base) ?>series"     <?= $view==='series'     ? 'class="active"' : '' ?>>Series</a>
      <a href="<?= h($base) ?>publishers" <?= $view==='publishers' ? 'class="active"' : '' ?>>Publishers</a>
      <a href="<?= h($base) ?>authors"    <?= $view==='authors'    ? 'class="active"' : '' ?>>Authors</a>
      <a href="<?= h($base) ?>tags"       <?= $view==='tags'       ? 'class="active"' : '' ?>>Tags</a>
      <?php if (main_site_url()): ?>
        <a href="<?= h(main_site_url()) ?>" class="nav-main-site" target="_blank"><?= h(main_site_name()) ?> ↗</a>
      <?php endif; ?>
    </nav>
  </div>
  <div class="search-bar">
    <div class="search-wrap">
      <input id="quick-search" type="search" placeholder="Search titles &amp; authors…" autocomplete="off" aria-label="Search titles and authors">
      <div id="search-results" class="search-dropdown" hidden></div>
    </div>
    <a href="<?= h($base) ?>fulltext" class="btn-fulltext">Full-text search</a>
  </div>
</header>

<main class="main-content">
  <?php if (!empty($heading)): ?>
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
