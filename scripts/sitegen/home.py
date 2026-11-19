"""首页工作台组件。只呈现清单数据，不推算缺失日期或重写研究结论。"""
from __future__ import annotations

import datetime as dt
import json
import math
from collections import defaultdict
from html import escape as esc

from .model import Entry, Thesis


def icon(name: str) -> str:
    paths = {
        'arrow': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
        'search': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
        'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    }
    return f'<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'


def tone(value: str) -> str:
    return value if value in ('up', 'down', 'flat') else 'flat'


def sample_values(e: Entry) -> list[float]:
    return [float(v) for v in (e.latest.get('spark') or [])
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)]


def metrics_for(e: Entry) -> list[dict]:
    return [m for m in (e.latest.get('metrics') or []) if isinstance(m, dict) and m.get('k')]


X0, X1 = 140, 944   # 绘图区左右边界（viewBox 单位）：左侧 140 留给轴标签


def chart(e: Entry, uid: str) -> str:
    vals = sample_values(e)
    if len(vals) < 2:
        return '<div class="chart-empty">暂无可用走势序列。可打开独立看板查看详情。</div>'
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * .12 if hi > lo else max(abs(hi) * .02, 1)
    lo, hi = lo - pad, hi + pad
    points = [(X0 + i / (len(vals)-1) * (X1-X0), 216 - (v-lo)/(hi-lo)*194) for i,v in enumerate(vals)]
    poly = ' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
    area = f'M{X0},216 L' + ' L'.join(f'{x:.2f},{y:.2f}' for x,y in points) + f' L{X1},216 Z'
    grids = ''.join(
        f'<line x1="{X0}" x2="{X1}" y1="{y}" y2="{y}" class="plot-grid"/>'
        f'<text class="plot-y" x="{X0-14}" y="{y+4}" text-anchor="end">{lo+(216-y)/194*(hi-lo):,.1f}</text>'
        for y in (22, 86, 151, 216)
    )
    metrics = metrics_for(e)
    unit = str(metrics[0].get('u', '')) if metrics else ''
    last = f'样本 {len(vals)} / {len(vals)} · {vals[-1]:,.2f} {unit}'
    rows = ''.join(f'<tr><td>{i+1}</td><td class="n">{v:,.2f}</td></tr>' for i,v in enumerate(vals))
    start = e.latest.get('spark_from')
    start_note = f'序列起点 {esc(str(start))} · ' if start else ''
    return f'''<figure class="market-chart" data-values="{esc(json.dumps(vals))}" data-unit="{esc(unit)}">
      <div class="plot-heading"><span>历史走势 <span class="plot-unit">{esc(unit)}</span></span><output id="{uid}-value">{last}</output></div>
      <svg class="market-plot" viewBox="0 0 960 250" tabindex="0" role="img" aria-labelledby="{uid}-title {uid}-desc">
        <title id="{uid}-title">{esc(e.short)}历史走势</title>
        <desc id="{uid}-desc">{len(vals)} 个按原始顺序排列的采样值，最小 {min(vals):,.2f}，最大 {max(vals):,.2f}。各点日期未提供，横轴为样本序号。</desc>
        {grids}<path d="{area}" class="plot-area"/>
        <polyline points="{poly}" class="plot-line"/>
        <circle class="plot-dot" cx="{points[-1][0]:.2f}" cy="{points[-1][1]:.2f}" r="4"/>
        <text class="plot-x" x="{X0}" y="244">样本 1</text><text class="plot-x" x="{X1}" y="244" text-anchor="end">样本 {len(vals)}</text>
      </svg>
      <figcaption>{start_note}悬停或点按曲线查看采样值；各点日期未提供，末值不一定与主指标同日。</figcaption>
      <details class="sample-table"><summary>查看 {len(vals)} 个采样值</summary><div class="sample-scroll"><table class="table"><caption>{esc(e.short)}原始采样值 · {esc(unit)}</caption><thead><tr><th>样本序号</th><th class="n">数值</th></tr></thead><tbody>{rows}</tbody></table></div></details>
    </figure>'''


