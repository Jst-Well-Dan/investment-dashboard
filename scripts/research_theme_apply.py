#!/usr/bin/env python3
"""把 11 个研究页的源文件接进 theme 的令牌体系。

为什么要一个脚本：11 个页面里有 600 多个颜色字面量、110 多个圆角、15 处投影，
手工改既慢又容易漏；而它们的语义高度重复（面板底、次级文字、发丝线、系列色）。

改写分四类（幂等，可重复跑）：
  ① <style> 块：hex → var(--token)，圆角 → 令牌，删投影、rgba 浅底换成 color-mix
  ② 页面自己的 <script>（跳过 ECharts 打包体）："#hex" → hx("#hex")，
     配一份每页一份的 TOKENS 表，运行时读令牌，所以跟随明暗切换
  ③ 正文里的内联 style="color:#hex"：CSS 上下文，直接给 var(--token)
  ④ <head> 里注入 tokens.css / research.css / 切肤重载脚本

用法：
    python scripts/research_theme_apply.py --check      # 只报告，不写
    python scripts/research_theme_apply.py              # 就地改写
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NL = "\n"

# ------------------------------------------------------------------ 令牌表
# 值写的是「语义角色」，不是颜色。映射过去以后，明暗由 tokens.css 决定。

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

B_MAP = {
    "#eef2ff": "actual-bg",
    "#fafaff": "actual-bg",
    "#f8f9ff": "actual-bg",
    "#6366f1": "actual-f",
    "#4338ca": "actual",
    "#d1d5db": "line-strong",
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
    "#f59e0b": "guide-f",
    "#fff7ed": "guide-bg",
    # 调节桥的「通过 / 不通过」：不是涨跌，但也用同一对色
    "#54a24b": "down",
    "#e45756": "up",
    "#f2a900": "guide",
    "#10b981": "down",
    "#ecfdf5": "guide-bg",
}

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

# B 组的 ECharts / Vega 调色盘：按色系收敛到主题的五个系列色
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
    "#b0b7c3": "muted",
    "#212121": "ink", "#464646": "ink-2", "#2f4554": "ink-2",
    "#484753": "ink-2",
    "#e5e7eb": "line", "#100c2a": "paper", "#20203b": "card-2",
    "#353450": "line", "#314656": "line", "#000000": "ink",
    "#4338ca": "actual", "#a5b4fc": "actual-f",
}

GROUPS = {"A": A_MAP, "B": B_MAP, "C": C_MAP}
JS_EXTRA = {"B": B_JS_MAP}

# 研究页里的浅底配方：把 rgba 的色相认出来，换成对应令牌的浅混色
RGBA_TO_TOKEN = {
    "rgba(47,111,179,.12)": "actual-f",  "rgba(47,111,179,.1)": "actual-f",
    "rgba(107,166,232,.16)": "actual-f", "rgba(107,166,232,.1)": "actual-f",
    "rgba(184,121,26,.14)": "guide-f",   "rgba(184,121,26,.12)": "guide-f",
    "rgba(224,169,74,.18)": "guide-f",   "rgba(224,169,74,.12)": "guide-f",
    "rgba(99,102,241,.1)": "actual-f",   "rgba(245,158,11,.12)": "guide-f",
    "rgba(28,122,77,.14)": "up",         "rgba(176,42,28,.13)": "down",
    "rgba(122,92,196,.14)": "series-3-f",
}

RADIUS_TOKENS = [(11, "var(--r-lg)"), (6, "var(--r-md)"), (1, "var(--r-sm)")]

HEX_RE = r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b"


def _norm(mapping: dict[str, str]) -> dict[str, str]:
    """三位写法展开成六位，查表统一按六位。"""
    out = {}
    for k, v in mapping.items():
        key = k.lower()
        if len(key) == 4:
            key = "#" + "".join(c * 2 for c in key[1:])
        out[key] = v
    return out


CSS_MAPS = {g: _norm(m) for g, m in GROUPS.items()}
JS_MAPS = {g: _norm({**m, **JS_EXTRA.get(g, {})}) for g, m in GROUPS.items()}

# ------------------------------------------------------------------ CSS 改写

SELF_REF = re.compile(r"--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*(?=[;}])", re.I)


def drop_self_reference(css: str, mapping: dict[str, str], stats: dict) -> str:
    """删掉「令牌定义自己」的声明。

    研究页里写着 `--up:#1c7a4d`。直接换成 `--up:var(--up)` 会在计算值阶段形成
    循环，整条令牌失效。这些名字主题已经定义了，让它们消失即可。
    """
    def sub(m: re.Match) -> str:
        name, hx = m.group(1).lower(), m.group(2).lower()
        if len(hx) == 4:
            hx = "#" + "".join(c * 2 for c in hx[1:])
        if mapping.get(hx) == name:
            stats["dropped"] += 1
            return ""
        return m.group(0)

    return SELF_REF.sub(sub, css)


def rewrite_css(css: str, mapping: dict[str, str], stats: dict) -> str:
    css = drop_self_reference(css, mapping, stats)

    def prop_before(pos: int) -> str:
        seg = css[max(0, pos - 90):pos]
        m2 = re.search(r"([-a-z]+)\s*:\s*[^;{}]*$", seg)
        return m2.group(1) if m2 else ""

    def sub_hex(m: re.Match) -> str:
        hx = m.group(0).lower()
        if len(hx) == 4:
            hx = "#" + "".join(c * 2 for c in hx[1:])
        # 白与黑在文字色和底色两个位置上语义相反：color:#fff 是深色底上最亮的字，
        # 映射成 --card 会让文字消失；底色上的 #fff 才应该是 --card。
        if hx in ("#ffffff", "#000000") and prop_before(m.start()).startswith(("color", "fill", "stroke")):
            stats["mapped_css"] += 1
            return "var(--ink)"
        tok = mapping.get(hx)
        if tok is None:
            stats["unmapped_css"][hx] = stats["unmapped_css"].get(hx, 0) + 1
            return m.group(0)
        stats["mapped_css"] += 1
        return f"var(--{tok})"

    css = re.sub(HEX_RE, sub_hex, css)

    def one_radius(v: str) -> str:
        v = v.strip()
        if v.startswith("var(") or v in ("0", "0px"):
            return v
        if v in ("999px", "50%"):
            return v                   # 圆点 / 胶囊在形状语言里有意义，保留
        num = re.match(r"(\d+(?:\.\d+)?)px$", v)
        if not num:
            return v
        px = float(num.group(1))
        for lo, tok in RADIUS_TOKENS:
            if px >= lo:
                return tok
        return v

    def sub_radius(m: re.Match) -> str:
        # 简写（0 8px 8px 0）逐值处理，否则右半圆角会漏掉
        parts = m.group(2).split()
        out = [one_radius(v) for v in parts]
        if out != parts:
            stats["radius"] += 1
        return f"{m.group(1)}{' '.join(out)}"

    css = re.sub(r"(border-radius\s*:\s*)([^;}]+)", sub_radius, css)

    def sub_shadow(m: re.Match) -> str:
        val = m.group(1).strip()
        if val == "none" or val.startswith("var(--shadow"):
            return m.group(0)
        stats["shadow"] += 1
        return "box-shadow:none"

    css = re.sub(r"box-shadow\s*:\s*([^;}]+)", sub_shadow, css)

    # --shadow 变量本身是「投影配方」，纸本里不再需要
    css = re.sub(r"--shadow\s*:\s*[^;}]+;?", "", css)

    def sub_rgba(m: re.Match) -> str:
        solid = RGBA_TO_TOKEN.get(re.sub(r"\s+", "", m.group(0)))
        if solid:
            stats["rgba"] += 1
            return f"color-mix(in oklch, var(--{solid}) 12%, var(--card))"
        stats["unmapped_rgba"][m.group(0)] = stats["unmapped_rgba"].get(m.group(0), 0) + 1
        return m.group(0)

    css = re.sub(r"rgba?\(([^)]*)\)", sub_rgba, css)

    # 研究页原有的 .pos/.neg 带 !important，会和主题的 .up/.down 打架
    css = re.sub(r"(\.(?:pos|neg|neu|dirup|dirdn)\s*\{[^}]*?)!important", r"\1", css)

    # 删掉空声明（自引令牌被拿掉后会留下 `;;`）
    prev = None
    while prev != css:
        prev = css
        css = re.sub(r";\s*;", ";", css)
        css = re.sub(r"\{\s*;", "{", css)
        css = re.sub(r";\s*\}", ";}", css)
        css = re.sub(r"\{\s*\}", "", css)
    return css


# ------------------------------------------------------------------ JS 改写

PRELUDE = """<script id="research-tokens">
/* 研究页颜色间接层：颜色字面量 → 主题令牌。
   由 scripts/research_theme_apply.py 生成，改色改 tokens.css，不要手改这张表。
   令牌在 tokens.css 里按明暗两档定义，所以这里读到的值跟着顶栏「明暗」走；
   切换时页面会重载（见 head 里的 research-theme 脚本），SVG / ECharts 自然重画。 */
