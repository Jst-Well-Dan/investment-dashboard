"""页面渲染。所有研究信息都来自 model.load()，模板里不写死任何研究数据（约束 C4）。"""
from __future__ import annotations

import datetime as dt
import math
import re
from html import escape as esc
from pathlib import Path

import markdown

from .model import Entry, Group, Thesis

MD = markdown.Markdown(
    extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    output_format="html5",
)

# python-markdown 没有内置任务列表，这里自己补：把 `- [ ] xxx` / `- [x] xxx`
# 渲染成打勾框。必须在 markdown 转换之后做，此时已经是 <li>[ ] xxx</li>。
TASK = re.compile(r"<li>(\s*)\[( |x|X)\](\s*)", re.I)


def _tasks(html: str) -> str:
    return TASK.sub(
        lambda m: f'<li>{m.group(1)}<span class="task" aria-hidden="true">'
                  f'{"☑" if m.group(2).lower() == "x" else "☐"}</span>{m.group(3)}',
        html,
    )


# --------------------------------------------------------------- 公共片段

def head(title: str, depth: int, extra_css: str = "") -> str:
    up = "../" * depth
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{up}assets/theme.css">
{extra_css}
</head>
<body>
"""


def topbar(site: dict, depth: int, current: str) -> str:
    up = "../" * depth
    nav = [
        ("index.html", "今天", "today"),
        ("archive.html", "研究档案", "archive"),
    ]
    if site.get("show_journal"):
        nav.append(("journal/", "日志", "journal"))
    nav.append(("theme.html", "主题", "theme"))

    def href_for(h: str) -> str:
        # journal/ 目录下的页面用 ./ 指向自己这一层，避免变成 journal/journal/
        if h == "journal/" and current == "journal":
            return "./"
        return up + h

    links = "".join(
        f'<a href="{href_for(href)}"' + (' aria-current="page"' if key == current else "") + f'>{label}</a>'
        for href, label, key in nav
    )
    return f"""<div class="topbar">
  <a class="brand" href="{up}index.html">{esc(site.get('title', "Dan's Investment Dashboard"))}</a>
  <nav>{links}</nav>
  <span class="spacer"></span>
  <button class="iconbtn" id="theme-btn" type="button" title="切换浅色 / 深色">◐ 主题</button>
</div>
"""


def foot(site: dict, depth: int, built_at: str) -> str:
    up = "../" * depth
    return f"""<footer class="foot">
  <span>{esc(site.get('disclaimer', ''))}</span>
  <span class="spacer"></span>
  <span>构建于 <span class="num">{built_at}</span></span>
  <a href="{up}index.html">回到入口</a>
</footer>
"""


def script(depth: int) -> str:
    up = "../" * depth
    return f'<script src="{up}assets/site.js"></script>\n'


def href(url: str, depth: int) -> str:
    """把站点根相对 URL 变成相对于 depth 层深的页面 URL（外链原样返回）。"""
    if url.startswith(("http://", "https://", "#", "mailto:")):
        return url
    return "../" * depth + url


def badges_for(e: Entry) -> str:
    kind = f'<span class="tag">{esc(e.kind_label)}</span>'
    topics = "".join(f'<span class="tag">{esc(t)}</span>' for t in e.topics)
    ext = '<span class="tag">独立站点</span>' if e.external else ""
    return kind + ext + topics


def date_str(d: dt.date | None) -> str:
    return d.isoformat() if d else ""


# --------------------------------------------------------------- 论点卡片

def thesis_card(t: Thesis, depth: int = 0) -> str:
    status_badge = f'<span class="badge {c}">{esc(t.status)}</span>' if (c := {
        "跟踪中": "track", "成立": "hold", "存疑": "doubt", "证伪": "dead",
    }.get(t.status, "track")) else ""
    if t.overdue:
        status_badge = '<span class="badge overdue">已到期</span>' + status_badge
    check = ""
    if t.next_check:
        d = t.days_left
        if d is None:
            tail = ""
        elif d < 0:
            tail = f"（逾期 {-d} 天）"
        elif d == 0:
            tail = "（今天）"
        else:
            tail = f"（还有 {d} 天）"
        check = f'<span>下次检查 <span class="num">{t.next_check.isoformat()}</span>{tail}</span>'
    note = f'<span class="th-note">{esc(t.note)}</span>' if t.note else ""
    return f"""<div class="thesis {t.css}">
  <div class="th-claim">{esc(t.claim)}</div>
  <div class="th-badges">{status_badge}</div>
  <div class="th-foot">
    <span><a href="{href(t.entry_url, depth)}">{esc(t.entry_title)}</a></span>
    {check}
    {note}
  </div>
