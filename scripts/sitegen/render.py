"""页面渲染。所有研究信息都来自 model.load()，模板里不写死任何研究数据（约束 C4）。"""
from __future__ import annotations

import datetime as dt
import math
from html import escape as esc

from . import home
from .model import Entry, Group, Thesis


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
        ("index.html", "今日看板", "today"),
        ("archive.html", "研究档案", "archive"),
        ("theses.html", "判断跟踪", "theses"),
    ]
    links = "".join(
        f'<a href="{up}{h}"' + (' aria-current="page"' if key == current else "") + f'>{label}</a>'
        for h, label, key in nav
    )
    return f"""<a class="skip-link" href="#main">跳到主内容</a>
<div class="topbar">
  <a class="brand" href="{up}index.html">{esc(site.get('title', "Dan's Investment Dashboard"))}</a>
  <nav aria-label="主导航">{links}</nav>
  <span class="spacer"></span>
  <button class="iconbtn" id="theme-btn" type="button" title="切换浅色 / 深色">{home.icon('sun')}<span>明暗</span></button>
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


# --------------------------------------------------------------- 论点卡片

def thesis_card(t: Thesis, depth: int = 0) -> str:
    # 「跟踪中」用 .badge 基类（空心圆），其余状态加修饰类。
    # .track 这类空修饰类已废弃：状态只有四种，基类就是默认态。
    cls = {"成立": "hold", "存疑": "doubt", "证伪": "dead"}.get(t.status, "")
    badge_cls = f"badge {cls}".strip()
    status_badge = f'<span class="{badge_cls}">{esc(t.status)}</span>'
    if t.overdue:
        status_badge = '<span class="badge overdue">已到期</span>' + status_badge
    # AI 初稿：显式标注来源，不假装是自己的判断
    draft_badge = '<span class="badge draft">AI 初稿 · 待改写</span>' if t.draft else ""
    when = '<span class="th-days">—</span><span class="th-unit">未定检查日</span>'
    if t.next_check:
        d = t.days_left
        if d is None:
            big, unit = "—", "检查日"
        elif d < 0:
            big, unit = str(-d), "天 · 已逾期"
        elif d == 0:
            big, unit = "0", "今天检查"
        else:
            big, unit = str(d), "天后检查"
        when = (f'<span class="th-days num">{big}</span><span class="th-unit">{unit}</span>'
                f'<span class="th-date num">{t.next_check.isoformat()}</span>')
    note = f'<p class="th-note">{esc(t.note)}</p>' if t.note else ""
    # 反证条件与动作是判断的三要素之二：一条不可观测的「反证」等于没有反证。
    lines = []
    if t.falsifier:
        lines.append(f'<p class="th-line"><span class="th-k">反证</span>{esc(t.falsifier)}</p>')
    if t.action:
        lines.append(f'<p class="th-line"><span class="th-k">动作</span>{esc(t.action)}</p>')
    extra = ""
    if lines:
        extra = '<div class="th-extra">' + "".join(lines) + '</div>'
    # 草稿缺反证 / 动作时把缺口写出来：页面上的一条待办，比默默感动好。
    # 只对还在跟踪的草稿提示——已结算的判断改不改都不影响下一步。
    if t.draft and t.status in ("跟踪中", "存疑") and (not t.falsifier or not t.action):
        gaps = [n for n, v in (("可观测的反证条件", t.falsifier), ("决策动作", t.action)) if not v]
        extra += '<p class="th-gap">待补：' + "、".join(gaps) + '</p>'
    return f"""<article class="thesis {t.css}">
  <div class="th-when">{when}</div>
  <div class="th-body">
    <p class="th-claim">{esc(t.claim)}</p>
    {note}{extra}
    <a class="th-src" href="{href(t.entry_url, depth)}">{esc(t.entry_title)}</a>
  </div>
  <div class="th-badges">{status_badge}{draft_badge}</div>