def site_link(url: str, up: str) -> str:
    """站内根相对链接按页面深度补前缀；外链与锚点原样返回。"""
    if url.startswith(('http://', 'https://', '#', 'mailto:')):
        return url
    return up + url


def market_panel(e: Entry, idx: int, prefix: str, up: str = '') -> str:
    latest = e.latest
    metrics = metrics_for(e)
    asof = latest.get('asof') or latest.get('date') or e.data_asof or '未提供'
    badge = {'up': 'bull', 'down': 'bear'}.get(latest.get('tone'), 'warn')
    hero = '<p class="chart-empty">暂无指标快照</p>'
    if metrics:
        m = metrics[0]
        hero = f'''<div class="market-number"><span class="market-value num">{esc(str(m.get('v', '—')))}</span>
          <span class="market-unit">{esc(str(m.get('u', '')))}</span><span class="market-change num {tone(m.get('tone'))}">{esc(str(m.get('d', '')))}</span></div>'''
    kpis = ''.join(f'''<div class="market-kpi"><dt>{esc(str(m['k']))}</dt><dd class="num {tone(m.get('tone'))}">{esc(str(m.get('v', '—')))}<small>{esc(str(m.get('u', '')))}</small></dd><dd class="metric-note">{esc(str(m.get('d', '')))}</dd></div>''' for m in metrics[1:])
    note = ''
    if latest.get('text'):
        note = f'''<details class="snapshot-note"><summary>研究记录 <time>{esc(str(latest.get('date') or '日期未提供'))}</time></summary><p>{esc(str(latest['text']))}</p><p class="note-line">文字记录与指标快照独立更新，请按各自日期阅读。</p></details>'''
    elif latest.get('text_auto') or e.summary:
        note = f'<p class="market-summary">{esc(str(latest.get("text_auto") or e.summary))}</p>'
    target = ' target="_blank" rel="noopener"' if e.external else ''
    return f'''<section class="market-panel" aria-labelledby="{prefix}-h-{idx}">
      <div class="market-heading"><h3 id="{prefix}-h-{idx}">{esc(metrics[0]['k'] if metrics else e.short)}</h3><span>指标截至 <time class="num">{esc(str(asof))}</time></span></div>
      {hero}<div class="market-verdict"><span class="verdict {badge}">{esc(str(latest.get('verdict') or '暂无判断'))}</span><span class="snapshot-label">数据快照 · 非实时行情</span></div>
      {chart(e, f'{prefix}-{idx}')}
      <dl class="market-kpis">{kpis}</dl>
      <div class="market-bottom">{note}<a class="text-action" href="{esc(site_link(e.url, up))}"{target}>打开{esc(e.short)}看板{icon('arrow')}</a></div>
    </section>'''


def market(entries: list[Entry], prefix: str = 'market', up: str = '') -> str:
    """两块看板并列。首屏就是这两栏，不再套一层重复的「今日看板」标题。"""
    if not entries:
        return '<section class="work-panel"><p class="empty">暂无每日看板。</p></section>'
    boards = '<div class="board-divider" aria-hidden="true"></div>'.join(
        market_panel(e, i, prefix, up) for i, e in enumerate(entries)
    )
    single = ' single' if len(entries) == 1 else ''
    return f'''<section class="work-panel market" aria-label="今日看板">
      <div class="market-boards{single}">{boards}</div>
    </section>'''


def tracking(theses: list[Thesis]) -> list[Thesis]:
    return sorted((t for t in theses if t.status in ('跟踪中','存疑')), key=lambda t:(t.next_check or dt.date.max, t.entry_id))