</div>"""


# --------------------------------------------------------------- 首页

def sparkline(values: list[float], uid: str, w: int = 420, h: int = 54,
              stroke: str = "var(--ink-2)") -> str:
    """纯 inline SVG 面积走势线：无 JS、无 CDN、无外部依赖。"""
    vals = [float(v) for v in values if isinstance(v, (int, float))]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    n = len(vals)
    pts = [(i / (n - 1) * w, h - 3 - (v - lo) / (hi - lo) * (h - 6)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    path = "M" + f"{pts[0][0]:.1f},{h} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) \
           + f" L{pts[-1][0]:.1f},{h} Z"
    return f"""<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">
  <defs><linearGradient id="sg{uid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{stroke}" stop-opacity=".20"/>
    <stop offset="1" stop-color="{stroke}" stop-opacity="0"/>
  </linearGradient></defs>
  <path d="{path}" fill="url(#sg{uid})"/>
  <polyline points="{line}" fill="none" stroke="{stroke}" stroke-width="1.6"
    stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="2.6" fill="{stroke}"/>
</svg>"""


def today_card(e: Entry, idx: int = 0) -> str:
    """今日看板卡：结论徽标 + 大数字 + 走势线 + 三列 KPI + 一句话。

    数据来自 research.yaml 里 latest: 的手写字段（date / text）和
    pull_latest.py 写的 auto 块（asof / verdict / metrics / spark）。
    auto 块不存在时自动退回旧版纯文字卡，不会崩。
    """
    latest = e.latest
    text = latest.get("text") or latest.get("text_auto") or e.summary
    metrics = [m for m in (latest.get("metrics") or []) if isinstance(m, dict) and m.get("k")]
    spark = latest.get("spark") or []
    verdict = latest.get("verdict") or ""
    asof = latest.get("asof") or latest.get("date") or e.data_asof

    # 结论徽标颜色：按看板给出的基调猜，猜不到就中性色
    tone = latest.get("tone") or ""
    if not tone and metrics:
        tone = metrics[0].get("tone", "")
    badge_cls = {"up": "bull", "down": "bear"}.get(tone, "warn")
    verdict_html = f'<span class="verdict {badge_cls}">{esc(verdict)}</span>' if verdict else \
        f'<span class="tag">{esc(e.kind_label)}</span>'

    hero = ""
    if metrics:
        m0 = metrics[0]
        hero = f"""<div class="hero-num">
      <span class="hn-v num">{esc(str(m0.get('v', '')))}</span>
      <span class="hn-u">{esc(str(m0.get('u', '')))}</span>
      <span class="hn-d num {esc(str(m0.get('tone', 'flat')))}">{esc(str(m0.get('d', '')))}</span>
    </div>"""

    # 走势线画的是「绝对值走势」而不是涨跌：用墨色，不占用涨跌语义，
    # 也不用金色——按规则 3，数据区里的金色只表示指引。
    spark_html = sparkline(spark, str(idx), stroke="var(--ink-2)")
    axis = ""
    if spark_html:
        axis = (f'<div class="spark-axis"><span class="num">{esc(str(latest.get("spark_from", "")) or "")}</span>'
                f'<span class="num">{esc(str(asof))}</span></div>')

    rest = metrics[1:]
    kpi_html = ""
    if rest:
        kpi_html = '<div class="kpi3">' + "".join(
            f'<div class="k3"><div class="k3-k">{esc(str(m.get("k", "")))}</div>'
            f'<div class="k3-v num">{esc(str(m.get("v", "")))}'
            f'<span class="k3-u">{esc(str(m.get("u", "")))}</span></div>'
            f'<div class="k3-d {esc(str(m.get("tone", "flat")))}">{esc(str(m.get("d", "")))}</div></div>'
            for m in rest) + '</div>'

    tone_cls = {"bull": " tone-bull", "bear": " tone-bear"}.get(badge_cls, "")
    return f"""<a class="today{tone_cls}" href="{e.url}" target="_blank" rel="noopener">
  <div class="t-top">
    <span class="t-name">{esc(e.short or e.title)}</span>
    {verdict_html}
    <span class="t-date num">{esc(str(asof))}</span>
  </div>
  {hero}
  {spark_html}{axis}
  {kpi_html}
  <div class="t-text">{esc(text)}</div>
  <span class="t-link">打开看板 →</span>
</a>"""


def research_card(e: Entry, show_group: str | None = None, depth: int = 0) -> str:
    """整张卡片就是链接。日期只是标注文字，不再单独做按钮（避免嵌套 a）。"""
    asof = f'<span>数据截至 <span class="num">{esc(e.data_asof)}</span></span>' if e.data_asof else ""
    grp = f'<span class="tag accent">{esc(show_group)}</span>' if show_group else ""
    target = ' target="_blank" rel="noopener"' if e.external else ""
    arrow = " ↗" if e.external else ""
    return f"""<a class="rcard" href="{href(e.url, depth)}"{target} data-topics="{' '.join(e.topics)}" data-group="{e.group}">
  <div class="r-title">{esc(e.title)}{arrow}</div>
  <div class="r-sum">{esc(e.summary)}</div>
  <div class="r-foot">
    {grp}{badges_for(e)}
    {asof}
    <span class="tag-date num">{e.date.isoformat()}</span>
  </div>