</article>"""


# --------------------------------------------------------------- 首页

def research_card(e: Entry, show_group: str | None = None, depth: int = 0) -> str:
    """整张卡片就是链接。日期只是标注文字，不再单独做按钮（避免嵌套 a）。"""
    asof = f'<span>数据截至 <span class="num">{esc(e.data_asof)}</span></span>' if e.data_asof else ""
    grp = f'<span class="tag accent">{esc(show_group)}</span>' if show_group else ""
    target = ' target="_blank" rel="noopener"' if e.external else ""
    arrow = '<span class="ext" aria-label="（独立站点）">↗</span>' if e.external else ""
    return f"""<a class="rcard" href="{href(e.url, depth)}"{target} data-topics="{esc('|'.join(e.topics))}" data-group="{e.group}">
  <span class="r-date num">{e.date.isoformat()}</span>
  <span class="r-main">
    <span class="r-title">{esc(e.title)}{arrow}</span>
    <span class="r-sum">{esc(e.summary)}</span>
    <span class="r-foot">{grp}{badges_for(e)}{asof}</span>
  </span>
</a>"""


def group_block(g: Group, depth: int = 0, named: bool = True) -> str:
    """一个分组的两栏账本。named=False 时省掉组名与简介——
    分组名和作用域名一字不差（例如「方法论」）时，重复一遍只是噪声。"""
    code = f'<span class="code">{esc(g.code)}</span>' if g.code else ""
    # 分组自己的主题 + 成员条目的主题并集：否则按「方法论」筛选时，
    # 同组里的方法论条目会连同整组一起被隐藏。
    gtopics = sorted({g.topic, *(t for e in g.entries for t in e.topics)})
    head = ""
    if named:
        head = f"""  <h3><a href="{href(g.url, depth)}">{esc(g.name)}</a></h3>
    {code}
    <p class="group-intro">{esc(g.intro)}</p>
"""
    return f"""<section class="group-block{' flush' if not named else ''}" data-topics="{esc('|'.join(gtopics))}" data-group="{g.id}">
  <header class="group-head">{head}
    <p class="group-meta">{'<a href="' + href(g.url, depth) + '">' if not named else ''}<span class="num">{len(g.entries)}</span> 篇 · 最近更新 <span class="num">{g.latest_date.isoformat()}</span>{'</a>' if not named else ''}</p>
  </header>
  <div class="archive-list">
    {"".join(research_card(e, depth=depth) for e in g.entries)}
  </div>
</section>"""


def index_page(cfg: dict, built_at: str) -> str:
    site = cfg["site"]
    return (
        head("今日看板 · " + site.get("title", ""), 0)
        + topbar(site, 0, "today")
        + '<div class="wrap">'
        + home.today_boards(cfg, built_at)
        + "</div>\n"
        + foot(site, 0, built_at)
        + script(0)
        + "</body>\n</html>\n"
    )


def theses_page(cfg: dict, built_at: str) -> str:
    site = cfg["site"]
    theses = cfg["theses"]
    active = [t for t in theses if t.status in ("跟踪中", "存疑")]
    settled = [t for t in theses if t.status in ("成立", "证伪")]
    drafts = sum(1 for t in theses if t.draft)
    draft_note = ""
    if drafts:
        draft_note = (f' · <span class="num">{drafts}</span> 条为 AI 初稿，待自己重写'
                      f'（<span class="badge draft">AI 初稿</span> 标记，改写后删掉 research.yaml 里的 '
                      f'<code>origin: ai</code> 即可）')
    return (
        head("判断跟踪 · " + site.get("title", ""), 0)
        + topbar(site, 0, "theses")
        + f"""<div class="wrap" id="main">
  <header class="pagehead">
    <h1>判断跟踪</h1>
    <p class="lede">每条判断来自具体研究，保留原文结论与反证条件。</p>
    <div class="meta"><span class="num">{len(active)}</span> 条跟踪中 · <span class="num">{len(settled)}</span> 条已结算{draft_note}</div>
  </header>
  <div class="workbench">{home.review_queue(theses, title="下一组到期", all_link=False, compact=True)}</div>
  <section class="sect">
    <div class="sect-head"><h2>跟踪中</h2><span class="hint">按下次检查日期排列</span></div>
    <div class="thesis-list">{"".join(thesis_card(t) for t in active) or '<div class="empty">没有正在跟踪的判断。</div>'}</div>
  </section>
  <section class="sect">
    <div class="sect-head"><h2>已结算</h2><span class="hint">成立或证伪的旧判断</span></div>
    <div class="thesis-list">{"".join(thesis_card(t) for t in settled) or '<div class="empty">暂无已结算判断。</div>'}</div>
  </section>
