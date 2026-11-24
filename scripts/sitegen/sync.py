"""把本地研究 HTML 同步进发布目录，并做发布前处理。

三步，缺一不可：
  1. 清洗：抹掉本机绝对路径等不该公开的东西
  2. 注入：统一顶栏（不改原页面布局）
  3. 检查：扫描敏感串，发现问题直接抛错，不静默发布

源文件永远留在原目录，这里是副本（约束 C2）。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .model import Entry, Group

# ---------------------------------------------------------------- 清洗

# Windows 绝对路径：要求「一个字母 + 冒号 + 至少一个反斜杠 + 字母」，
# 这样 CSS 里的 `background:#0b0f14` 不会被误伤（它没有反斜杠）。
# 反斜杠允许连续多个：JSON 里内嵌的 Windows 路径会被转义成 `\\\\`。
WIN_PATH = re.compile(r'(?<![A-Za-z])[A-Za-z]:\\+[^"<>\n\\]{1,400}(?:\\+[^"<>\n\\]{1,400})*')
POSIX_HOME = re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+/[^"<>\n ]{0,300}')

REDACTED = "（本机路径已隐去）"

# 「发布前检查」用的敏感串：命中即中止构建
SECRET_PATTERNS = [
    (re.compile(r'(?<![A-Za-z])[A-Za-z]:\\+[A-Za-z]'), "本机绝对路径"),
    (re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+/'), "本机绝对路径"),
    (re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}'), "GitHub token"),
    (re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}'), "GitHub token"),
    (re.compile(r'\bsk-[A-Za-z0-9]{20,}'), "API key"),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), "AWS key"),
    (re.compile(r'(?i)tushare[_\s-]?(?:api[_\s-]?)?token\s*[:=]\s*["\']?[A-Za-z0-9]{20,}'), "tushare token"),
    (re.compile(r'(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*["\'][A-Za-z0-9]{16,}["\']'), "凭证"),
]


def redact(html: str) -> tuple[str, int]:
    n = 0

    def sub(m):
        nonlocal n
        n += 1
        return REDACTED

    html = WIN_PATH.sub(sub, html)
    html = POSIX_HOME.sub(sub, html)
    return html, n


# ---------------------------------------------------------------- 注入顶栏

TOPBAR_STYLE = """
<style id="site-topbar-style">
  /* 由 build 注入：统一顶栏（黑金带）。固定定位 + html padding，避免影响原页面 body 布局。
     颜色走 tokens.css 的令牌（研究页的 head 里已经引了它），不再写死 hex——
     以前这里是 theme.css 的一份硬编码副本，改色要改两处。 */
  html { padding-top: var(--topbar-h, 44px) !important; }
  #site-topbar {
    position: fixed; inset: 0 0 auto 0; z-index: 2147483000;
    height: var(--topbar-h, 44px); display: flex; align-items: center; gap: 10px;
    padding: 0 14px;
    font: 500 12.5px/1.5 var(--font-sans, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif);
    background: var(--band); color: var(--band-muted);
    border-bottom: 1px solid var(--band-line);
    -webkit-font-smoothing: antialiased;
  }
  #site-topbar > * { white-space: nowrap; }
  #site-topbar .stb-lab { margin-left: 5px; }
  #site-topbar .stb-btn { text-align: center; }
  #site-topbar a { color: inherit; text-decoration: none; opacity: .85; }
  #site-topbar a:hover { opacity: 1; color: var(--band-ink); text-decoration: none; }
  #site-topbar .stb-home { font-weight: 600; }
  #site-topbar .stb-home, #site-topbar .stb-group { color: var(--brand-f); }
  #site-topbar .stb-sep { opacity: .3; }
  #site-topbar .stb-title { font-weight: 600; color: var(--band-ink); opacity: 1;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #site-topbar .stb-spacer { flex: 1 1 auto; }
  #site-topbar .stb-asof { opacity: .62; font-variant-numeric: tabular-nums;
    font-family: var(--font-mono, ui-monospace, Menlo, Consolas, monospace);
    font-size: 11.5px; white-space: nowrap; }
  #site-topbar .stb-btn {
    font: inherit; font-size: 11.5px; cursor: pointer;
    background: transparent; color: inherit; opacity: .7;
    border: 1px solid var(--band-line);
    border-radius: var(--r-sm, 4px); padding: 1px 8px; line-height: 1.55;
  }
  #site-topbar .stb-btn:hover { opacity: 1; border-color: var(--brand-f); color: var(--band-ink); }
  #site-topbar .stb-btn:disabled { opacity: .3; cursor: default; }
  /* 页面自带的栏：顶栏在上面，它就不能再粘一遍，否则两块黑带叠在顶部。
     首页 -> 页内都是单层吸顶（只有站点顶栏），自带那条随页面滚走。
     它的 56px 高度原本是给吸顶留的，现在没这个需要，收紧到 40px。 */
  body.has-site-topbar > .bar { position: static !important; backdrop-filter: none !important;
    border-bottom: 1px solid var(--line); padding: 0 !important; }
  body.has-site-topbar > .bar > .bar-in,
  body.has-site-topbar > .bar > .wrap { height: 40px !important; padding-top: 0 !important;
    padding-bottom: 0 !important; }
  /* 自带栏上「当前页」那条高亮（.btn.on）在托管后是重复信息：顶栏已经写了页面标题 */
  body.has-site-topbar > .bar .btn.on { background: transparent !important;
    border-color: var(--line) !important; color: var(--ink-2) !important; }
  /* 侧栏目录原本吸在自带栏下面，现在改吸在站点顶栏下面 */
  body.has-site-topbar > .shell > .side {
    top: calc(var(--topbar-h, 44px) + 16px) !important;
    max-height: calc(100vh - var(--topbar-h, 44px) - 32px);
  }
  /* 顶栏已经有「明暗」按钮：页面自带的那个不要再摆一份 */
  body.has-site-topbar .theme-toggle { display: none !important; }
  /* 页面自带的吸顶表头要让开顶栏 */
  thead th { top: var(--topbar-h, 44px) !important; }
  @media (max-width: 720px) {
    #site-topbar { gap: 6px; padding: 0 10px; }
    #site-topbar .stb-asof, #site-topbar .stb-group, #site-topbar .stb-sep { display: none; }
    #site-topbar .stb-btns .stb-lab { display: none; }
  }
  @media (max-width: 520px) {
    #site-topbar .stb-lab { display: none; }
    #site-topbar .stb-title { max-width: 46vw; }
  }
  @media print { #site-topbar { display: none; } html { padding-top: 0 !important; } }
</style>
<script id="site-topbar-theme">
/* 顶栏「明暗」按钮 → 与站点同一套偏好键（dan-dash-theme）。
   同步进来的页面没有站点 site.js，所以这里自带一份最小实现；
   页面自己的 theme.js 会在重载时读到同一个键，图跟着令牌一起换色。 */
(function () {
  var root = document.documentElement, KEY = 'dan-dash-theme';
  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest && ev.target.closest('#theme-btn');
    if (!btn) return;
    var dark = root.getAttribute('data-theme') === 'dark' ||
      (!root.getAttribute('data-theme') && window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
    location.reload();
  });
})();
</script>
"""



def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def topbar_html(entry: Entry, group: Group, up: str, prev: Entry | None, next: Entry | None) -> str:
    asof = f'数据截至 {entry.data_asof}' if entry.data_asof else ""
    # 只有会生成分组页的组（scope 非空）才给链接：市场看板这类不进档案的组没有
    # research/<group>/index.html，链过去就是死链。
    if group.scope:
        group_node = f'<a class="stb-group" href="{up}{group.url}">{_esc(group.name)}</a>'
    else:
        group_node = f'<span class="stb-group">{_esc(group.name)}</span>'
    parts = [
        '<div id="site-topbar">',
        f'<a class="stb-home" href="{up}index.html" title="今日看板">←<span class="stb-lab">今日看板</span></a>',
        f'<span class="stb-sep">/</span>',
        group_node,
        f'<span class="stb-sep">/</span>',
        f'<span class="stb-title">{_esc(entry.title)}</span>',
        '<span class="stb-spacer"></span>',
    ]
    if asof:
        parts.append(f'<span class="stb-asof">{_esc(asof)}</span>')
    if prev or next:
        def btn(e: Entry | None, arrow: str, label: str) -> str:
            if e is None:
                return f'<button class="stb-btn" disabled>{arrow}<span class="stb-lab">{label}</span></button>'
            return (f'<a class="stb-btn" href="{e.url.split("/")[-1]}" title="{label}：{_esc(e.short or e.title)}">'
                    f'{arrow}<span class="stb-lab">{label}</span></a>')

        prev_btn = btn(prev, "‹", "上一页")
        next_btn = btn(next, "›", "下一页")
        parts += ['<span class="stb-btns" style="display:flex;gap:4px">', prev_btn, next_btn, '</span>']
    # 明暗切换：研究页的脚本（research-theme）统一监听这个 id，切完重载页面，
    # 让内联 SVG 与 ECharts 用新的令牌重画。
    parts.append('<button class="stb-btn" id="theme-btn" type="button" '
                 'title="切换浅色 / 深色">◐<span class="stb-lab">明暗</span></button>')
    parts.append('</div>')
    return "".join(parts)


def inject(html: str, entry: Entry, group: Group, up: str,
           prev: Entry | None, next: Entry | None) -> str:
    # 1) 标题：以清单为准（原页面可能是「财报可视化」这种无信息标题）
    if re.search(r"<title[^>]*>.*?</title>", html, re.S | re.I):
        html = re.sub(r"<title[^>]*>.*?</title>",
                      lambda m: f"<title>{_esc(entry.title)}</title>", html,
                      count=1, flags=re.S | re.I)
    else:
        html = re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + f"<title>{_esc(entry.title)}</title>",
                      html, count=1, flags=re.I)

    # 2) 顶栏样式放 head 末尾
    if re.search(r"</head>", html, re.I):
        html = re.sub(r"</head>", TOPBAR_STYLE + "</head>", html, count=1, flags=re.I)
    else:
        html = TOPBAR_STYLE + html

    # 3) 顶栏节点插在真实 <body> 之后（顶栏是纯 CSS，不再注入脚本）。
    #    注意：有的页面把 <body> / </body> 写进了 JS 字符串（打印窗口模板），
    #    用第一个匹配会把脚本塞进字符串里，直接毁掉整段脚本。所以：
    #    - <body> 取第一个（正文一定是第一个）
    #    - </body> 取最后一个，且必须位于第一个 <body> 之后
    m = re.search(r"<body[^>]*>", html, re.I)
    if not m:
        raise RuntimeError(f"{entry.id}: 找不到 <body>，无法注入顶栏")
    # 给 body 加标记：页面自带的吸顶栏（.bar / .nav）靠它让开顶栏高度
    body_tag = m.group(0)
    if "has-site-topbar" not in body_tag:
        if "class=" in body_tag:
            body_tag = body_tag.replace('class="', 'class="has-site-topbar ', 1)
        else:
            body_tag = body_tag[:-1] + ' class="has-site-topbar">'
    bar = topbar_html(entry, group, up, prev, next)
    return html[: m.start()] + body_tag + bar + html[m.end():]


# ---------------------------------------------------------------- 检查

def scan(path: Path, display: str) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    problems = []
    for pat, label in SECRET_PATTERNS:
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            problems.append(f"{display}:{line} 发现{label} → {m.group(0)[:80]}")
    return problems


# ---------------------------------------------------------------- 主流程

def sync_entry(entry: Entry, group: Group, docs: Path,
               prev: Entry | None, next: Entry | None) -> dict:
    """复制 + 清洗 + 注入，返回统计信息。"""
    if entry.external or not entry.source:
        return {}
    src: Path = entry.source
    if not src.exists():
        raise FileNotFoundError(f"[research.yaml] {entry.id} 的 source 不存在：{src}")

    raw = src.read_text(encoding="utf-8", errors="strict")
    cleaned, n_redacted = redact(raw)

    depth_prefix = "../../"
    out = docs / entry.url
    out.parent.mkdir(parents=True, exist_ok=True)
    html = inject(cleaned, entry, group, up=depth_prefix, prev=prev, next=next)
    out.write_text(html, encoding="utf-8")

    # 原文件大小，用于在日志里提示「复制了多少」
    return {
        "id": entry.id,
        "src": str(src),
        "out": str(out),
        "bytes": len(html.encode("utf-8")),
        "redacted": n_redacted,
    }