(function () {
  var TOKENS = __TOKENS__;
  window.__rcss = getComputedStyle(document.documentElement);
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

ECHARTS_HOOK = """<script id="research-echarts-tokens">
/* ECharts 的默认文字色写在打包体里（#333 / #666 / #ccc），CSS 改不到。
   所以注册一套读主题令牌的 ECharts 主题，并让 echarts.init 默认就用它：
   主题是 base 层，页面自己的 setOption 只覆盖它显式设过的项。 */
(function () {
  if (!window.echarts || window.echarts.__danTokens) return;
  var css = getComputedStyle(document.documentElement);
  function C(n, fb) { var v = css.getPropertyValue(n).trim(); return v || fb; }
  var ink = C('--ink', '#1c1712'), ink2 = C('--ink-2', '#4a433a'), muted = C('--muted', '#6f685c');
  var line = C('--line', '#e4ddcf'), lineSoft = C('--line-soft', '#ece6da'), card = C('--card', '#fffdf8');
  var axis = {
    axisLine: { lineStyle: { color: line } },
    axisTick: { lineStyle: { color: line } },
    axisLabel: { color: muted },
    splitLine: { lineStyle: { color: lineSoft } },
    nameTextStyle: { color: muted }
  };
  window.echarts.registerTheme('dan', {
    color: [C('--actual'), C('--series-4'), C('--guide'), C('--series-3'), C('--series-5'),
            C('--up'), C('--down'), muted],
    backgroundColor: 'transparent',
    textStyle: { color: ink },
    title: { textStyle: { color: ink }, subtextStyle: { color: muted } },
    legend: { textStyle: { color: ink2 } },
    tooltip: { backgroundColor: card, borderColor: line, textStyle: { color: ink2 } },
    categoryAxis: axis, valueAxis: axis, timeAxis: axis, logAxis: axis,
    line: { label: { color: ink2 } },
    bar: { label: { color: ink2 } },
    sankey: { label: { color: ink }, nodeGap: 10 },
    graph: { label: { color: ink } },
    treemap: { label: { color: ink } }
  });
  var orig = window.echarts.init;
  window.echarts.init = function (dom, theme, opts) {
    return orig.call(this, dom, theme || 'dan', opts);
  };
  window.echarts.__danTokens = true;
})();
</script>"""

STASH = "\x00W{}\x00"


def rewrite_js(js: str, mapping: dict[str, str], stats: dict) -> str:
    """把页面脚本里的颜色字面量换成令牌查询。

    ① 带引号的完整色值 `"#7aa2f7"`：传给 SVG 属性 / ECharts 选项，必须是一个
       真实色值（var() 在那里不生效），换成 hx("#7aa2f7")。
    ② 拼接进 HTML 的内联样式 `style="color:#7aa2f7"`：这里 var() 反而可用。
    """
    def sub_quoted(m: re.Match) -> str:
        quote, hx = m.group(1), m.group(2)
        if hx.lower() not in mapping:
            stats["unmapped_js"][hx.lower()] = stats["unmapped_js"].get(hx.lower(), 0) + 1
            return m.group(0)
        stats["mapped_js"] += 1
        return f"hx({quote}{hx}{quote})"

    # 幂等：已经包好的 hx('#xxx') 先挖出来，改完再放回去，避免 hx(hx(...))
    wrapped: list[str] = []

    def stash(m: re.Match) -> str:
        wrapped.append(m.group(0))
        return STASH.format(len(wrapped) - 1)

    js = re.sub(r"hx\s*\(\s*([\"'])#[0-9a-fA-F]{6}\1\s*\)", stash, js)
    js = re.sub(r"([\"'])(#[0-9a-fA-F]{6})\1", sub_quoted, js)
    js = re.sub(r"\x00W(\d+)\x00", lambda m: wrapped[int(m.group(1))], js)

    def sub_bare(m: re.Match) -> str:
        hx = m.group(0).lower()
        tok = mapping.get(hx)
        if tok is None:
            stats["unmapped_js"][hx] = stats["unmapped_js"].get(hx, 0) + 1
            return m.group(0)
        stats["mapped_js"] += 1
        return f"var(--{tok})"

    return re.sub(r"(?<=[:( ])#[0-9a-fA-F]{6}\b(?=[;\"'\s<])", sub_bare, js)


def build_tokens(mapping: dict[str, str]) -> str:
    items = ", ".join(f'"{k}":"--{v}"' for k, v in sorted(mapping.items()))
    return "{" + items + "}"


# ------------------------------------------------------------------ head 注入

HEAD_LINKS = """<link rel="stylesheet" href="../../assets/tokens.css">
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

HEAD_BLOCK_RE = re.compile(
    r'<link rel="stylesheet" href="[^"]*assets/(?:tokens|theme)\.css">\s*'
    r'<link rel="stylesheet" href="[^"]*assets/research\.css">\s*'
    r'<script id="research-theme">.*?</script>\s*', re.S)


def inject_head(html: str) -> str:
    """把令牌表与切肤脚本插到 <head> 开头。

    插在最前面（页面自己的 <style> 之前）：theme 只做基底与令牌，页面内联样式
    仍然优先——研究页的版式不归主题管。
    """
    if 'id="research-theme"' in html:
        html = HEAD_BLOCK_RE.sub("", html, count=1)
    block = HEAD_LINKS
    m = re.search(r"<head[^>]*>", html, re.I)
    if m:
        return html[: m.end()] + block + html[m.end():]
    return block + html


def strip_own_theme_toggle(html: str, stats: dict) -> str:
    """删掉页面自带的明暗按钮与它那套偏好键（capex 原来有一个）。

    统一走顶栏 #theme-btn，两个开关并存会互相打架。必须按行删：页面里有很多
    `const tb=document.createElement('tbody')`，跨行正则会把整个 init 吃掉。
    """
    lines = html.split(NL)
    out, i, changed = [], 0, False
    while i < len(lines):
        line = lines[i]
        if 'id="theme"' in line and "<button" in line:
            j = i
            while j < len(lines) and "</button>" not in lines[j]:
                j += 1
            i = j + 1
            changed = True
            continue
        if "const tb=$('#theme')" in line:
            j = i
            while j < len(lines) and "ct-theme')" not in lines[j]:
                j += 1
            i = j + 1
            changed = True
            continue
        out.append(line)
        i += 1
    if changed:
        stats["dropped_toggle"] = 1
    return NL.join(out)


# ------------------------------------------------------------------ 主流程

STYLE_RE = re.compile(r"(<style[^>]*>)(.*?)(</style>)", re.S)
SCRIPT_RE = re.compile(r"(<script(?![^>]*application/json)[^>]*>)(.*?)(</script>)", re.S)
OWN_SCRIPTS = re.compile(r'id="research-(tokens|echarts-tokens|theme)"')


def transform(path: Path, group: str, dry: bool) -> dict:
    html = path.read_text(encoding="utf-8")
    mapping = CSS_MAPS[group]
    js_mapping = JS_MAPS[group]
    stats = {"mapped_css": 0, "mapped_js": 0, "mapped_inline": 0,
             "radius": 0, "shadow": 0, "dropped": 0, "rgba": 0, "scripts": 0,
             "dropped_toggle": 0, "echarts_hook": 0,
             "unmapped_css": {}, "unmapped_js": {}, "unmapped_rgba": {}}

    # ① <style>
    def css_repl(m: re.Match) -> str:
        return m.group(1) + rewrite_css(m.group(2), mapping, stats) + m.group(3)

    html = STYLE_RE.sub(css_repl, html)

    # ② 页面脚本（跳过压缩过的 ECharts 打包体，在它后面挂主题适配）
    def js_repl(m: re.Match) -> str:
        if OWN_SCRIPTS.search(m.group(1)):
            return m.group(0)
        body = m.group(2)
        if len(body) > 400_000 and body.count(NL) < 200:
            if "echarts" in body and "research-echarts-tokens" not in html:
                stats["echarts_hook"] = 1
                return m.group(0) + NL + ECHARTS_HOOK
            return m.group(0)
        stats["scripts"] += 1
        return m.group(1) + rewrite_js(body, js_mapping, stats) + m.group(3)

    html = SCRIPT_RE.sub(js_repl, html)

    # ③ 正文内联 style="color:#7dcfff"
    def inline_repl(m: re.Match) -> str:
        attr = m.group(1)

        def hex_sub(mm: re.Match) -> str:
            hx = mm.group(0).lower()
            if len(hx) == 4:
                hx = "#" + "".join(c * 2 for c in hx[1:])
            tok = mapping.get(hx)
            if tok is None:
                stats["unmapped_css"][hx] = stats["unmapped_css"].get(hx, 0) + 1
                return mm.group(0)
            stats["mapped_inline"] += 1
            return f"var(--{tok})"

        return 'style="' + re.sub(HEX_RE, hex_sub, attr) + '"'

    html = re.sub(r'style="([^"]*)"', inline_repl, html)

    # 颜色间接层：插在第一个页面脚本之前
    if 'id="research-tokens"' not in html:
        prelude = PRELUDE.replace("__TOKENS__", build_tokens(js_mapping))
        m = SCRIPT_RE.search(html)
        if m:
            html = html[: m.start()] + prelude + NL + html[m.start():]

    html = strip_own_theme_toggle(html, stats)
    html = inject_head(html)

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

COUNT_KEYS = ("mapped_css", "mapped_js", "mapped_inline", "radius", "shadow",
              "dropped", "rgba", "dropped_toggle", "echarts_hook")
DICT_KEYS = ("unmapped_css", "unmapped_js", "unmapped_rgba")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只报告，不写文件")
    ap.add_argument("--only", help="只处理文件名含该串的页面")
    args = ap.parse_args()

    total = {k: 0 for k in COUNT_KEYS}
    total.update({k: {} for k in DICT_KEYS})

    for path_str, group in PLAN.items():
        path = Path(path_str)
        if args.only and args.only not in path.name:
            continue
        if not path.exists():
            print(f"跳过（源文件不存在）：{path}")
            continue
        st = transform(path, group, args.check)
        print(f"[{group}] {path.name:<42} css {st['mapped_css']:>3} js {st['mapped_js']:>3} "
              f"内联 {st['mapped_inline']:>2} radius {st['radius']:>2} shadow {st['shadow']} "
              f"rgba {st['rgba']:>2} 自引 {st['dropped']:>2} 未映射 "
              f"css {len(st['unmapped_css'])} js {len(st['unmapped_js'])} "
              f"rgba {len(st['unmapped_rgba'])}")
        for k in COUNT_KEYS:
            total[k] += st[k]
        for k in DICT_KEYS:
            for hx, n in st[k].items():
                total[k][hx] = total[k].get(hx, 0) + n

    print()
    print(f"合计：CSS {total['mapped_css']}、JS {total['mapped_js']}、内联 {total['mapped_inline']}、"
          f"圆角 {total['radius']}、阴影 {total['shadow']}、rgba {total['rgba']}、"
          f"自引令牌 {total['dropped']}、页内明暗按钮 {total['dropped_toggle']}、"
          f"ECharts 适配 {total['echarts_hook']}")
    for k, label in (("unmapped_css", "CSS"), ("unmapped_js", "JS"), ("unmapped_rgba", "rgba")):
        if total[k]:
            print(f"未映射 {label}：", dict(sorted(total[k].items(), key=lambda x: -x[1])))
    if args.check:
        print(NL + "（--check：没有写入任何文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
