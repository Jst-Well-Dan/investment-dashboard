/* Dan's Investment Dashboard · 页面交互
   主题切换、档案筛选与走势采样点查看。无 JS 时所有内容仍可直接阅读。 */
(function () {
  'use strict';

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

  var filters = document.getElementById('filters');
  var search = document.getElementById('archive-search');
  if (filters || search) {
    var buttons = filters ? Array.prototype.slice.call(filters.querySelectorAll('[data-filter-topic]')) : [];
    var activeTopic = '';

    function applyFilter() {
      var query = search ? search.value.trim().toLowerCase() : '';
      Array.prototype.slice.call(document.querySelectorAll('[data-topics]')).forEach(function (n) {
        // 主题名里有空格（如「AI 产业链」），所以用 "|" 分隔而不是空白
        var tags = (n.getAttribute('data-topics') || '').split('|').filter(Boolean);
        var topicOk = !activeTopic || tags.indexOf(activeTopic) !== -1;
        var queryOk = !query || n.textContent.toLowerCase().indexOf(query) !== -1;
        n.style.display = topicOk && queryOk ? '' : 'none';
      });
      // 作用域块（板块 / 个股 / 方法论）：里面一个分组都没了就整块收起来，
      // 避免筛出「个股研究」时留下一个空的方法论标题。
      Array.prototype.slice.call(document.querySelectorAll('.scope-block')).forEach(function (s) {
        var alive = Array.prototype.slice.call(s.querySelectorAll('.group-block')).some(function (g) {
          return g.style.display !== 'none';
        });
        s.style.display = alive ? '' : 'none';
      });
      buttons.forEach(function (b) {
        b.setAttribute('aria-pressed', String(b.getAttribute('data-filter-topic') === activeTopic));
      });
    }

    if (filters) {
      filters.addEventListener('click', function (ev) {
        var b = ev.target.closest('[data-filter-topic]');
        if (!b) return;
        activeTopic = b.getAttribute('data-filter-topic') || '';
        applyFilter();
      });
    }
    if (search) {
      search.addEventListener('input', applyFilter);
    }
  }

  Array.prototype.slice.call(document.querySelectorAll('.market-chart')).forEach(function (chart) {
    var values = [];
    try { values = JSON.parse(chart.getAttribute('data-values') || '[]'); } catch (e) {}
    if (values.length < 2) return;
    var unit = chart.getAttribute('data-unit') || '';
    var svg = chart.querySelector('.market-plot');
    var dot = chart.querySelector('.plot-dot');
    var out = chart.querySelector('output');
    var current = values.length - 1;
    var points = (chart.querySelector('.plot-line').getAttribute('points') || '').trim().split(/\s+/).map(function (pair) {
      var parts = pair.split(',');
      return [ Number(parts[0]), Number(parts[1]) ];
    });

    function show(index) {
      current = Math.max(0, Math.min(values.length - 1, index));
      var pt = points[current];
      if (pt && dot) {
        dot.setAttribute('cx', pt[0].toFixed(2));
        dot.setAttribute('cy', pt[1].toFixed(2));
      }
      if (out) {
        out.textContent = '样本 ' + (current + 1) + ' / ' + values.length + ' · ' +
          values[current].toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 }) +
          (unit ? ' ' + unit : '');
      }
    }

    if (svg) {
      svg.addEventListener('pointermove', function (ev) {
        var rect = svg.getBoundingClientRect();
        var ratio = (ev.clientX - rect.left) / Math.max(rect.width, 1);
        show(Math.round(ratio * (values.length - 1)));
      });
      svg.addEventListener('keydown', function (ev) {
        if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
        ev.preventDefault();
        show(current + (ev.key === 'ArrowRight' ? 1 : -1));
      });
    }
  });
})();