</a>"""


def group_block(g: Group, depth: int = 0) -> str:
    outer = [e for e in g.entries if not e.external]
    links = "".join(
        (f'<a class="tag accent" href="{e.url}" target="_blank" rel="noopener">'
         f'{esc(e.short or e.title)} ↗</a>') if e.external else
        f'<a class="tag" href="{href(e.url, depth)}">{esc(e.short or e.title)}</a>'
        for e in g.entries
    )
    code = f'<span class="code">{esc(g.code)}</span>' if g.code else ""
    return f"""<div class="group-block" data-topics="{esc(g.topic)}" data-group="{g.id}">
  <div class="group-head">
    <h3><a href="{href(g.url, depth)}">{esc(g.name)}</a></h3>
    {code}
    <span class="tag-date num">最近更新 {g.latest_date.isoformat()}</span>
  </div>
  <p class="group-intro">{esc(g.intro)}</p>
  <div class="archive-grid">
    {"".join(research_card(e, depth=depth) for e in g.entries)}
  </div>
  <p class="card-note" style="margin-top:8px">组内页面：{links}</p>
</div>"""


def index_page(cfg: dict, built_at: str, latest_journal, journal_count: int,
               journal_dir_rel: str) -> str:
    site = cfg["site"]
    entries = cfg["entries"]
    groups = cfg["groups"]
    theses = cfg["theses"]

    today_entries = [e for e in entries if e.raw.get("today")]
    tracking = [t for t in theses if t.status in ("跟踪中", "存疑")]
    overdue = [t for t in theses if t.overdue]
    settled = [t for t in theses if t.status in ("成立", "证伪")]

    if site.get("show_journal"):
        if latest_journal:
            j_date, j_title, j_sum = latest_journal
            journal_block = f"""<a class="jrow" href="{journal_dir_rel}{j_date}.html">
  <span class="j-date">{j_date}</span>
  <span class="j-title">{esc(j_title)}</span>
  <span class="tag">最近一篇</span>
  <span class="j-note">{esc(j_sum)}</span>
</a>"""
        else:
            journal_block = '<div class="empty">还没有复盘记录。运行 <code>new_journal.bat</code> 生成今天的一篇。</div>'
        journal_sect = f"""<section class="sect">
    <div class="sect-head"><h2>今日复盘</h2><span class="hint">一天一个文件，写在 journal/ 目录</span></div>
    <div class="sect-rule"></div>
    <div class="jlist">{journal_block}</div>
  </section>"""
    else:
        journal_sect = ""

    topics = cfg["topics"]
    filters = '<button type="button" data-filter-topic="" aria-pressed="true">全部</button>' + "".join(
        f'<button type="button" data-filter-topic="{esc(t)}" aria-pressed="false">{esc(t)}</button>'
        for t in topics
    )

    settled_hint = f" · 另有 {len(settled)} 条已结算" if settled else ""
    overdue_note = ""
    if overdue:
        overdue_note = f'<div class="callout risk"><div class="co-h">需要复盘</div>' \
                       f'<p>有 {len(overdue)} 条判断已过检查日期，见下方标红项。</p></div>'

    # lede 只报真实存在的模块，否则会出现「0 篇复盘」这种噪音
    lede_bits = [f'已收录 <span class="num">{len(entries)}</span> 项研究',
                 f'<span class="num">{len(theses)}</span> 条可跟踪判断']
    if site.get("show_journal") and journal_count:
        lede_bits.append(f'<span class="num">{journal_count}</span> 篇复盘')

    return (
        head(site.get("title", "Dan's Investment Dashboard"), 0)
        + topbar(site, 0, "today")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">研究入口</div>
    <h1>{esc(site.get("title", ""))}</h1>
    <p class="lede">{esc(site.get("subtitle", ""))} · {'、'.join(lede_bits)}。</p>
  </header>

  <section class="sect">
    <div class="sect-head"><h2>今天</h2><span class="hint">每天自动更新的看板，点开是它们的独立站点</span></div>
    <div class="sect-rule"></div>
    <div class="today-grid">{"".join(today_card(e, i) for i, e in enumerate(today_entries)) or '<div class="empty">清单里还没有标 today 的看板。</div>'}</div>
  </section>

  {journal_sect}

  <section class="sect">
    <div class="sect-head"><h2>在跟踪的判断</h2><span class="hint">{len(tracking)} 条跟踪中 · 按下次检查日期排{settled_hint}</span></div>
    <div class="sect-rule"></div>
    {overdue_note}
    <div class="thesis-list">{"".join(thesis_card(t) for t in tracking) or '<div class="empty">没有正在跟踪的判断。</div>'}</div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>研究档案</h2><span class="hint">{len(groups)} 组 · 按主题筛选</span></div>
    <div class="sect-rule"></div>
    <div class="filters" id="filters">{filters}</div>
    <div class="stack" id="archive">
      {"".join(group_block(g) for g in groups)}
    </div>
    <p class="card-note" style="margin-top:16px">时间线视图：<a href="archive.html">全部研究按日期排列 →</a></p>
  </section>
"""
        + foot(site, 0, built_at)
        + script(0)
        + "</body>\n</html>\n"
    )


