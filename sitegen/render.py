"""页面渲染。所有研究信息都来自 model.load()，模板里不写死任何研究数据（约束 C4）。"""
from __future__ import annotations

import datetime as dt
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
        ("journal/", "日志", "journal"),
        ("theme.html", "主题", "theme"),
    ]

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

def today_card(e: Entry) -> str:
    latest = e.latest
    text = latest.get("text") or e.summary
    d = latest.get("date") or e.data_asof
    return f"""<div class="today">
  <div class="t-top">
    <span class="t-name">{esc(e.short or e.title)}</span>
    <span class="tag">{esc(e.kind_label)}</span>
    <span class="t-date num">{esc(str(d))}</span>
  </div>
  <div class="t-text">{esc(text)}</div>
  <a class="t-link" href="{e.url}" target="_blank" rel="noopener">打开看板 →</a>
</div>"""


def research_card(e: Entry, show_group: str | None = None, depth: int = 0) -> str:
    asof = f'<span>数据截至 <span class="num">{esc(e.data_asof)}</span></span>' if e.data_asof else ""
    grp = f'<span class="tag accent">{esc(show_group)}</span>' if show_group else ""
    target = ' target="_blank" rel="noopener"' if e.external else ""
    return f"""<div class="rcard" data-topics="{' '.join(e.topics)}" data-group="{e.group}">
  <div class="r-top">{esc(e.title)}</div>
  <div class="r-sum">{esc(e.summary)}</div>
  <div class="r-foot">
    {grp}{badges_for(e)}
    {asof}
    <a class="tag-date num" href="{href(e.url, depth)}"{target}>{e.date.isoformat()} →</a>
  </div>
</div>"""


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

    topics = cfg["topics"]
    filters = '<button type="button" data-filter-topic="" aria-pressed="true">全部</button>' + "".join(
        f'<button type="button" data-filter-topic="{esc(t)}" aria-pressed="false">{esc(t)}</button>'
        for t in topics
    )

    overdue_note = ""
    if overdue:
        overdue_note = f'<div class="callout risk"><div class="co-h">需要复盘</div>' \
                       f'<p>有 {len(overdue)} 条判断已过检查日期，见下方标红项。</p></div>'

    return (
        head(site.get("title", "Dan's Investment Dashboard"), 0)
        + topbar(site, 0, "today")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">研究入口</div>
    <h1>{esc(site.get("title", ""))}</h1>
    <p class="lede">{esc(site.get("subtitle", ""))} · 已收录 <span class="num">{len(entries)}</span> 项研究、<span class="num">{len(theses)}</span> 条可跟踪判断、<span class="num">{journal_count}</span> 篇复盘。</p>
  </header>

  <section class="sect">
    <div class="sect-head"><h2>今天</h2><span class="hint">每天自动更新的看板，点开是它们的独立站点</span></div>
    <div class="sect-rule"></div>
    <div class="today-grid">{"".join(today_card(e) for e in today_entries) or '<div class="empty">清单里还没有标 today 的看板。</div>'}</div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>今日复盘</h2><span class="hint">一天一个文件，写在 journal/ 目录</span></div>
    <div class="sect-rule"></div>
    <div class="jlist">{journal_block}</div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>在跟踪的判断</h2><span class="hint">{len(tracking)} 条跟踪中 · 按下次检查日期排</span></div>
    <div class="sect-rule"></div>
    {overdue_note}
    <div class="thesis-list">{"".join(thesis_card(t) for t in theses) or '<div class="empty">还没有登记任何论点。</div>'}</div>
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
    swatches = [
        ("paper", "--paper", "页面底"), ("paper-2", "--paper-2", "次级底"),
        ("card", "--card", "卡片"), ("card-2", "--card-2", "卡片次级"),
        ("ink", "--ink", "主文字"), ("ink-2", "--ink-2", "次文字"),
        ("muted", "--muted", "弱文字"), ("dim", "--dim", "更弱"),
        ("line", "--line", "分隔线"), ("line-strong", "--line-strong", "强分隔线"),
        ("accent", "--accent", "强调"), ("accent-bg", "--accent-bg", "强调底"),
        ("up", "--up", "涨（红）"), ("down", "--down", "跌（绿）"),
        ("actual", "--actual", "实际"), ("guide", "--guide", "指引 / 预期"),
        ("st-track", "--st-track", "跟踪中"), ("st-hold", "--st-hold", "成立"),
        ("st-doubt", "--st-doubt", "存疑"), ("st-dead", "--st-dead", "证伪"),
        ("warn", "--warn", "警示"),
    ]
    sw = "".join(
        f'<div class="kpi" style="padding:0;overflow:hidden">'
        f'<div style="height:44px;background:var({var});border-bottom:1px solid var(--line)"></div>'
        f'<div style="padding:8px 10px"><div class="kpi-k">{name}</div>'
        f'<code style="font-size:10.5px">{var}</code>'
        f'<div class="card-note" style="margin-top:2px">{label}</div></div></div>'
        for name, var, label in swatches
    )
    return (
        head("主题样例 · " + site.get("title", ""), 0)
        + topbar(site, 0, "theme")
        + f"""<div class="wrap">
  <header class="pagehead">
    <div class="kicker">Design tokens</div>
    <h1>主题样例</h1>
    <p class="lede">这里展示 <code>theme/theme.css</code> 的全部令牌与组件。所有页面（含托管的研究页）都以这套为准；
       点右上角「主题」切换深色，验证同一套令牌在两种模式下都成立。</p>
  </header>

  <section class="sect">
    <div class="sect-head"><h2>颜色令牌</h2><span class="hint">语义色含义固定，不得挪用</span></div>
    <div class="sect-rule"></div>
    <div class="kpi-grid" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">{sw}</div>
    <div class="callout method" style="margin-top:16px">
      <div class="co-h">用色规则</div>
      <p>涨红跌绿只用于价格与收益的变动；<span class="actual">蓝＝实际值</span>、<span class="guide">琥珀＝指引 / 预期</span>，
      这两组颜色在全站含义不重叠。观点状态（跟踪中 / 成立 / 存疑 / 证伪）用第三组色，避免被读成行情。</p>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>字体与数字</h2><span class="hint">数字一律等宽 + tabular-nums</span></div>
    <div class="sect-rule"></div>
    <h1>标题 H1 · 27px</h1><h2>标题 H2 · 21px</h2><h3>标题 H3 · 17px</h3>
    <p>正文 14.5px，行高 1.72。中文回退栈：PingFang SC / Noto Sans SC / Microsoft YaHei。
       <span class="num">1,234.56</span> 与 <span class="num">-3.28%</span> 用等宽数字，纵向对齐。</p>
    <p><span class="up num">+2.17pt</span> · <span class="down num">-1.86%</span> ·
       <span class="actual num">730 bn</span> · <span class="guide num">1,051 bn</span></p>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>KPI 卡</h2></div>
    <div class="sect-rule"></div>
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-k">股东总回报</div>
        <div class="kpi-v up">+2795<span class="u">%</span></div>
        <div class="kpi-d">×28.9 市值 233 → 7,003 亿</div>
        <div class="kpi-asof">2023-01-31 → 2026-10-26</div></div>
      <div class="kpi"><div class="kpi-k">PE_NTM</div>
        <div class="kpi-v">11.71<span class="u">x</span></div>
        <div class="kpi-d">滚动 250 日分位 0.0%</div>
        <div class="kpi-asof">数据截至 2026-10-26</div></div>
      <div class="kpi"><div class="kpi-k">2026 四家指引合计</div>
        <div class="kpi-v actual">730<span class="u">bn</span></div>
        <div class="kpi-d">同公司组年内上修 <span class="up num">+10.9%</span></div>
        <div class="kpi-asof">数据截至 2026-10-29</div></div>
      <div class="kpi"><div class="kpi-k">2027 外推</div>
        <div class="kpi-v guide">1,051<span class="u">bn</span></div>
        <div class="kpi-d">不是公司指引</div>
        <div class="kpi-asof">仅供情景参考</div></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>表格</h2><span class="hint">表头吸顶 · 数字右对齐</span></div>
    <div class="sect-rule"></div>
    <div class="table-wrap"><table class="table">
      <thead><tr><th>年</th><th class="n">市值（亿）</th><th class="n">E_NTM（亿）</th><th class="n">PE_NTM</th><th class="n">盈利贡献 pp</th><th class="n">估值贡献 pp</th><th class="n">总回报</th></tr></thead>
      <tbody>
        <tr><td>2023</td><td class="n">233 → 906</td><td class="n">15.2 → 36.5</td><td class="n">15.3x → 24.8x</td><td class="n up">+87.6</td><td class="n up">+48.2</td><td class="n up">+288.7%</td></tr>
        <tr><td>2024</td><td class="n">888 → 1,385</td><td class="n">36.6 → 89.4</td><td class="n">24.3x → 15.5x</td><td class="n up">+89.3</td><td class="n down">-44.9</td><td class="n up">+56.7%</td></tr>
        <tr><td>2025</td><td class="n">1,369 → 6,778</td><td class="n">89.4 → 189.8</td><td class="n">15.3x → 35.7x</td><td class="n up">+75.3</td><td class="n up">+84.7</td><td class="n up">+161.0%</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>提示框</h2></div>
    <div class="sect-rule"></div>
    <div class="stack">
      <div class="callout"><div class="co-h">结论</div><p>默认样式用于普通结论。</p></div>
      <div class="callout info"><div class="co-h">口径</div><p>蓝框用于说明数据口径与算法假设。</p></div>
      <div class="callout risk"><div class="co-h">风险</div><p>红框用于风险与失效条件。</p></div>
      <div class="callout method"><div class="co-h">方法</div><p>琥珀框用于方法说明。</p></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>标签与状态徽标</h2></div>
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
      <div class="chart-title">图一 · NTM 共识净利</div>
      <div class="chart-sub">未来 12 个月净利预测；变化来自预测修订、日历滚动与机构进出。</div>
      <div class="chart-body"><div class="empty" style="padding:48px">（图表放这里）</div></div>
      <div class="chart-foot"><span>单位：亿元</span><span class="src">来源：tushare report_rc · 数据截至 2026-10-26</span></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>日志正文（Markdown 渲染）</h2></div>
    <div class="sect-rule"></div>
    <div class="prose">
      <h2>今日市场一句话</h2>
      <p>AI 链温度回升到 69，但波动率仍在剧烈档；黄金继续走弱。<code>[[300308-consensus]]</code> 的判断没有变化。</p>
      <blockquote><p>引用块用于摘录原文或自己的旧判断。</p></blockquote>
      <ul><li>支持列表</li><li>支持表格、代码块</li></ul>
    </div>
  </section>
"""
        + foot(site, 0, built_at)
        + script(0)
        + "</body>\n</html>\n"
    )
