/* Dan's Investment Dashboard · 页面交互
   只做三件事：主题切换、主题筛选、无 JS 也不影响阅读。 */
(function () {
  'use strict';

  /* ---------------------------------------------------------- 主题切换 */
  var KEY = 'dan-dash-theme';
  var root = document.documentElement;

  function apply(mode) {
    if (mode === 'dark' || mode === 'light') {
      root.setAttribute('data-theme', mode);
    } else {
      root.removeAttribute('data-theme');
    }
  }

  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  apply(saved);

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('#theme-btn');
    if (!btn) return;
    var isDark = root.getAttribute('data-theme') === 'dark' ||
      (!root.getAttribute('data-theme') &&
        window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var next = isDark ? 'light' : 'dark';
    apply(next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
  });

  /* ---------------------------------------------------------- 主题筛选 */
  var filters = document.getElementById('filters');
  if (!filters) return;

  var buttons = Array.prototype.slice.call(filters.querySelectorAll('[data-filter-topic]'));

  function nodes() {
    return Array.prototype.slice.call(document.querySelectorAll('[data-topics]'));
  }

  function applyFilter(topic) {
    nodes().forEach(function (n) {
      var tags = (n.getAttribute('data-topics') || '').split(/\s+/).filter(Boolean);
      var show = !topic || tags.indexOf(topic) !== -1;
      n.style.display = show ? '' : 'none';
    });
    buttons.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-filter-topic') === topic));
    });
  }

  filters.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-filter-topic]');
    if (!b) return;
    applyFilter(b.getAttribute('data-filter-topic'));
  });
})();
