#!/usr/bin/env python3
"""把 11 个研究页的源文件接进 theme.css / research.css 的令牌体系。

为什么要一个脚本：11 个页面里有 270 多个颜色字面量、150 多个圆角与阴影，
手工改既慢又容易漏；而它们的语义高度重复（面板底、次级文字、发丝线、系列色）。

三步改写（幂等，可重复跑）：
  1) <style> 块：hex → var(--token)，圆角 → --r-sm/--r-md/--r-lg，删 box-shadow
  2) 页面自己的 <script>（不碰 ECharts 打包体）："#hex" → hx("#hex")，
     配一个每页一个的 TOKENS 表，运行时读令牌，所以跟随明暗切换
  3) <head> 里注入 theme.css / research.css / 切肤重载脚本

用法：
    python scripts/research_theme_apply.py --check      # 只报告，不写
    python scripts/research_theme_apply.py              # 就地改写
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ------------------------------------------------------------------ 分组的令牌表
# 值写的是「语义角色」，不是颜色。映射过去以后，明暗由 theme.css 决定。
# A 组：原 Tokyo Night 深色（绿涨红跌）
A_MAP = {
    # 基底
    "#0b0f14": "paper", "#0b0f16": "paper", "#0b1017": "paper",
    "#121821": "card", "#111722": "card",
    "#151d29": "card-2",
    "#232c38": "line", "#222c3a": "line", "#1b2431": "line-soft",
    "#e6edf3": "ink",
    "#8b98a8": "muted", "#8b98a9": "muted",
    "#63707f": "dim", "#5c6a7a": "dim", "#7a8290": "dim", "#5a6a7e": "dim",
    # 系列色（旧名字）
    "#7aa2f7": "actual",       # blue → 靛（实际值）
    "#7dcfff": "series-4",     # cyan → 青
    "#bb9af7": "series-3",     # purple → 梅
    "#e0af68": "guide",        # orange → 蜜（指引）
    "#e8c07d": "brand",        # gold
    "#2ac3de": "series-4",
    # 涨跌：旧页绿涨红跌 → 主题红涨绿跌（A 股）
    "#9ece6a": "up",           # green（正）→ 朱
    "#f7768e": "down",         # red（负）→ 石绿
    # 次级文字 / 强调
    "#c3cedb": "ink-2", "#c9d4e0": "ink-2", "#dbe4ee": "ink-2",
    "#eef2f6": "ink", "#c0caf5": "ink", "#c6d2df": "ink-2",
    "#a9c6ff": "actual", "#8ba8d8": "actual", "#4a6099": "actual",
    "#8a97a8": "muted", "#7b8ea8": "muted", "#7b8794": "muted",
    "#7a8699": "dim", "#5f7a9b": "muted",
    "#e8d9c0": "ink-2",        # warn 文字
    "#c9a25f": "guide", "#7fae5b": "down",
    # 线 / 边框
    "#3a4b62": "line-strong", "#33415a": "line-strong", "#33445c": "line-strong",
    "#3d4d63": "line-strong", "#42536a": "line-strong", "#4d5d70": "line-strong",
    "#4c5765": "line-strong", "#4d6076": "line-strong", "#55687f": "line-strong",
    "#3f4d5e": "line", "#414d5f": "line", "#2c3f5a": "line", "#2a3a4d": "line",
    "#2f4a6d": "line-strong",
    "#1a2331": "line-soft", "#1b2432": "line-soft", "#2a3646": "line-soft",
    "#2a3441": "line-soft", "#2a3444": "line-soft", "#243244": "line-soft",
    "#2c3a4a": "line-soft",
    # 次级面板 / 悬停面
    "#101822": "card-2", "#141b25": "card-2", "#141b26": "card-2",
    "#131a24": "card-2", "#131a25": "card-2", "#16202e": "card-2",
    "#161e28": "card-2", "#161e29": "card-2", "#161f2b": "card-2",
    "#1b2632": "card-2", "#1b2230": "card-2", "#182231": "card-2",
    "#1d2837": "card-2", "#1d2a3d": "card-2",
    "#0d1319": "paper-2",
    # 通用
    "#ffffff": "card", "#eeeeee": "line-soft", "#1c2531": "line-soft",
    # 警示 / 选中
    "#1a1721": "warn-bg", "#221d18": "warn-bg", "#242021": "warn-bg",
    "#8a6f3a": "accent-line", "#3d5a80": "actual-f", "#5d6b7d": "line-strong",
    "#3f5568": "line-strong",
}

# B 组：靛紫（#6366f1）+ 灰白
B_MAP = {
    "#eef2ff": "actual-bg",     # 浅靛底
    "#fafaff": "actual-bg",
    "#f8f9ff": "actual-bg",
    "#6366f1": "actual-f",      # 靛边框
    "#4338ca": "actual",        # 靛文字
    "#d1d5db": "line-strong",   # 控件边框
    "#4b5563": "ink-2",
    "#555555": "ink-2", "#555": "ink-2",
    "#666666": "muted", "#666": "muted",
    "#888888": "dim", "#888": "dim",
    "#999999": "dim", "#999": "dim",
    "#bbb": "line-strong", "#ccc": "line", "#ddd": "line-soft",
    "#eee": "line-soft", "#f0f0f0": "line-soft", "#f2f3f5": "line-soft",
    "#f3f4f6": "line-soft",
    "#fafafa": "card-2", "#f7f7f8": "paper",
    "#ffffff": "card", "#fff": "card",
    "#222222": "ink", "#222": "ink",
    "#333333": "ink", "#333": "ink",
    "#444444": "ink-2", "#444": "ink-2",
    "#000000": "ink", "#000": "ink",
    "#f59e0b": "guide-f",       # 警示橙
    "#fff7ed": "guide-bg",
    # 状态：调平通过 / 不通过（不是涨跌，用形状语义）
    "#54a24b": "down",
    "#e45756": "up",
}

# C 组：capex（浅色纸本，涨跌是绿涨红跌，系列色已近）
C_MAP = {
    "#faf9f6": "paper", "#f4f2ec": "card-2", "#ffffff": "card", "#fff": "card",
    "#191813": "ink", "#4a4842": "ink-2", "#6d6b64": "muted",
    "#e4e0d7": "line", "#d3cec1": "line-strong",
    "#2f6fb3": "actual", "#1c7a4d": "up", "#b02a1c": "down",
    "#b8791a": "guide", "#6b6a66": "flat",
    "#7a5cc4": "series-3",
    "#121310": "paper", "#1a1b17": "card", "#22231d": "card-2",
    "#f0eee6": "ink", "#c3c0b5": "ink-2", "#aaa69b": "muted",
    "#2c2d26": "line", "#3a3b32": "line-strong",
    "#6ba6e8": "actual", "#e0a94a": "guide", "#4dc78d": "up",
    "#f0796b": "down", "#9a978d": "flat", "#a98cf0": "series-3",
    "#0f8b8d": "series-4", "#8a93a6": "muted",
}

# B 组 JS 里的 ECharts / Vega 调色盘：按色系收敛到主题的五个系列色
# 顺序有意义：同色系不同深浅映射到同一个令牌，图例里本来就用同一种颜色的不同档
B_JS_MAP = {
    "#4c78a8": "actual", "#2c5f8a": "actual", "#316bf3": "actual",
    "#5470c6": "actual", "#4992ff": "actual", "#006edd": "actual",
    "#5793f3": "actual", "#4d587d": "actual", "#8fb0f7": "actual",
    "#d2dbee": "actual-bg", "#a4b1d7": "actual-bg", "#91b7f2": "actual-bg",
    "#eef1fa": "actual-bg", "#e0e6f1": "actual-bg", "#dae1f5": "actual-bg",
    "#f4f7fd": "actual-bg", "#c5cbe3": "actual-bg",
    "#e45756": "up", "#ee6666": "up", "#f64e56": "up", "#eb5454": "up",
    "#c23531": "up", "#c62828": "up", "#bf444c": "up", "#fd7b5f": "up",
    "#ff6e76": "up", "#fb7293": "up", "#e062ae": "up",
    "#54a24b": "down", "#91cc75": "down", "#3ba272": "down", "#47b262": "down",
    "#54ea92": "down", "#10b981": "down", "#2f7d32": "down",
    "#05c091": "down", "#7cffb2": "down",
    "#f2a900": "guide", "#fac858": "guide", "#ffdb5c": "guide",
    "#e7bcf3": "guide", "#f6efa6": "guide-bg", "#ffd85c": "guide",
    "#d88273": "guide-f", "#ff9f7f": "guide-f", "#ff8a45": "guide-f",
    "#b3541e": "guide",
    "#b279a2": "series-3", "#9a60b4": "series-3", "#ea7ccc": "series-3",
    "#8d48e3": "series-3", "#dd79ff": "series-3", "#9d96f5": "series-3",
    "#8378ea": "series-3", "#e690d1": "series-3",
    "#72b7b2": "series-4", "#73c0de": "series-4", "#37a2da": "series-4",
    "#32c5e9": "series-4", "#67e0e3": "series-4", "#17becf": "series-4",
    "#0d7f8f": "series-4", "#58d9f9": "series-4", "#3e98c5": "series-4",
    "#8da0cb": "series-5", "#fc8452": "series-5", "#fddd60": "series-5",
    "#9fe6b8": "series-5",
    "#9aa5b1": "muted", "#6e7079": "muted", "#71708a": "muted",
    "#817f91": "muted", "#63677a": "muted", "#b9b8ce": "muted",
    "#b0b6c3": "muted", "#b9bec9": "muted", "#acb8d1": "muted",
    "#212121": "ink", "#464646": "ink-2", "#2f4554": "ink-2",
    "#484753": "ink-2",
    "#e5e7eb": "line", "#100c2a": "paper", "#20203b": "card-2",
    "#353450": "line", "#314656": "line", "#000000": "ink",
    "#4338ca": "actual", "#a5b4fc": "actual-f",
    "#b0b7c3": "muted",
}

GROUPS = {
    "A": A_MAP,
    "B": B_MAP,
    "C": C_MAP,
}

# B 组的 JS 单独一张表（ECharts 调色盘）
JS_EXTRA = {"B": B_JS_MAP}

# ------------------------------------------------------------------ CSS 改写

RADIUS_TOKENS = [
    # (阈值下限, 令牌)：圆角越大越像面板
    (11, "var(--r-lg)"),
    (6, "var(--r-md)"),
    (1, "var(--r-sm)"),
]


def _norm_keys(mapping: dict[str, str]) -> dict[str, str]:
    """把 #eee 这种三位写法展开成 #eeeeee，查表统一按六位。"""
    out = {}
    for k, v in mapping.items():
        key = k.lower()
        if len(key) == 4:
            key = "#" + "".join(c * 2 for c in key[1:])
        out[key] = v
    return out


