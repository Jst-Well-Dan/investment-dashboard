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
  /* 由 build 注入：统一顶栏。固定定位 + html padding，避免影响原页面 body 布局。 */
  html { padding-top: 42px !important; }
  #site-topbar {
    position: fixed; inset: 0 0 auto 0; z-index: 2147483000;
    height: 42px; display: flex; align-items: center; gap: 10px;
    padding: 0 14px;
    font: 500 12.5px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
          "Noto Sans SC", "Microsoft YaHei", sans-serif;
    background: #f7f5f0; color: #4b4437; border-bottom: 1px solid #e6ddc9;
    box-shadow: 0 1px 3px rgba(0,0,0,.05);
    -webkit-font-smoothing: antialiased;
  }
  #site-topbar[data-tone="dark"] {
    background: #12161c; color: #c3cedb; border-bottom-color: #232b36;
    box-shadow: 0 1px 3px rgba(0,0,0,.4);
  }
  #site-topbar a { color: inherit; text-decoration: none; opacity: .82; }
  #site-topbar a:hover { opacity: 1; text-decoration: underline; text-underline-offset: 3px; }
  #site-topbar .stb-home { font-weight: 700; }
  #site-topbar .stb-sep { opacity: .32; }
  #site-topbar .stb-title { font-weight: 650; opacity: 1;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #site-topbar .stb-spacer { flex: 1 1 auto; }
  #site-topbar .stb-asof { opacity: .62; font-variant-numeric: tabular-nums;
    font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11.5px; white-space: nowrap; }
  #site-topbar .stb-btn {
    font: inherit; font-size: 11.5px; cursor: pointer;
    background: transparent; color: inherit; opacity: .7;
    border: 1px solid currentColor; border-bottom-color: transparent;
    border-radius: 5px; padding: 1px 8px; line-height: 1.55;
  }
  #site-topbar .stb-btn:hover { opacity: 1; }
  #site-topbar .stb-btn:disabled { opacity: .3; cursor: default; }
  /* 页面自带的吸顶表头要让开顶栏 */
  thead th { top: 42px !important; }
  @media (max-width: 720px) {
    #site-topbar .stb-asof, #site-topbar .stb-group { display: none; }
  }
  @media print { #site-topbar { display: none; } html { padding-top: 0 !important; } }
</style>
"""

TOPBAR_SCRIPT = """
<script id="site-topbar-script">
(function () {
  var bar = document.getElementById('site-topbar');
  if (!bar) return;
  function luma(c) {
    var m = /rgba?\\(([^)]+)\\)/.exec(c || '');
    if (!m) return 1;
    var p = m[1].split(',').map(parseFloat);
    if (p.length > 3 && p[3] === 0) return 1;
    var f = function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(p[0]) + 0.7152 * f(p[1]) + 0.0722 * f(p[2]);
  }
  function sync() {
    var b = getComputedStyle(document.body).backgroundColor;
    if (!b || b === 'rgba(0, 0, 0, 0)' || b === 'transparent') {
      b = getComputedStyle(document.documentElement).backgroundColor;
    }
    bar.setAttribute('data-tone', luma(b) < 0.42 ? 'dark' : 'light');
  }
  sync();
  try {
    var mo = new MutationObserver(sync);
    [document.documentElement, document.body].forEach(function (n) {
      mo.observe(n, { attributes: true, attributeFilter: ['class', 'data-theme', 'style'] });
    });
  } catch (e) {}
})();
</script>
"""


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def topbar_html(entry: Entry, group: Group, up: str, prev: Entry | None, next: Entry | None) -> str:
    asof = f'数据截至 {entry.data_asof}' if entry.data_asof else ""
    parts = [
        f'<div id="site-topbar" data-tone="light">',
        f'<a class="stb-home" href="{up}index.html">← 研究入口</a>',
        f'<span class="stb-sep">/</span>',
        f'<a class="stb-group" href="{up}{group.url}">{_esc(group.name)}</a>',
        f'<span class="stb-sep">/</span>',
        f'<span class="stb-title">{_esc(entry.title)}</span>',
        '<span class="stb-spacer"></span>',
    ]
    if asof:
        parts.append(f'<span class="stb-asof">{_esc(asof)}</span>')
    if prev or next:
        prev_btn = (f'<a class="stb-btn" href="{prev.url.split("/")[-1]}">上一页</a>'
                    if prev else '<button class="stb-btn" disabled>上一页</button>')
        next_btn = (f'<a class="stb-btn" href="{next.url.split("/")[-1]}">下一页</a>'
                    if next else '<button class="stb-btn" disabled>下一页</button>')
        parts += ['<span class="stb-btns" style="display:flex;gap:4px">', prev_btn, next_btn, '</span>']
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

    # 3) 顶栏节点插在真实 <body> 之后；脚本插在「最后一个」</body> 之前。
    #    注意：有的页面把 <body> / </body> 写进了 JS 字符串（打印窗口模板），
    #    用第一个匹配会把脚本塞进字符串里，直接毁掉整段脚本。所以：
    #    - <body> 取第一个（正文一定是第一个）
    #    - </body> 取最后一个，且必须位于第一个 <body> 之后
    m = re.search(r"<body[^>]*>", html, re.I)
    if not m:
        raise RuntimeError(f"{entry.id}: 找不到 <body>，无法注入顶栏")
    bar = topbar_html(entry, group, up, prev, next)
    html = html[: m.end()] + bar + html[m.end():]

    body_end = max((mm.start() for mm in re.finditer(r"</body\s*>", html, re.I)), default=-1)
    if body_end > m.end():
        html = html[:body_end] + TOPBAR_SCRIPT + html[body_end:]
    else:
        html += TOPBAR_SCRIPT
    return html


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