# --------------------------------------------------------------- 档案（时间线）

def archive_page(cfg: dict, built_at: str) -> str:
    site = cfg["site"]
    entries = sorted(cfg["entries"], key=lambda e: (e.date, e.id), reverse=True)
    rows = []
    for e in entries:
        target = ' target="_blank" rel="noopener"' if e.external else ""
        rows.append(f"""<tr data-topics="{' '.join(e.topics)}">
  <td class="date">{e.date.isoformat()}</td>
  <td><a href="{href(e.url, 0)}"{target}>{esc(e.title)}</a>{' ↗' if e.external else ''}</td>
  <td><span class="tag">{esc(e.kind_label)}</span></td>
  <td>{' '.join(f'<span class="tag">{esc(t)}</span>' for t in e.topics)}</td>
  <td class="n">{esc(e.data_asof) or "—"}</td>
  <td>{esc(e.summary)}</td>
</tr>""")
    topics = cfg["topics"]
    filters = '<button type="button" data-filter-topic="" aria-pressed="true">全部</button>' + "".join(
        f'<button type="button" data-filter-topic="{esc(t)}" aria-pressed="false">{esc(t)}</button>'
        for t in topics
    )
    return (
        head("研究档案 · " + site.get("title", ""), 0)
        + topbar(site, 0, "archive")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">Archive</div>
    <h1>研究档案</h1>
    <p class="lede">按完成 / 最近更新日倒序。<span class="num">{len(entries)}</span> 项。</p>
  </header>
  <div class="filters" id="filters">{filters}</div>
  <div class="table-wrap">
    <table class="table">
      <thead><tr>
        <th>日期</th><th>研究</th><th>类型</th><th>主题</th><th class="n">数据截至</th><th>一句话结论</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
  <p class="card-note" style="margin-top:12px">分组视图：<a href="index.html#archive">回到首页按组浏览 →</a></p>
"""
        + foot(site, 0, built_at)
        + script(0)
        + "</body>\n</html>\n"
    )


# --------------------------------------------------------------- 分组页

def group_page(cfg: dict, g: Group, built_at: str, depth: int = 2) -> str:
    site = cfg["site"]
    theses = [t for t in cfg["theses"] if t.group_name == g.name]
    d = depth
    code = f'<span class="tag accent num">{esc(g.code)}</span>' if g.code else ""
    thesis_block = ""
    if theses:
        thesis_block = f"""<section class="sect">
    <div class="sect-head"><h2>本组判断</h2><span class="hint">{len(theses)} 条</span></div>
    <div class="sect-rule"></div>
    <div class="thesis-list">{"".join(thesis_card(t, d) for t in theses)}</div>
  </section>"""
    return (
        head(g.name + " · " + site.get("title", ""), d)
        + topbar(site, d, "")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">研究分组</div>
    <h1>{esc(g.name)} {code}</h1>
    <p class="lede">{esc(g.intro)}</p>
    <div class="meta">共 <span class="num">{len(g.entries)}</span> 页 · 最近更新 <span class="num">{g.latest_date.isoformat()}</span> · 主题 {esc(g.topic)}</div>
  </header>
  <div class="archive-grid">{"".join(research_card(e, depth=depth) for e in g.entries)}</div>
  {thesis_block}
"""
        + foot(site, d, built_at)
        + script(d)
        + "</body>\n</html>\n"
    )


# --------------------------------------------------------------- 日志

FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def _resolve_links(md_text: str, refs: dict[str, str], labels: dict[str, str] | None = None) -> str:
    """[[id]] → 站内链接。日志页在 journal/ 下，所以组内相对路径要加 ../。"""
    labels = labels or {}

    def sub(m):
        key = m.group(1).strip()
        if key.startswith("journal:"):
            d = key.split(":", 1)[1]
            return f"[{d} 复盘]({d}.html)"
        if key in refs:
            target = refs[key]
            prefix = "" if target.startswith("http") else "../"
            return f"[{labels.get(key, key)}]({prefix}{target})"
        return m.group(0)

    return re.sub(r"\[\[([^\]]+)\]\]", sub, md_text)