def queue_item(t: Thesis, up: str = '') -> str:
    cls = ' doubt' if t.status == '存疑' else ''
    draft = '<span class="badge draft">AI 初稿</span>' if t.draft else ''
    return f'''<details class="review-item {t.css}"><summary><div class="review-head"><span class="review-title">{esc(t.entry_title)}</span><span class="review-state">{draft}<span class="badge{cls}">{esc(t.status)}</span></span></div><span class="review-preview">{esc(t.claim)}</span></summary>
      <div class="review-detail">{f'<p class="review-note">{esc(t.note)}</p>' if t.note else ''}<a href="{esc(site_link(t.entry_url, up))}">打开研究原文{icon('arrow')}</a></div>
    </details>'''


def review_queue(theses: list[Thesis], up: str = '', title: str = '下次复核',
                 all_link: bool = True, compact: bool = False) -> str:
    """最近一组到期判断。放在判断跟踪页顶部，因为它是日期驱动的。

    compact=True 时只留日期条（判断明细就在下面同一页，不重复列一次）。
    """
    active = tracking(theses)
    groups = defaultdict(list)
    for t in active:
        groups[t.next_check].append(t)
    head = f'''<div class="panel-heading"><h2 id="review-heading">{esc(title)}</h2><span class="soft-label">{len(active)} 条待复核</span></div>'''
    all_link = f'<a class="text-action review-all" href="{site_link("theses.html", up)}">查看全部判断{icon('arrow')}</a>' if all_link else ''
    if not groups:
        if compact:
            return ''
        body = '<p class="empty">没有待复核判断。可在判断跟踪页回看已结算记录。</p>'
        return f'''<aside class="work-panel review-panel" aria-labelledby="review-heading"><div class="review-rail">{head}{all_link}</div>{body}</aside>'''

    (date, group), *later = groups.items()
    date_label = date.strftime('%Y-%m-%d') if date else '检查日待定'
    due = '已过检查日期' if group[0].overdue else ('今天检查' if group[0].days_left == 0 else '待检查')
    later_note = '<p class="review-next">此后再无待检查判断</p>'
    if later:
        nxt, items = later[0]
        later_note = f'<p class="review-next">下一组 · <span class="num">{nxt.isoformat() if nxt else "检查日待定"}</span><br>{esc(items[0].group_name)} {len(items)} 条判断</p>'

    if compact:
        # 判断明细就在下面同一页，这里只给一条日期带 + 「哪几家要到期」的分布
        tally = defaultdict(int)
        for t in group:
            tally[t.group_name] += 1
        chips = ''.join(f'<span class="review-chip">{esc(n)}<span class="num">{c}</span></span>'
                        for n, c in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])))
        return f'''<div class="review-strip{' is-overdue' if group[0].overdue else ''}">
      <span class="rs-label">{esc(title)}</span>
      <time class="rs-date num">{date_label}</time>
      <span class="rs-due">{len(group)} 条判断 · {due}</span>
      <span class="review-heads">{chips}</span>
      <span class="rs-next">{later_note}</span>
    </div>'''

    return f'''<aside class="work-panel review-panel" aria-labelledby="review-heading">
      <div class="review-rail">{head}
        <div class="review-date {'is-overdue' if group[0].overdue else ''}"><time>{date_label}</time><p>{len(group)} 条判断 · {due}</p></div>
        {later_note}{all_link}
      </div>
      <div class="review-items">{''.join(queue_item(t, up) for t in group)}</div>
    </aside>'''


def today_boards(cfg: dict, built_at: str) -> str:
    """首页 = 今日看板页。只有看板，不放研究入口与复核队列。"""
    boards = [e for e in cfg['entries'] if e.raw.get('today')]
    asofs = [str(e.latest.get('asof') or e.data_asof) for e in boards if (e.latest.get('asof') or e.data_asof)]
    return f'''<main class="workspace" id="main">
      <header class="workspace-heading"><div><h1>今日看板</h1><p>两个独立看板并列，各自标注数据截至。</p></div><div class="workspace-meta"><span>数据快照 · 非实时行情</span><span>页面构建 <time class="num">{built_at}</time></span></div></header>
      {market(boards)}
    </main>'''