</div>
"""
        + foot(site, 0, built_at)
        + script(0)
        + "</body>\n</html>\n"
    )


# --------------------------------------------------------------- 档案（时间线）

def archive_page(cfg: dict, built_at: str) -> str:
    """研究档案：只收进档案的分组（scope 三段），市场看板不在这里。

    只有一个视图：按作用域分段的分组账本。之前那版「时间线表格 + 分组账本」
    是同一批研究列两遍（12 行对 12 张卡，URL 完全重合），删掉了表格。
    """
    site = cfg["site"]
    entries = [e for g in cfg["archive_groups"] for e in g.entries]
    # 筛选按钮只列档案里真的出现过的主题：市场看板已经不在档案里，
    # 再给一个「市场与制度」按钮，点下去只会得到一页空白。
    topics = [t for t in cfg["topics"] if any(t in e.topics for e in entries)]
    filters = '<button type="button" data-filter-topic="" aria-pressed="true">全部</button>' + "".join(
        f'<button type="button" data-filter-topic="{esc(t)}" aria-pressed="false">{esc(t)}</button>'
        for t in topics
    )
    scope_nav = "".join(
        f'<a href="#scope-{esc(s["id"])}">{esc(s["name"])}<span>{len(s["entries"])}</span></a>'
        for s in cfg["scopes"]
    )
    scope_blocks = "".join(
        f'''<section class="scope-block" id="scope-{esc(s["id"])}" aria-labelledby="scope-h-{esc(s["id"])}">
    <header class="scope-head">
      <h2 id="scope-h-{esc(s["id"])}">{esc(s["name"])}</h2>
      <span class="scope-count num">{len(s["entries"])}</span>
      <p>{esc(s["intro"])}</p>
    </header>
    <div class="stack">{"".join(group_block(g, named=(g.name != s["name"])) for g in s["groups"])}</div>
  </section>'''
        for s in cfg["scopes"]
    )
    return (
        head("研究档案 · " + site.get("title", ""), 0)
        + topbar(site, 0, "archive")
        + f"""<div class="wrap" id="main">
  <header class="pagehead">
    <h1>研究档案</h1>
    <p class="lede">按板块 / 个股 / 方法论三段组织，共 <span class="num">{len(entries)}</span> 项。市场看板不在这里，它们就是首页。</p>
  </header>
  <nav class="group-shortcuts scope-nav" aria-label="按作用域浏览">{scope_nav}</nav>
  <div class="archive-toolbar">
    <div class="filters" id="filters">{filters}</div>
    <label class="search-field" for="archive-search">{home.icon('search')}<input id="archive-search" type="search" placeholder="筛选标题、主题或结论…" autocomplete="off"></label>
  </div>
  <div id="archive">{scope_blocks}</div>
  <p class="note-line">视觉验收样本（色板、组件演示）已存档，不在导航里：<a href="archive/theme.html">打开主题样本页</a>。</p>
</div>
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
    <div class="thesis-list">{"".join(thesis_card(t, d) for t in theses)}</div>
  </section>"""
    return (
        head(g.name + " · " + site.get("title", ""), d)
        + topbar(site, d, "")
        + f"""<div class="wrap" id="main">
  <header class="pagehead">
    <h1>{esc(g.name)} {code}</h1>
    <p class="lede">{esc(g.intro)}</p>
    <div class="meta">共 <span class="num">{len(g.entries)}</span> 页 · 最近更新 <span class="num">{g.latest_date.isoformat()}</span> · 主题 {esc(g.topic)}</div>
  </header>
  <div class="archive-list">{"".join(research_card(e, depth=depth) for e in g.entries)}</div>
  {thesis_block}