CSS_MAPS = {g: _norm_keys(m) for g, m in GROUPS.items()}
JS_MAPS = {g: _norm_keys({**m, **JS_EXTRA.get(g, {})}) for g, m in GROUPS.items()}


def css_map_for(group: str) -> dict[str, str]:
    return CSS_MAPS[group]


def rewrite_css(css: str, mapping: dict[str, str], stats: dict) -> str:
    """把 CSS 里的 hex 换成 var(--token)，圆角换成令牌，删掉投影。"""

    def sub_hex(m: re.Match) -> str:
        hx = m.group(0).lower()
        hx6 = hx if len(hx) == 7 else "#" + "".join(c * 2 for c in hx[1:])
        tok = mapping.get(hx6)
        if tok is None:
            stats["unmapped_css"][hx6] = stats["unmapped_css"].get(hx6, 0) + 1
            return m.group(0)
        stats["mapped_css"] += 1
        return f"var(--{tok})"

    css = re.sub(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", sub_hex, css)

    def sub_radius(m: re.Match) -> str:
        val = m.group(2).strip()
        if val.startswith("var(") or val == "0" or val == "0px":
            return m.group(0)
        if val == "999px" or val == "50%":
            return m.group(0)          # 圆点 / 胶囊在形状语言里有意义，保留
        num = re.match(r"(\d+(?:\.\d+)?)px", val)
        if not num:
            return m.group(0)
        px = float(num.group(1))
        for lo, tok in RADIUS_TOKENS:
            if px >= lo:
                stats["radius"] += 1
                return f"{m.group(1)}{tok}"
        return m.group(0)

    css = re.sub(r"(border-radius\s*:\s*)([^;}]+)", sub_radius, css)

    def sub_shadow(m: re.Match) -> str:
        val = m.group(1).strip()
        if val == "none" or val.startswith("var(--shadow"):
            return m.group(0)
        stats["shadow"] += 1
        return "box-shadow:none"

    css = re.sub(r"box-shadow\s*:\s*([^;}]+)", sub_shadow, css)

    # 研究页原有的 .pos/.neg 带 !important，会和主题的 .up/.down 打架
    if "!important" in css:
        css = re.sub(r"(!important)", lambda m: m.group(1), css)
    css = re.sub(r"(\.(?:pos|neg|neu|dirup|dirdn)\s*\{[^}]*?)!important", r"\1", css)

    return css


# ------------------------------------------------------------------ JS 改写

PRELUDE = """<script id="research-tokens">
/* 研究页颜色间接层：颜色字面量 → 主题令牌。
   由 scripts/research_theme_apply.py 生成，改色改 theme.css，不要手改这张表。
   令牌在 theme.css 里按明暗两档定义，所以这里读到的值跟着顶栏「明暗」走；
   切换时页面会重载（见 head 里的 research-theme 脚本），SVG / ECharts 自然重画。 */
(function () {
  var TOKENS = __TOKENS__;
  function read() { return getComputedStyle(document.documentElement); }
  window.__rcss = read();
  window.hx = function (v) {
    var t = TOKENS[String(v).toLowerCase()];
    if (!t) return v;
    var c = window.__rcss.getPropertyValue(t).trim();
    return c || v;
  };
  window.rcssVar = function (name) {
    return window.__rcss.getPropertyValue(name).trim();
  };
})();
</script>"""


def rewrite_js(js: str, mapping: dict[str, str], stats: dict) -> str:
    """把页面脚本里的颜色字面量换成令牌查询。

    两种出现位置，两种换法：
      ① 带引号的完整色值 `"#7aa2f7"`：是传给 SVG 属性 / ECharts 选项的值，
         必须是一个真实色值（var() 在那里不生效），换成 hx("#7aa2f7")。
      ② 拼接进 HTML 的内联样式 `style="color:#7aa2f7"`：这里 var() 反而能用，
         换成 var(--actual)，不需要函数调用。
    """

    def sub_quoted(m: re.Match) -> str:
        quote, hx = m.group(1), m.group(2)
        if hx.lower() not in mapping:
            stats["unmapped_js"][hx.lower()] = stats["unmapped_js"].get(hx.lower(), 0) + 1
            return m.group(0)
        stats["mapped_js"] += 1
        return f"hx({quote}{hx}{quote})"

    js = re.sub(r"([\"'])(#[0-9a-fA-F]{6})\1", sub_quoted, js)

    # ② 内联样式里的裸色值：靠上下文判定（color: / solid / background / cssText）
    def sub_bare(m: re.Match) -> str:
        hx = m.group(0).lower()
        tok = mapping.get(hx)
        if tok is None:
            stats["unmapped_js"][hx] = stats["unmapped_js"].get(hx, 0) + 1
            return m.group(0)
        stats["mapped_js"] += 1
        return f"var(--{tok})"

    js = re.sub(r"(?<=[:( ])#[0-9a-fA-F]{6}\b(?=[;\"'\s<])", sub_bare, js)
    return js


def build_tokens(mapping: dict[str, str]) -> str:
    items = ", ".join(f'"{k}":"--{v}"' for k, v in sorted(mapping.items()))
    return "{" + items + "}"


# ------------------------------------------------------------------ head 注入

HEAD_LINKS = """<link rel="stylesheet" href="../../assets/theme.css">
<link rel="stylesheet" href="../../assets/research.css">
<script id="research-theme">
/* 研究页沿用站点顶栏的明暗偏好；切换时重载，让内联 SVG 与 ECharts 用新令牌重画。 */
(function () {
  var KEY = 'dan-dash-theme', root = document.documentElement;
  try { var s = localStorage.getItem(KEY); if (s === 'dark' || s === 'light') root.setAttribute('data-theme', s); } catch (e) {}
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


def inject_head(html: str, group: str) -> str:
    if 'id="research-theme"' in html:
        html = re.sub(r'<link rel="stylesheet" href="[^"]*assets/theme\.css">\s*'
                      r'<link rel="stylesheet" href="[^"]*assets/research\.css">\s*'
                      r'<script id="research-theme">.*?</script>\s*', "", html, flags=re.S)
    depth = "../../"
    block = HEAD_LINKS.replace("../../", depth)
    if re.search(r"</head>", html, re.I):
        return re.sub(r"</head>", block + "</head>", html, count=1, flags=re.I)
    return block + html


# ------------------------------------------------------------------ 主流程

STYLE_RE = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S)
SCRIPT_RE = re.compile(r"(<script(?![^>]*application/json)[^>]*>)(.*?)(</script>)", re.S)


def transform(path: Path, group: str, dry: bool) -> dict:
    html = path.read_text(encoding="utf-8")
    mapping = CSS_MAPS[group]
    js_mapping = JS_MAPS[group]
    stats = {"mapped_css": 0, "mapped_js": 0, "radius": 0, "shadow": 0,
             "unmapped_css": {}, "unmapped_js": {}, "scripts": 0}

    def css_repl(m: re.Match) -> str:
        return m.group(1) + rewrite_css(m.group(2), mapping, stats) + m.group(3)

    html = STYLE_RE.sub(css_repl, html)

    def js_repl(m: re.Match) -> str:
        body = m.group(2)
        if len(body) > 200_000:      # ECharts 打包体，不动
            return m.group(0)
        stats["scripts"] += 1
        return m.group(1) + rewrite_js(body, js_mapping, stats) + m.group(3)

    html = SCRIPT_RE.sub(js_repl, html)

    # 颜色间接层：插在第一个页面脚本之前
    prelude = PRELUDE.replace("__TOKENS__", build_tokens(js_mapping))
    if 'id="research-tokens"' not in html:
        m = SCRIPT_RE.search(html)
        if m:
            html = html[: m.start()] + prelude + "\n" + html[m.start():]

    html = inject_head(html, group)

    if not dry:
        path.write_text(html, encoding="utf-8")
    return stats


PLAN = {
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/report_300308_attribution.html": "A",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/report_300308_consensus.html": "A",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/report_300308_gk.html": "A",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/report_300308_stages.html": "A",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/300502/report_300502_consensus.html": "A",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/300502/report_300502_gk_2026YTD.html": "A",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/report_300308_structure.html": "B",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/report_300308_structure_q.html": "B",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/300502/report_300502_structure.html": "B",
    "E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/30_页面/300502/report_300502_structure_q.html": "B",
    "E:/Python_Doc/Investment/20261030 capex_tracker/capex_tracker.html": "C",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只报告，不写文件")
    ap.add_argument("--only", help="只处理文件名含该串的页面")
    args = ap.parse_args()

    total = {"mapped_css": 0, "mapped_js": 0, "radius": 0, "shadow": 0,
             "unmapped_css": {}, "unmapped_js": {}}
    for path_str, group in PLAN.items():
        path = Path(path_str)
        if args.only and args.only not in path.name:
            continue
        if not path.exists():
            print(f"跳过（源文件不存在）：{path}")
            continue
        st = transform(path, group, args.check)
        print(f"[{group}] {path.name:<42} css {st['mapped_css']:>3} js {st['mapped_js']:>3} "
              f"radius {st['radius']:>2} shadow {st['shadow']} 未映射 "
              f"css {len(st['unmapped_css'])} js {len(st['unmapped_js'])}")
        for k in ("mapped_css", "mapped_js", "radius", "shadow"):
            total[k] += st[k]
        for k in ("unmapped_css", "unmapped_js"):
            for hx, n in st[k].items():
                total[k][hx] = total[k].get(hx, 0) + n

    print()
    print(f"合计：CSS {total['mapped_css']} 处、JS {total['mapped_js']} 处、"
          f"圆角 {total['radius']} 处、阴影 {total['shadow']} 处")
    if total["unmapped_css"]:
        print("未映射 CSS 色：", dict(sorted(total["unmapped_css"].items(), key=lambda x: -x[1])))
    if total["unmapped_js"]:
        print("未映射 JS 色：", dict(sorted(total["unmapped_js"].items(), key=lambda x: -x[1])))
    if args.check:
        print("\n（--check：没有写入任何文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