def parse_journal(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    title, summary = "", ""
    m = FRONT_MATTER.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "title":
                    title = v
                elif k == "summary":
                    summary = v
        text = text[m.end():]
    body = text
    h1 = re.search(r"^#\s+(.+)$", body, re.M)
    if h1 and not title:
        title = h1.group(1).strip()
        body = body[: h1.start()] + body[h1.end():]
    if not summary:
        # 取第一段非标题文本作为摘要
        for line in body.splitlines():
            s = line.strip()
            if s and not s.startswith(("#", ">", "-", "|", "```", "*")):
                summary = s[:120]
                break
    return {"date": path.stem, "title": title or path.stem, "summary": summary, "body": body}


def load_journals(journal_dir: Path) -> list[dict]:
    if not journal_dir.exists():
        return []
    items = []
    for p in sorted(journal_dir.glob("*.md"), reverse=True):
        if p.name.startswith("_"):
            continue
        items.append(parse_journal(p))
    return items


def journal_entry_page(cfg: dict, j: dict, prev: dict | None, next: dict | None,
                       built_at: str) -> str:
    site = cfg["site"]
    refs = {e.id: e.url for e in cfg["entries"]}
    refs.update({g.id: g.url for g in cfg["groups"]})
    labels = {e.id: e.short or e.title for e in cfg["entries"]}
    labels.update({g.id: g.name for g in cfg["groups"]})
    MD.reset()
    html_body = _tasks(MD.convert(_resolve_links(j["body"], refs, labels)))
    pager = []
    if prev:
        pager.append(f'<a class="prev" href="{prev["date"]}.html"><span>前一篇</span>{prev["date"]} {esc(prev["title"])}</a>')
    if next:
        pager.append(f'<a class="next" href="{next["date"]}.html"><span>后一篇</span>{next["date"]} {esc(next["title"])}</a>')
    return (
        head(f'{j["date"]} 复盘 · ' + site.get("title", ""), 1)
        + topbar(site, 1, "journal")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">复盘日志</div>
    <h1>{esc(j["title"])}</h1>
    <div class="meta"><span class="num">{j["date"]}</span></div>
  </header>
  <article class="prose">{html_body}</article>
  <div class="pager">{"".join(pager)}</div>
  <p class="card-note" style="margin-top:20px"><a href="./">← 全部日志</a></p>
"""
        + foot(site, 1, built_at)
        + script(1)
        + "</body>\n</html>\n"
    )


def journal_index_page(cfg: dict, journals: list[dict], built_at: str) -> str:
    site = cfg["site"]
    if journals:
        yrs: dict[str, list[dict]] = {}
        for j in journals:
            yrs.setdefault(j["date"][:4], []).append(j)
        blocks = []
        for y, items in yrs.items():
            rows = "".join(
                f"""<a class="jrow" href="{j['date']}.html">
  <span class="j-date">{j['date']}</span>
  <span class="j-title">{esc(j['title'])}</span>
  <span class="tag">阅读 →</span>
  <span class="j-note">{esc(j['summary'])}</span>
</a>""" for j in items)
            blocks.append(f'<div class="sect-head" style="margin-top:24px"><h2>{y}</h2>'
                          f'<span class="hint">{len(items)} 篇</span></div>'
                          f'<div class="jlist">{rows}</div>')
        body = "".join(blocks)
    else:
        body = '<div class="empty">还没有复盘记录。运行 <code>new_journal.bat</code> 生成今天的一篇。</div>'
    return (
        head("复盘日志 · " + site.get("title", ""), 1)
        + topbar(site, 1, "journal")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">Journal</div>
    <h1>复盘日志</h1>
    <p class="lede">一天一个文件。写了什么不重要，重要的是三个月后能看出哪些判断改了、为什么改。</p>
  </header>
  {body}
"""
        + foot(site, 1, built_at)
        + script(1)
        + "</body>\n</html>\n"
    )


# --------------------------------------------------------------- 主题样例页

def theme_page(cfg: dict, built_at: str) -> str:
    site = cfg["site"]

    # 色板：OKLCH 固定明度/彩度、只转色相。浅色文字档 L .50、色块档 L .68；
    # 深色文字档 L .77、色块档 L .62。数值与 theme.css 的令牌一一对应。
    pal = [
        ("蜜", "Honey", 74, ("#835a18", "6.0"), ("#bd8f4e", ""), ("#d7ac72", "8.3"), ("#a77e45", ""),
         "主题色 · 指引 / 预期", "导航高亮、品牌标记、图表里的预期柱"),
        ("朱", "Cinnabar", 28, ("#924c44", "6.2"), ("#cf8075", ""), ("#e89e94", "8.1"), ("#b67168", ""),
         "涨 · 风险框 · 已到期", ""),
        ("石绿", "Jade", 158, ("#29734e", "5.7"), ("#5eab81", ""), ("#82c69e", "8.7"), ("#539771", ""),
         "跌", ""),
        ("靛", "Indigo", 250, ("#356697", "5.9"), ("#679dd4", ""), ("#88b9ec", "8.4"), ("#5b8abb", ""),
         "实际值 · 口径框", ""),
        ("梅", "Plum", 318, ("#7a5186", "6.2"), ("#b284c0", ""), ("#cda2da", "8.1"), ("#9d75a9", ""),
         "备用 · 图表第三条系列", "不分配固定含义"),
    ]

    def swatch(c: tuple[str, str], on_dark: bool = False) -> str:
        note = f"对比 {c[1]}:1" if c[1] else "图形用"
        cls = "sw on-dark" if on_dark else "sw"
        return (f'<div class="{cls}"><i style="background:{c[0]}"></i>'
                f'<span><span class="hex">{c[0]}</span>'
                f'<span class="cr">{note}</span></span></div>')

    pal_rows = "".join(
        f'<tr><td class="nm"><b>{n}</b><span>{en} · {h}°</span></td>'
        f'<td>{swatch(lt)}</td><td>{swatch(lf)}</td>'
        f'<td>{swatch(dt, True)}</td><td>{swatch(df, True)}</td>'
        f'<td class="role">{role}' + (f'<br><span class="x">{xref}</span>' if xref else "") + '</td></tr>'
        for n, en, h, lt, lf, dt, df, role, xref in pal
    )

    # 色相环：OKLCH 的 a 轴朝右、b 轴朝上
    dots = []
    for i, (n, _en, h, _lt, lf, *_rest) in enumerate(pal):
        r = math.radians(h)
        x, y = math.cos(r) * 92, -math.sin(r) * 92
        lx, ly = math.cos(r) * 113, -math.sin(r) * 113 + 4
        stroke = ' stroke="var(--ink)" stroke-width="1.5"' if i == 0 else ""
        dots.append(
            f'<line x1="0" y1="0" x2="{x:.1f}" y2="{y:.1f}" stroke="var(--line-soft)"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{11 if i == 0 else 8}" fill="{lf[0]}"{stroke}/>'
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
            f'fill="var(--ink-2)" font-size="12">{n}</text>'
        )
    wheel = "".join(dots)

    return (
        head("主题 · " + site.get("title", ""), 0)
        + topbar(site, 0, "theme")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">Design tokens</div>
    <h1>主题</h1>
    <p class="lede">印刷纸本 + 黑金：纸色做正文，暖黑做书脊（顶栏与页脚），金只用细线和字。
       所有页面都读这一套令牌，点右上角「主题」切深色，验证两种模式都成立。</p>
  </header>

  <section class="sect">
    <div class="sect-head"><h2>色板</h2><span class="hint">OKLCH 里固定明度与彩度，只转色相</span></div>
    <div class="sect-rule"></div>
    <div class="wheel-wrap">
      <svg class="wheel" viewBox="-120 -120 240 240" role="img" aria-label="色相环：五个色板值的位置">
        <circle r="92" fill="none" stroke="var(--line)" stroke-width="1"/>
        <circle r="62" fill="none" stroke="var(--line-soft)" stroke-width="1" stroke-dasharray="2 4"/>
        {wheel}
        <text x="0" y="-4" text-anchor="middle" fill="var(--ink)" font-size="13" font-weight="600">L .50 · C .095</text>
        <text x="0" y="14" text-anchor="middle" fill="var(--muted)" font-size="11">只有色相不同</text>
      </svg>
      <div class="notes">
        <p><b>色相来自主题色。</b>蜜金 74° 是起点；朱 28° 与石绿 158° 被「红涨绿跌」固定；
           靛 250°、梅 318° 把剩下的色环拉开。相邻两色的色差都在 7 以上。</p>
        <p><b>明度与彩度固定。</b>文字档 L .50、色块档 L .68（深色分别提到 .77 与 .62），彩度 .09–.10。
           所有颜色一样重、一样艳，所以表格里一列朱一列石绿不会互相抢。</p>
        <p><b>梅是备用。</b>不分配固定含义，只在图表需要第三条系列时使用。</p>
      </div>
    </div>
    <div style="overflow-x:auto;margin-top:24px">
      <table class="pal">
        <thead><tr><th>色板值</th><th>浅色 · 文字</th><th>浅色 · 色块</th>
          <th>深色 · 文字</th><th>深色 · 色块</th><th>用途</th></tr></thead>
        <tbody>{pal_rows}</tbody>
      </table>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>三条规则</h2></div>
    <div class="sect-rule"></div>
    <div class="kpi-grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      <div class="card card-tight">
        <div class="card-h"><h3>数据区里，金只表示指引</h3></div>
        <p class="card-note">KPI、表格、图表里出现金色，读者就可以默认它是预期或指引。
          数据区里的链接和强调一律用墨色下划线；金色留给顶栏、页脚、小节标记和图表里的预期柱。</p>
      </div>
      <div class="card card-tight">
        <div class="card-h"><h3>判断状态不占色板</h3></div>
        <p class="card-note">跟踪中、成立、存疑、证伪用空心、实心、半圆和删除线区分，颜色都是墨色；
          只有「已到期」借朱，因为它就是警示。这样「成立」不会再和「跌」同为绿色。</p>
      </div>
      <div class="card card-tight">
        <div class="card-h"><h3>浅底在 OKLCH 里混色</h3></div>
        <p class="card-note">提示框底色用 <code>color-mix(in oklch, 色块档 9%, 卡片)</code>，
          不再用 rgba 叠在暖纸色上，所以口径框不会变成灰蓝。</p>
      </div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>字体与数字</h2><span class="hint">数字等宽 + 同宽数字；大数字用衬线</span></div>
    <div class="sect-rule"></div>
    <h1>标题 H1</h1><h2>标题 H2</h2><h3>标题 H3</h3>
    <p>正文 14.5px，行高 1.72。中文回退栈 PingFang SC / Noto Sans SC / Microsoft YaHei；
       大数字用 Cambria / Georgia，报表味道来自字形而不是加粗。
       <span class="num">1,234.56</span> 与 <span class="num">-3.28%</span> 纵向对齐。</p>
    <p><span class="up num">+2.17pt</span> · <span class="down num">-1.86%</span> ·
       <span class="actual num">730 bn</span> · <span class="guide num">1,051 bn</span></p>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>KPI 卡</h2><span class="hint">数字用衬线，单位用等宽</span></div>
    <div class="sect-rule"></div>
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-k">股东总回报</div>
        <div class="kpi-v up">+2,795<span class="u">%</span></div>
        <div class="kpi-d">×28.9 市值 233 → 7,003 亿</div>
        <div class="kpi-asof">2023-01-31 → 2026-10-26</div></div>
      <div class="kpi"><div class="kpi-k">PE_NTM</div>
        <div class="kpi-v">11.71<span class="u">x</span></div>
        <div class="kpi-d">滚动 250 日分位 0.0%</div>
        <div class="kpi-asof">数据截至 2026-10-26</div></div>
      <div class="kpi"><div class="kpi-k">2026 四家实际</div>
        <div class="kpi-v actual">730<span class="u">bn</span></div>
        <div class="kpi-d">同公司组年内上修 <span class="up num">+10.9%</span></div>
        <div class="kpi-asof">数据截至 2026-10-29</div></div>
      <div class="kpi"><div class="kpi-k">2027 指引外推</div>
        <div class="kpi-v guide">1,051<span class="u">bn</span></div>
        <div class="kpi-d">不是公司指引</div>
        <div class="kpi-asof">仅供情景参考</div></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>表格</h2><span class="hint">账本式：上下墨线，中间发丝线</span></div>
    <div class="sect-rule"></div>
    <div class="table-wrap"><table class="table">
      <thead><tr><th>年</th><th class="n">市值（亿）</th><th class="n">E_NTM（亿）</th><th class="n">PE_NTM</th><th class="n">盈利 pp</th><th class="n">估值 pp</th><th class="n">总回报</th></tr></thead>
      <tbody>
        <tr><td>2023</td><td class="n">233 → 906</td><td class="n">15.2 → 36.5</td><td class="n">15.3x → 24.8x</td><td class="n up">+87.6</td><td class="n up">+48.2</td><td class="n up">+288.7%</td></tr>
        <tr><td>2024</td><td class="n">888 → 1,385</td><td class="n">36.6 → 89.4</td><td class="n">24.3x → 15.5x</td><td class="n up">+89.3</td><td class="n down">-44.9</td><td class="n up">+56.7%</td></tr>
        <tr><td>2025</td><td class="n">1,369 → 6,778</td><td class="n">89.4 → 189.8</td><td class="n">15.3x → 35.7x</td><td class="n up">+75.3</td><td class="n up">+84.7</td><td class="n up">+161.0%</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>提示框</h2><span class="hint">细框 + 小标签；只有风险铺一层极淡底</span></div>
    <div class="sect-rule"></div>
    <div class="stack">
      <div class="callout"><div class="co-h">结论</div><p>默认样式：细框，无底色。用于普通结论。</p></div>
      <div class="callout info"><div class="co-h">口径</div><p>靛色框说明数据口径与算法假设；底色是在 OKLCH 里混出来的，不会发灰。</p></div>
      <div class="callout risk"><div class="co-h">风险</div><p>朱色框用于风险与失效条件，是唯一允许铺底的提示框。</p></div>
      <div class="callout method"><div class="co-h">方法</div><p>方法说明用次级纸底，不占用色板。</p></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>标签与判断状态</h2><span class="hint">形状区分，不借行情色</span></div>
    <div class="sect-rule"></div>
    <div class="row" style="margin-bottom:12px">
      <span class="tag">标签</span><span class="tag accent">强调标签</span>
      <span class="tag-date num">2026-10-26</span>
    </div>
    <div class="row">
      <span class="badge track">跟踪中</span><span class="badge hold">成立</span>
      <span class="badge doubt">存疑</span><span class="badge dead">证伪</span>
      <span class="badge overdue">已到期</span>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>论点卡</h2><span class="hint">首页「在跟踪的判断」用的就是这个</span></div>
    <div class="sect-rule"></div>
    <div class="thesis-list">
      <div class="thesis st-track"><div class="th-claim">共识线的上涨大部分是日历滚动，不是分析师改模型。</div>
        <div class="th-badges"><span class="badge track">跟踪中</span></div>
        <div class="th-foot"><span>中际旭创 · 事后归因</span><span>下次检查 <span class="num">2027-01-31</span></span></div></div>
      <div class="thesis st-overdue"><div class="th-claim">这条已经过了检查日期，会被标红。</div>
        <div class="th-badges"><span class="badge overdue">已到期</span><span class="badge doubt">存疑</span></div>
        <div class="th-foot"><span>示例</span><span>下次检查 <span class="num">2026-01-01</span>（逾期 320 天）</span></div></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>图表容器</h2><span class="hint">标题 + 副标题 + 正文 + 来源脚注</span></div>
    <div class="sect-rule"></div>
    <div class="chart-card">
      <div class="chart-title">图一 · 北美四家 capex（十亿美元）</div>
      <div class="chart-sub">实际值用靛，指引与外推用蜜金虚线框。</div>
      <div class="chart-body">
        <svg viewBox="0 0 320 150" style="width:100%;height:auto" role="img" aria-label="capex 实际与指引">
          <line x1="0" y1="124" x2="320" y2="124" stroke="var(--line)"/>
          <rect x="18"  y="99" width="44" height="25"  rx="2" fill="var(--actual-f)"/>
          <rect x="96"  y="78" width="44" height="46"  rx="2" fill="var(--actual-f)"/>
          <rect x="174" y="49" width="44" height="75"  rx="2" fill="var(--actual-f)"/>
          <rect x="174" y="43" width="44" height="6"   rx="1" fill="var(--guide-f)"/>
          <rect x="252" y="16" width="44" height="108" rx="2" fill="none" stroke="var(--guide-f)" stroke-width="1.5" stroke-dasharray="3 2"/>
          <text x="40"  y="93" text-anchor="middle" fill="var(--actual)" font-size="11" font-weight="600">243</text>
          <text x="118" y="72" text-anchor="middle" fill="var(--actual)" font-size="11" font-weight="600">447</text>
          <text x="196" y="37" text-anchor="middle" fill="var(--actual)" font-size="11" font-weight="600">730</text>
          <text x="274" y="10" text-anchor="middle" fill="var(--guide)"  font-size="11" font-weight="600">1,051</text>
          <text x="40"  y="141" text-anchor="middle" fill="var(--muted)" font-size="11">2024</text>
          <text x="118" y="141" text-anchor="middle" fill="var(--muted)" font-size="11">2025</text>
          <text x="196" y="141" text-anchor="middle" fill="var(--muted)" font-size="11">2026</text>
          <text x="274" y="141" text-anchor="middle" fill="var(--muted)" font-size="11">2027E</text>
        </svg>
      </div>
      <div class="chart-foot"><span>单位：十亿美元</span><span class="src">来源：公司指引汇总 · 数据截至 2026-10-29</span></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>日志正文（Markdown 渲染）</h2></div>
    <div class="sect-rule"></div>
    <div class="prose">
      <h2>今日市场一句话</h2>
      <p>AI 链温度回升到 69，但波动率仍在剧烈档；黄金继续走弱。<a href="research/300308/consensus.html">共识与估值</a>
         的判断没有变化。（日志里写 <code>[[300308-consensus]]</code>，构建时就会变成这样的链接。）</p>
      <blockquote><p>引用块用于摘录原文或自己的旧判断。</p></blockquote>
      <ul><li>支持列表</li><li>支持表格、代码块</li></ul>
    </div>
  </section>
"""
        + foot(site, 0, built_at)
        + script(0)
        + "</body>\n</html>\n"
    )