"""
        + foot(site, d, built_at)
        + script(d)
        + "</body>\n</html>\n"
    )


# --------------------------------------------------------------- 主题样例页

def theme_page(cfg: dict, built_at: str) -> str:
    site = cfg["site"]
    up = "../"  # 主题页存档在 docs/archive/，资源与站内链接比首页深一层

    # 色板：OKLCH 固定明度/彩度、只转色相。浅色文字档 L .50、色块档 L .68；
    # 深色文字档 L .77、色块档 L .62。数值与 theme.css 的令牌一一对应。
    # 对比度一律按「纸底 paper」记，因为细线和字大多落在纸上，不落在卡片上。
    pal = [
        ("蜜", "Honey", 74, ("#835a18", "5.6"), ("#bd8f4e", ""), ("#d7ac72", "9.1"), ("#a77e45", ""),
         "主题色 · 指引 / 预期", "导航高亮、品牌标记、图表里的预期柱"),
        ("朱", "Cinnabar", 28, ("#924c44", "5.8"), ("#cf8075", ""), ("#e89e94", "8.9"), ("#b67168", ""),
         "涨 · 风险侧栏 · 已到期", ""),
        ("石绿", "Jade", 158, ("#29734e", "5.3"), ("#5eab81", ""), ("#82c69e", "9.6"), ("#539771", ""),
         "跌", ""),
        ("靛", "Indigo", 250, ("#356697", "5.5"), ("#679dd4", ""), ("#88b9ec", "9.3"), ("#5b8abb", ""),
         "实际值 · 口径框", ""),
        ("梅", "Plum", 318, ("#7a5186", "5.8"), ("#b284c0", ""), ("#cda2da", "8.9"), ("#9d75a9", ""),
         "图表第三系列", "不分配给业务含义"),
        ("青", "Qing", 204, ("#007378", "5.2"), ("#38abb1", ""), ("#67c6cb", "9.6"), ("#33969b", ""),
         "图表第四系列", "多系列图的后补色"),
        ("赭", "Ochre", 50, ("#8e522e", "5.7"), ("#ca865f", ""), ("#e3a480", "9.0"), ("#b27654", ""),
         "图表第五系列", "多系列图的后补色"),
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

    # 主题页是验收依据，所以它必须把首页与内页「真正在用」的组件全部演一遍。
    # 顺序 = 阅读顺序：色板 → 规则 → 排版 → 今日栏 → 判断行 → 档案行 → 表格 …
    return (
        head("主题 · " + site.get("title", ""), 1)
        + topbar(site, 1, "")
        + f"""<div class="wrap" id="main">
  <header class="pagehead">
    <h1>主题</h1>
    <p class="lede">暖纸、黑金与七色 OKLCH 色板保持不变；首页使用工作台面板承载行情复盘与判断复核，研究档案与内页保留账本式阅读结构。
       这一页是二次存档的视觉验收样本（不在主导航里），展示色板、首页工作台与内页组件。</p>
  </header>

  <section class="sect">
    <div class="sect-head"><h2>色板</h2><span class="hint">OKLCH 里固定明度与彩度，只转色相</span></div>
    <div class="wheel-wrap">
      <svg class="wheel" viewBox="-120 -120 240 240" role="img" aria-label="色相环：七个色板值的位置">
        <circle r="92" fill="none" stroke="var(--line)" stroke-width="1"/>
        <circle r="62" fill="none" stroke="var(--line-soft)" stroke-width="1" stroke-dasharray="2 4"/>
        {wheel}
        <text x="0" y="-4" text-anchor="middle" fill="var(--ink)" font-size="13" font-weight="600">L .50 · C .095</text>
        <text x="0" y="14" text-anchor="middle" fill="var(--muted)" font-size="11">只有色相不同</text>
      </svg>
      <div class="notes">
        <p><b>色相来自主题色。</b>蜜金 74° 是起点；朱 28° 与石绿 158° 被「红涨绿跌」固定；
           靛 250°、梅 318° 把剩下的色环拉开。后补的青 204° 与赭 50° 不承担业务含义，
           只给多系列图表用，所以它们只出现在系列色位置，不出现在正文里。</p>
        <p><b>明度与彩度固定。</b>文字档 L .50、色块档 L .68（深色分别提到 .77 与 .62），彩度 .09–.10。
           所有颜色一样重、一样艳，所以表格里一列朱一列石绿不会互相抢。</p>
        <p><b>对比度按纸底记。</b>下表写的是「文字档 vs 纸底 <code>--paper</code>」的实测值，
           落在卡片上会再高 0.3–0.6，两个底都过 AA。</p>
        <p><b>梅、青、赭是系列色。</b>不分配固定含义，只在图表需要第三、四、五条系列时使用；
           正文与结论区不用这三个色。</p>
      </div>
    </div>
    <div class="table-wrap mt-5">
      <table class="pal">
        <thead><tr><th>色板值</th><th>浅色 · 文字</th><th>浅色 · 色块</th>
          <th>深色 · 文字</th><th>深色 · 色块</th><th>用途</th></tr></thead>
        <tbody>{pal_rows}</tbody>
      </table>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>四条规则</h2><span class="hint">这四条决定了下面的组件长什么样</span></div>
    <div class="cols cols-4">
      <div><h3>工作台有边界</h3>
        <p>首页的独立功能模块（市场概览、复核队列、研究预览）使用细边框面板与留白分隔；内页表格、判断行与档案行仍用墨线分栏，不套多层卡片。</p></div>
      <div><h3>金只表示指引</h3>
        <p>数据区里出现金色，读者就可以默认它是预期或指引。
           链接与强调一律墨色下划线；金色留给顶栏、页脚、小节菱形和图表里的预期柱。</p></div>
      <div><h3>结论不占行情色</h3>
        <p>涨跌色只能落在数字上。结论、状态用形状区分（▲▼●、空心实心半圆删除线），颜色是墨色。
           这样「利空」不会和「跌」撞成同一个绿。</p></div>
      <div><h3>手动才动</h3>
        <p>页面加载时没有任何动画。走势线、数字、区块都在原地，动效只发生在用户操作上，
           而且只动 150–250ms 的颜色与位移。</p></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>首页工作台</h2><span class="hint">首页就是今日看板：两块并列、各自标注数据截至</span></div>
    <div class="workbench">{home.market([e for e in cfg["entries"] if e.raw.get("today")], "theme-market", up="../")}</div>
    <p class="note-line">主趋势线代表历史实际值，因此使用靛色 <code>--actual</code>；两个看板并列展示，走势采样点在无 JS 时也可读。内页使用 <code>.pagehead</code>。</p>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>复核日期带</h2><span class="hint">判断跟踪页顶部的一条带——同页下面就列全量判断，不再重复正文</span></div>
    {home.review_queue(cfg["theses"], up="../", title="下一组到期", all_link=False, compact=True)}
  </section>

  <section class="sect">
    <div class="sect-head"><h2>区块标题</h2><span class="hint">墨线在上；菱形是唯一的小面积金色</span></div>
    <div class="sect-head">
      <h2>今天</h2><span class="hint">右侧灰字是这一块的读法提示</span>
    </div>
    <div class="sect-more"><a href="../archive.html">区块末尾的「还有更多」链接长这样 →</a></div>
    <p class="note-line">页面标题 <code>.pagehead</code> 已经用墨线收尾，紧跟其后的第一个区块标题自动去掉上边线（<code>.pagehead + .sect .sect-head</code>），不会出现两条并行墨线。</p>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>判断行</h2><span class="hint">判断跟踪页与分组页：左栏天数，中间判断，右栏状态</span></div>
    <div class="thesis-list">
      <article class="thesis"><div class="th-when"><span class="th-days num">74</span><span class="th-unit">天后检查</span><span class="th-date num">2027-01-31</span></div>
        <div class="th-body"><p class="th-claim">共识线的上涨大部分是日历滚动，不是分析师改模型。</p><p class="th-note">反证条件或备注写在这里。</p><a class="th-src" href="{up}research/300308/consensus.html">中际旭创 · 共识与估值</a></div>
        <div class="th-badges"><span class="badge">跟踪中</span></div></article>
      <article class="thesis st-overdue"><div class="th-when"><span class="th-days num">320</span><span class="th-unit">天 · 已逾期</span><span class="th-date num">2026-01-01</span></div>
        <div class="th-body"><p class="th-claim">这条已经过了检查日期，天数会变成朱色。</p><a class="th-src" href="{up}index.html">示例</a></div>
        <div class="th-badges"><span class="badge overdue">已到期</span><span class="badge doubt">存疑</span></div></article>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>档案行</h2><span class="hint">研究档案与分组页共用：日期 / 标题 / 一句话 / 标签</span></div>
    <div class="archive-list">
      <a class="rcard" href="{up}research/300308/consensus.html">
        <span class="r-date num">2026-11-04</span>
        <span class="r-main">
          <span class="r-title">中际旭创 · 共识演化与估值分位</span>
          <span class="r-sum">NTM 共识净利 598.2 亿（21 家券商），PE_NTM 11.71x，滚动 250 日分位 0.0%。共识中位始终低估实际（同一天比低 31.6%），但低分位不等于低估 —— 分母仍然是预测。</span>
          <span class="r-foot"><span class="tag">研究</span><span class="tag">个股研究</span><span>数据截至 <span class="num">2026-10-26</span></span></span>
        </span>
      </a>
      <a class="rcard" href="https://jst-well-dan.github.io/gold-dashboard/" target="_blank" rel="noopener">
        <span class="r-date num">2026-11-07</span>
        <span class="r-main">
          <span class="r-title">黄金研究看板<span class="ext" aria-label="（独立站点）">↗</span></span>
          <span class="r-sum">不预测金价，只把黄金正在反映什么摊开：制度层 / 宏观层 / 市场层，41 个数据接口、30+ 指标，每图带最新值与 10 年分位。</span>
          <span class="r-foot"><span class="tag">看板</span><span class="tag">独立站点</span><span class="tag">市场与制度</span><span>数据截至 <span class="num">2026-11-11</span></span></span>
        </span>
      </a>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>筛选与分组</h2><span class="hint">下划线式分段；分组左栏宽屏吸顶</span></div>
    <div class="filters"><button type="button" aria-pressed="true">全部</button><button type="button" aria-pressed="false">市场与制度</button><button type="button" aria-pressed="false">AI 产业链</button><button type="button" aria-pressed="false">个股研究</button><button type="button" aria-pressed="false">方法论</button></div>
    <section class="group-block">
      <header class="group-head">
        <h3><a href="{up}research/300308/index.html">中际旭创</a></h3>
        <span class="code">300308.SZ</span>
        <p class="group-intro">光模块龙头。同一组数据切成不同角度：共识怎么被修上去、估值走到哪个分位、股价涨的是业绩还是倍数。</p>
        <p class="group-meta"><span class="num">6</span> 篇 · 最近更新 <span class="num">2026-11-08</span></p>
      </header>
      <div class="archive-list">
        <a class="rcard" href="{up}research/300308/gk.html">
          <span class="r-date num">2026-11-08</span>
          <span class="r-main">
            <span class="r-title">中际旭创 · 股东总回报三因子归因</span>
            <span class="r-sum">股东总回报 +2795%（×28.9）：盈利 +367.3pp、估值 -27.0pp、股息 -3.75pp。</span>
            <span class="r-foot"><span class="tag">研究</span><span class="tag">个股研究</span><span>数据截至 <span class="num">2026-10-26</span></span></span>
          </span>
        </a>
      </div>
    </section>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>字体与数字</h2><span class="hint">数字等宽 + 同宽数字；大数字用衬线</span></div>
    <h1>标题 H1</h1><h2>标题 H2</h2><h3>标题 H3</h3>
    <p>正文 15px，行高 1.72。中文回退栈 PingFang SC / Noto Sans SC / Microsoft YaHei；
       大数字与首页报头用自托管的 Newsreader 衬线（只含拉丁与数字，中文仍回退系统黑体），
       报表味道来自字形而不是加粗。
       <span class="num">1,234.56</span> 与 <span class="num">-3.28%</span> 纵向对齐。</p>
    <p><span class="up num">+2.17pt</span> · <span class="down num">-1.86%</span> ·
       <span class="actual num">730 bn</span> · <span class="guide num">1,051 bn</span></p>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>KPI 网格</h2><span class="hint">四格并列，竖线分栏，无卡壳</span></div>
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
    <div class="sect-head"><h2>提示框</h2><span class="hint">左侧一条色线 + 小标签；只有风险铺一层极淡底</span></div>
    <div class="stack">
      <div class="callout"><div class="co-h">结论</div><p>默认样式：只有一条灰左线，右、上、下都是空白。用于普通结论。</p></div>
      <div class="callout info"><div class="co-h">口径</div><p>靛色左线说明数据口径与算法假设；左线颜色是唯一信号，不铺底。</p></div>
      <div class="callout risk"><div class="co-h">风险</div><p>朱色左线用于风险与失效条件，是唯一允许铺一层右向渐隐底的提示框。</p></div>
      <div class="callout method"><div class="co-h">方法</div><p>方法说明用最淡的一条线，让位给内容本身。</p></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>标签与判断状态</h2><span class="hint">状态只看形状，不借行情色</span></div>
    <div class="row mb-3">
      <span class="tag">标签</span><span class="tag accent">强调标签</span>
      <span class="tag-date num">2026-10-26</span>
    </div>
    <div class="row">
      <span class="badge">跟踪中</span><span class="badge hold">成立</span>
      <span class="badge doubt">存疑</span><span class="badge dead">证伪</span>
      <span class="badge overdue">已到期</span><span class="badge draft">AI 初稿</span>
    </div>
    <p class="note-line">前五个是判断状态，靠形状区分、不借行情色；最右的 <span class="badge draft">AI 初稿</span>
      不是状态而是一个「来源」标记，所以用虚线框，不参与四种状态的形状语言。</p>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>图表容器</h2><span class="hint">标题 + 副标题 + 正文 + 来源脚注；上下墨线，无卡壳</span></div>
    <div class="chart-card">
      <div class="chart-title">图一 · 北美四家 capex（十亿美元）</div>
      <div class="chart-sub">实际值用靛，指引与外推用蜜金虚线框。</div>
      <div class="chart-body">
        <svg class="fit" viewBox="0 0 960 450" role="img" aria-label="capex 实际与指引">
          <line x1="0" y1="372" x2="960" y2="372" stroke="var(--line)"/>
          <rect x="54"  y="297" width="132" height="75"  rx="2" fill="var(--actual-f)"/>
          <rect x="288" y="234" width="132" height="138" rx="2" fill="var(--actual-f)"/>
          <rect x="522" y="147" width="132" height="225" rx="2" fill="var(--actual-f)"/>
          <rect x="756" y="48"  width="132" height="324" rx="2" fill="none" stroke="var(--guide-f)" stroke-width="1.5" stroke-dasharray="4 3"/>
          <text x="120" y="279" text-anchor="middle" class="cv-num" fill="var(--actual)">243</text>
          <text x="354" y="216" text-anchor="middle" class="cv-num" fill="var(--actual)">447</text>
          <text x="588" y="129" text-anchor="middle" class="cv-num" fill="var(--actual)">730</text>
          <text x="822" y="30"  text-anchor="middle" class="cv-num" fill="var(--guide)">1,051</text>
          <text x="120" y="423" text-anchor="middle" class="cv-ax"  fill="var(--muted)">2024</text>
          <text x="354" y="423" text-anchor="middle" class="cv-ax"  fill="var(--muted)">2025</text>
          <text x="588" y="423" text-anchor="middle" class="cv-ax"  fill="var(--muted)">2026</text>
          <text x="822" y="423" text-anchor="middle" class="cv-ax"  fill="var(--muted)">2027E</text>
        </svg>
      </div>
      <div class="chart-foot"><span>单位：十亿美元</span><span class="src">来源：公司指引汇总 · 数据截至 2026-10-29</span></div>
    </div>
  </section>

  <section class="sect">
    <div class="sect-head"><h2>长文本（阅读区）</h2><span class="hint">.prose：研究笔记、方法说明用这块</span></div>
    <div class="prose">
      <h2>小节标题</h2>
      <p>正文段落，行宽限制在 72ch。<a href="{up}research/300308/consensus.html">站内链接</a>用墨色下划线，不改变行距。</p>
      <blockquote><p>引用块用于摘录原文或自己的旧判断。</p></blockquote>
      <ul><li>支持列表</li><li>支持表格、代码块</li></ul>
    </div>
  </section>
"""
        + foot(site, 1, built_at)
        + script(1)
        + "</body>\n</html>\n"
    )
