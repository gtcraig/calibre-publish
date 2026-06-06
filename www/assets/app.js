/**
 * app.js — as-you-type title/author search
 *
 * Watches #quick-search, debounces keystrokes, calls search.php,
 * renders results in #search-results dropdown.
 * Pressing Enter on a highlighted item navigates to book.php.
 */

(function () {
  'use strict';

  const input    = document.getElementById('quick-search');
  const dropdown = document.getElementById('search-results');

  if (!input || !dropdown) return;

  let timer    = null;
  let items    = [];   // current rendered items
  let selected = -1;  // keyboard-selected index

  // ── Debounced fetch ──────────────────────────────────────
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { hide(); return; }
    timer = setTimeout(() => fetchResults(q), 200);
  });

  async function fetchResults(q) {
    try {
      const res  = await fetch('search.php?q=' + encodeURIComponent(q) + '&limit=20');
      const data = await res.json();
      render(data, q);
    } catch {
      hide();
    }
  }

  // ── Render ───────────────────────────────────────────────
  function render(books, q) {
    dropdown.innerHTML = '';
    items = [];
    selected = -1;

    if (books.length === 0) {
      const el = document.createElement('div');
      el.className = 'sd-none';
      el.textContent = 'No results for "' + q + '"';
      dropdown.appendChild(el);
      show();
      return;
    }

    for (const book of books) {
      const el = document.createElement('div');
      el.className = 'sd-item';
      el.setAttribute('role', 'option');
      el.dataset.href = 'book.php?id=' + book.id;

      const authors = (book.authors || []).join(', ');
      const series  = book.series
        ? '<span class="sd-series">' + esc(book.series) + ' #' + (book.series_index || '') + '</span>'
        : '';

      el.innerHTML =
        '<img class="sd-thumb" src="' + esc(book.cover || '') + '" alt="" ' +
             'onerror="this.src=\'assets/no-cover.svg\'">' +
        '<div class="sd-info">' +
          '<div class="sd-title">' + highlight(esc(book.title), q) + '</div>' +
          '<div class="sd-author">' + highlight(esc(authors), q) + '</div>' +
          series +
        '</div>';

      el.addEventListener('mousedown', (e) => {
        e.preventDefault(); // stop blur dismissing dropdown before click
        navigate(el.dataset.href);
      });

      dropdown.appendChild(el);
      items.push(el);
    }

    show();
  }

  // ── Keyboard navigation ──────────────────────────────────
  input.addEventListener('keydown', (e) => {
    if (!isVisible()) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelected(Math.min(selected + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelected(Math.max(selected - 1, -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selected >= 0 && items[selected]) {
        navigate(items[selected].dataset.href);
      } else if (items.length > 0) {
        navigate(items[0].dataset.href);
      }
    } else if (e.key === 'Escape') {
      hide();
    }
  });

  function setSelected(idx) {
    items.forEach((el, i) => el.classList.toggle('active', i === idx));
    selected = idx;
    if (idx >= 0) items[idx].scrollIntoView({ block: 'nearest' });
  }

  // ── Dismiss on outside click ─────────────────────────────
  document.addEventListener('click', (e) => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) hide();
  });

  input.addEventListener('focus', () => {
    if (items.length > 0) show();
  });

  // ── Helpers ──────────────────────────────────────────────
  function show() { dropdown.hidden = false; }
  function hide() { dropdown.hidden = true; }
  function isVisible() { return !dropdown.hidden; }

  function navigate(href) {
    hide();
    window.location.href = href;
  }

  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /** Wrap matching tokens in <strong> */
  function highlight(escaped, q) {
    const tokens = q.split(/\s+/).filter(Boolean);
    let out = escaped;
    for (const t of tokens) {
      const re = new RegExp('(' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
      out = out.replace(re, '<strong>$1</strong>');
    }
    return out;
  }

})();
