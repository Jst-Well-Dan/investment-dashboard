#!/usr/bin/env python3
"""生成「今日卡片」方案对比页（design/today-cards.html）。

只是设计稿：不进构建、不被 build.py 引用，用来挑方案用。
数据取自两个看板当前的真实 JSON（2026-11-11 前后）。

    python design/gen_today.py
"""
from __future__ import annotations

import json
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "design" / "today-cards.html"

GOLD_JSON = Path("E:/Python_Doc/Investment/20261107 黄金看板/data/board.json")
GS50_DIR = Path("E:/Python_Doc/Investment/20261029 gs50_dashboard/docs/data")


# ------------------------------------------------------------------ 取数
def load_gold():
    d = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    g = d["hero"]["gold"]
    spark = [(k, v) for k, v in g["spark"]][-40:]
    return {
        "value": g["value"], "date": g["date"], "chg_1d": g["chg_1d"],
        "ytd": g["chg_ytd"], "y1": g["chg_1y"],
        "cny": d["hero"]["gold_cny"]["value"], "cny_1d": d["hero"]["gold_cny"]["chg_1d"],
        "verdict": d["insights"]["verdict"],
        "cycle": d["insights"]["points"][0]["value"],
        "cycle_len": d["insights"]["points"][0]["text"],
        "drawdown": d["insights"]["points"][1]["value"],
        "annual": d["insights"]["points"][1]["text"],
        "outlook": d["hero"]["outlook"]["summary"],
        "drivers": d["hero"]["drivers"],
        "spark": [v for _, v in spark],
        "spark_d0": spark[0][0], "spark_d1": spark[-1][0],
    }


def gs_date(day: str) -> str:
    """20261111 → 11-11"""
    return f"{day[4:6]}-{day[6:]}"


def load_gs50():
    fs = sorted(gs50_dir.glob("*.json"))
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in fs]
    cur = rows[-1]
    return {
        "day": cur["day"], "score": cur["score"], "mood": cur["mood"],
        "median": cur["median"], "excess": cur["excess"], "bench": cur["bench300"],
        "up": cur["up"], "down": cur["down"], "n": cur["n"], "zt": cur["zt"],
        "share": cur["amount_share"], "vol": cur.get("w"),
        "ret5": cur["ret5"], "ret20": cur["ret20"],
        "layers": cur["layers"], "spark": [r["score"] for r in rows[-40:]],
        "delta": cur["score"] - rows[-2]["score"],
        "spark_d0": gs_date(rows[-40]["day"]), "spark_d1": gs_date(cur["day"]),
    }


gs50_dir = GS50_DIR
G = load_gold()
S = load_gs50()


# ------------------------------------------------------------------ 小工具
def fmt(v: float, dp: int = 2) -> str:
    return f"{v:,.{dp}f}"


def sign(v: float, dp: int = 2, suffix: str = "%") -> str:
    return f"{v:+.{dp}f}{suffix}"


def tone(v: float) -> str:
    """A 股口径：正=红(.up)，负=绿(.down)。"""
    return "up" if v > 0 else ("down" if v < 0 else "flat")


def spark_svg(values, uid, w=420, h=54, area=True, positive_color=None):
    lo, hi = min(values), max(values)
    if hi == lo:
        hi = lo + 1
    n = len(values)
    pts = [(i / (n - 1) * w, h - 3 - (v - lo) / (hi - lo) * (h - 6)) for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    stroke = positive_color or "var(--accent)"
    if not area:
        return (f'<svg class="sp" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
                f'<polyline points="{line}" fill="none" stroke="{stroke}" stroke-width="1.6" '
                f'stroke-linejoin="round" stroke-linecap="round"/></svg>')
    first, last = pts[0], pts[-1]
    fill = f'<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="0" y2="1">' \
           f'<stop offset="0" stop-color="{stroke}" stop-opacity=".22"/>' \
           f'<stop offset="1" stop-color="{stroke}" stop-opacity="0"/></linearGradient></defs>'
    return (f'<svg class="sp" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">{fill}'
            f'<path d="M{first[0]:.1f},{h} L{line.replace(" ", " L")} L{last[0]:.1f},{h} Z" fill="url(#g{uid})"/>'
            f'<polyline points="{line}" fill="none" stroke="{stroke}" stroke-width="1.6" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="2.6" fill="{stroke}"/></svg>')


def gauge_band(uid, pct, w=150, h=8):
    """0–100 色带 + 标记点。"""
    x = max(2, min(w - 2, pct / 100 * w))
    return (f'<svg class="band" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            f'<defs><linearGradient id="b{uid}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="var(--down)"/>'
            f'<stop offset=".5" stop-color="var(--guide)"/>'
            f'<stop offset="1" stop-color="var(--up)"/></linearGradient></defs>'
            f'<rect x="0" y="2" width="{w}" height="{h - 4}" rx="2" fill="url(#b{uid})" opacity=".5"/>'
            f'<rect x="{x - 1.5:.1f}" y="0" width="3" height="{h}" rx="1.5" fill="var(--ink)"/></svg>')


def layer_bars(layers):
    """板块分层：横向正负条。"""
    if not layers:
        return ""
    mx = max(abs(v) for v in layers.values()) or 1
    rows = []
    for k, v in layers.items():
        pct = abs(v) / mx * 100
        cls = tone(v)
        rows.append(
            f'<div class="ly-row"><span class="ly-k">{k}</span>'
            f'<span class="ly-track"><i class="{cls}" style="width:{pct:.1f}%"></i></span>'
            f'<span class="ly-v num {cls}">{sign(v, 2, "")}</span></div>')
    return f'<div class="layers">{"".join(rows)}</div>'


def kpis(items):
    return '<div class="kpi3">' + "".join(
        f'<div class="k3"><div class="k3-k">{k}</div>'
        f'<div class="k3-v num">{v}<span class="k3-u">{u}</span></div>'
        f'<div class="k3-d {t}">{d}</div></div>'
        for k, v, u, d, t in items) + "</div>"


# 两条走势供各方案复用
GOLD_SPARK = G["spark"]
GS50_SPARK = S["spark"]


# ------------------------------------------------------------------ 方案 A
def variant_a():
    gold = f"""<a class="tc a" href="#">
  <div class="tc-top">
    <span class="tc-name">黄金</span>
    <span class="tc-verdict bad">偏利空 · 熊市调整</span>
    <span class="tc-date num">11-09</span>
  </div>
  {kpis([
    ("国际金价", fmt(G['value'], 1), "美元/盎司", sign(G['chg_1d']) + " 单日", tone(G['chg_1d'])),
    ("年初至今", sign(G['ytd']), "", "人民币金价 881.0", tone(G['ytd'])),
    ("本轮回撤", G['drawdown'], "", "年化 -28.1%／年", "down"),
  ])}
  <div class="tc-text">第16轮熊市进行中 · 实际利率 2.60% 偏高、广义美元 121.67 走强，两个压制项都没松动。</div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    gs = f"""<a class="tc a" href="#">
  <div class="tc-top">
    <span class="tc-name">GS50</span>
    <span class="tc-verdict ok">升温 · 69 分</span>
    <span class="tc-date num">11-11</span>
  </div>
  {kpis([
    ("温度指数", fmt(S['score'], 1), "分", f"{sign(S['delta'],1,'')} 较昨日", "up"),
    ("名单中位", sign(S['median']), "", f"超额 {sign(S['excess'],2,'pt')}", "up"),
    ("上涨家数", f"{S['up']}/{S['n']}", "", f"涨停 {S['zt']} 家", "up"),
  ])}
  <div class="tc-text">占 A 股成交额 12.6%，10 日波动率 4.30%（剧烈）—— 方向在改善，波动没收敛。基础设施 +10.0 领先，应用端仍在跌。</div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    return gold, gs


# ------------------------------------------------------------------ 方案 B
def variant_b():
    gold = f"""<a class="tc b" href="#">
  <div class="tc-top">
    <span class="tc-name">黄金</span>
    <span class="tc-verdict bad">偏利空 · 熊市调整</span>
    <span class="tc-date num">11-09</span>
  </div>
  <div class="hero-num">
    <span class="hn-v num">{fmt(G['value'], 1)}</span>
    <span class="hn-u">美元/盎司</span>
    <span class="hn-d {tone(G['chg_1d'])} num">{sign(G['chg_1d'])}</span>
  </div>
  {spark_svg(GOLD_SPARK, "b1", positive_color="var(--up)")}
  <div class="sp-axis"><span class="num">{G['spark_d0']}</span><span class="num">{G['spark_d1']}</span></div>
  {kpis([
    ("年初至今", sign(G['ytd']), "", "人民币金价 881.0", tone(G['ytd'])),
    ("本轮回撤", G['drawdown'], "", "第16轮熊市 · 10 个月", "down"),
    ("地缘威胁", "157", "", "高于历史均值 100", "up"),
  ])}
  <span class="tc-cta">打开看板 →</span>
</a>"""
    gs = f"""<a class="tc b" href="#">
  <div class="tc-top">
    <span class="tc-name">GS50</span>
    <span class="tc-verdict ok">升温 · 69 分</span>
    <span class="tc-date num">11-11</span>
  </div>
  <div class="hero-num">
    <span class="hn-v num">{fmt(S['score'], 1)}</span>
    <span class="hn-u">/ 100 温度</span>
    <span class="hn-d num up">{sign(S['delta'], 1, '')}</span>
  </div>
  {spark_svg(GS50_SPARK, "b2", positive_color="var(--accent)")}
  <div class="sp-axis"><span class="num">{S['spark_d0']}</span><span class="num">{S['spark_d1']}</span></div>
  {kpis([
    ("名单中位", sign(S['median']), "", f"超额 {sign(S['excess'],2,'pt')}", "up"),
    ("上涨 / 下跌", f"{S['up']} / {S['down']}", "", f"涨停 {S['zt']} 家", "up"),
    ("成交额占比", fmt(S['share'], 1), "%", "10 日波动 4.30% 剧烈", "flat"),
  ])}
  <span class="tc-cta">打开看板 →</span>
</a>"""
    return gold, gs


# ------------------------------------------------------------------ 方案 C
def variant_c():
    gold = f"""<a class="tc c" href="#">
  <div class="tc-top">
    <span class="tc-name">黄金</span>
    <span class="tc-verdict bad">偏利空 · 熊市调整</span>
    <span class="tc-date num">11-09</span>
  </div>
  <div class="c-body">
    <div class="c-left">
      <div class="hero-num"><span class="hn-v num">{fmt(G['value'], 1)}</span><span class="hn-u">美元/盎司</span></div>
      <div class="c-chg num {tone(G['chg_1d'])}">单日 {sign(G['chg_1d'])}　<span class="{tone(G['ytd'])}">年初至今 {sign(G['ytd'])}</span></div>
      {spark_svg(GOLD_SPARK, "c1", h=44, area=True, positive_color="var(--up)")}
    </div>
    <div class="c-right">
      <div class="dial">
        <div class="dial-k">熊市进度</div>
        <div class="dial-v num down">-24%</div>
        <div class="dial-band">{gauge_band("c1", 24)}</div>
        <div class="dial-n">第 16 轮 · 第 10 个月</div>
      </div>
      <div class="dial">
        <div class="dial-k">四维结论</div>
        <div class="dim-row"><span>金价走势</span><b class="bear">偏空</b></div>
        <div class="dim-row"><span>制度层</span><b class="bull">偏多</b></div>
        <div class="dim-row"><span>宏观层</span><b class="bear">偏空</b></div>
        <div class="dim-row"><span>市场层</span><b class="warn">观察</b></div>
      </div>
    </div>
  </div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    gs = f"""<a class="tc c" href="#">
  <div class="tc-top">
    <span class="tc-name">GS50</span>
    <span class="tc-verdict ok">升温 · 69 分</span>
    <span class="tc-date num">11-11</span>
  </div>
  <div class="c-body">
    <div class="c-left">
      <div class="hero-num"><span class="hn-v num">{fmt(S['score'], 1)}</span><span class="hn-u">/ 100 温度</span></div>
      <div class="c-chg num"><span class="up">较昨日 {sign(S['delta'],1,'')}</span>　中位 <span class="up">{sign(S['median'])}</span></div>
      {spark_svg(GS50_SPARK, "c2", h=44, area=True, positive_color="var(--accent)")}
    </div>
    <div class="c-right">
      <div class="dial">
        <div class="dial-k">温度位置</div>
        <div class="dial-v num">{fmt(S['score'], 0)}</div>
        <div class="dial-band">{gauge_band("c2", S['score'])}</div>
        <div class="dial-n">0 冰点 / 50 中性 / 100 过热</div>
      </div>
      <div class="dial">
        <div class="dial-k">板块分层（今日）</div>
        {layer_bars(S['layers'])}
      </div>
    </div>
  </div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    return gold, gs


# ------------------------------------------------------------------ 方案 D
def variant_d():
    gold = f"""<a class="tc d" href="#">
  <div class="tc-top">
    <span class="tc-name">黄金</span>
    <span class="tc-verdict bad">偏利空 · 熊市调整</span>
    <span class="tc-date num">11-09</span>
  </div>
  <div class="hero-num">
    <span class="hn-v num">{fmt(G['value'], 1)}</span>
    <span class="hn-u">美元/盎司</span>
    <span class="hn-d num {tone(G['chg_1d'])}">{sign(G['chg_1d'])}</span>
  </div>
  <div class="d-facts">
    <span class="{tone(G['ytd'])}">年至今 {sign(G['ytd'])}</span>
    <span class="down">本轮回撤 {G['drawdown']}</span>
    <span>人民币 <b class="num">{fmt(G['cny'],1)}</b> 元/克</span>
  </div>
  <div class="d-chart">{spark_svg(GOLD_SPARK, "d1", h=88, area=True, positive_color="var(--up)")}</div>
  <div class="tc-text">实际利率 2.60% 偏高、广义美元 121.67 走强，两个压制项都没松动。</div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    gs = f"""<a class="tc d" href="#">
  <div class="tc-top">
    <span class="tc-name">GS50</span>
    <span class="tc-verdict ok">升温 · 69 分</span>
    <span class="tc-date num">11-11</span>
  </div>
  <div class="hero-num">
    <span class="hn-v num">{fmt(S['score'], 1)}</span>
    <span class="hn-u">/ 100 温度</span>
    <span class="hn-d num up">{sign(S['delta'],1,'')}</span>
  </div>
  <div class="d-facts">
    <span class="up">超额 {sign(S['excess'],2,'pt')}</span>
    <span class="up">{S['up']} 涨 {S['down']} 跌</span>
    <span>成交占比 <b class="num">{fmt(S['share'],1)}%</b></span>
  </div>
  <div class="d-chart">{spark_svg(GS50_SPARK, "d2", h=88, area=True, positive_color="var(--accent)")}</div>
  <div class="tc-text">基础设施 +10.0 领先，应用端仍在跌。方向在改善，波动没收敛。</div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    return gold, gs


# ------------------------------------------------------------------ 方案 E
def variant_e():
    gold_right = G["outlook"]
    gold = f"""<a class="tc e" href="#">
  <div class="e-strip bad">
    <span class="e-strip-h">今日结论</span>
    <span class="e-strip-v">偏利空 · 熊市调整</span>
    <span class="e-strip-n">{gold_right}</span>
  </div>
  <div class="e-main">
    <div class="tc-top">
      <span class="tc-name">黄金</span>
      <span class="tc-date num">数据 11-09</span>
    </div>
    <div class="e-grid">
      <div class="e-big"><div class="hero-num"><span class="hn-v num">{fmt(G['value'], 1)}</span><span class="hn-u">美元/盎司</span></div>
        <div class="c-chg num"><span class="{tone(G['chg_1d'])}">{sign(G['chg_1d'])}</span> · <span class="{tone(G['ytd'])}">年至今 {sign(G['ytd'])}</span></div></div>
      {spark_svg(GOLD_SPARK, "e1", h=48, positive_color="var(--up)")}
    </div>
    <div class="e-facts">
      <span><b class="num down">-24%</b> 本轮回撤</span>
      <span><b class="num">881.0</b> 元/克</span>
      <span><b class="num up">157</b> 地缘威胁</span>
      <span><b class="num down">2.60%</b> 实际利率</span>
    </div>
  </div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    gs = f"""<a class="tc e" href="#">
  <div class="e-strip ok">
    <span class="e-strip-h">今日结论</span>
    <span class="e-strip-v">升温 · 69 分</span>
    <span class="e-strip-n">中位 +2.58%，超额 +2.17pt；成交占比 12.6%，波动仍在剧烈档。</span>
  </div>
  <div class="e-main">
    <div class="tc-top">
      <span class="tc-name">GS50</span>
      <span class="tc-date num">数据 11-11</span>
    </div>
    <div class="e-grid">
      <div class="e-big"><div class="hero-num"><span class="hn-v num">{fmt(S['score'], 1)}</span><span class="hn-u">/ 100 温度</span></div>
        <div class="c-chg num"><span class="up">{sign(S['delta'],1,'')} 较昨日</span> · 30 涨 11 跌</div></div>
      {spark_svg(GS50_SPARK, "e2", h=48, positive_color="var(--accent)")}
    </div>
    <div class="e-facts">
      <span><b class="num up">+2.17pt</b> 超额</span>
      <span><b class="num">4.30%</b> 10 日波动</span>
      <span><b class="num up">+10.0</b> 基础设施</span>
      <span><b class="num down">-0.96</b> 应用·物理</span>
    </div>
  </div>
  <span class="tc-cta">打开看板 →</span>
</a>"""
    return gold, gs


VARIANTS = [
    ("A", "指标行", variant_a,
     "最小改动：文字块里加三列数字。不画图、不加色块，信息密度提升但视觉权重不变。",
     "最稳、最省事；但「单调」这个问题的根源（一整块纯文字）其实没解决。"),
    ("B", "KPI + 迷你走势线", variant_b,
     "一个大数字 + 40 点面积走势 + 三列 KPI。纯 inline SVG，无 JS、无 CDN、无外部依赖。",
     "信息量与体量最平衡，两个看板可以用同一套结构。走势线会压缩字距，窄屏要单独处理。"),
    ("C", "仪表 + 分层条", variant_c,
     "左侧大数字和走势，右侧放这个看板自己的语言：黄金是「熊市进度」条 + 四维结论，GS50 是 0–100 温度色带 + 板块分层正负条。",
     "最不像模板，两个看板各说各的语言。但两卡结构不对称，实现和维护成本最高。"),
    ("D", "大数字 + 面积图（hero 型）", variant_d,
     "整卡上半是面积走势图，数字和结论叠在图上，下半是 KPI。",
     "最像看板首屏、最有存在感。但两卡并排会显得挤，且图会抢掉「在跟踪的判断」的视觉优先级。"),
    ("E", "结论色带 + 细则", variant_e,
     "顶部一条整宽结论色带（偏利空=警示、升温=正面），下面是数字 + 走势 + 一行 facts。",
     "色带给了卡片明确的语义权重，一眼能扫出「今天哪个该看」。色带面积大，配色要克制。"),
]


# ------------------------------------------------------------------ 页面
def build_html():
    css_extra = """
/* ---- 设计稿专用（不进 theme.css） ---- */
.proto { max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }
.proto > header { margin-bottom: 40px; }
.proto h1 { font-size: 28px; margin-bottom: 8px; }
.proto .sub { color: var(--ink-2); font-size: 14px; }
.pv { margin-top: 46px; }
.pv-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
  border-top: 1px solid var(--line); padding-top: 14px; margin-bottom: 14px; }
.pv-badge { font-family: var(--font-mono); font-size: 13px; font-weight: 700;
  background: var(--accent-bg); border: 1px solid var(--accent-line); color: var(--accent-ink);
  padding: 1px 10px; border-radius: var(--r-pill); }
.pv-head h2 { font-size: 17px; }
.pv-note { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; margin-top: 12px; }
.pv-note div { font-size: 13px; line-height: 1.7; color: var(--ink-2);
  background: var(--card-2); border: 1px solid var(--line); border-radius: var(--r-md); padding: 10px 14px; }
.pv-note b { color: var(--muted); font-size: 11.5px; letter-spacing: .06em;
  text-transform: uppercase; display: block; margin-bottom: 3px; }

.pair { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; }
.tc { display: flex; flex-direction: column; gap: 10px; text-decoration: none;
  background: var(--card); border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 16px 20px; box-shadow: var(--shadow-1); color: inherit;
  transition: border-color .15s, transform .15s, box-shadow .15s; }
.tc:hover { border-color: var(--accent-line); transform: translateY(-1px); box-shadow: var(--shadow-2); text-decoration: none; }
.tc-top { display: flex; align-items: baseline; gap: 8px; }
.tc-name { font-weight: 650; font-size: 14.5px; }
.tc-date { color: var(--muted); font-size: 11.5px; margin-left: auto; }
.tc-text { font-size: 13px; line-height: 1.7; color: var(--ink-2); }
.tc-cta { font-size: 11.5px; color: var(--accent-ink); margin-top: auto; }

/* A 股口径：利多/涨 = 红(up)，利空/跌 = 绿(down) */
.bull, .tc-verdict.ok  { color: var(--up); }
.bear, .tc-verdict.bad { color: var(--down); }
.warn, .tc-verdict.warn { color: var(--guide); }
.tc-verdict { font-size: 11.5px; font-weight: 600; padding: 1px 9px; border-radius: 999px;
  border: 1px solid currentColor; }

.kpi3 { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px;
  border-top: 1px dashed var(--line); padding-top: 10px; }
.k3-k { font-size: 11.5px; color: var(--muted); }
.k3-v { font-size: 16px; font-weight: 650; line-height: 1.3; }
.k3-u { font-size: 11px; color: var(--muted); font-weight: 400; margin-left: 3px; }
.k3-d { font-size: 11.5px; color: var(--muted); }

.hero-num { display: flex; align-items: baseline; gap: 6px; }
.hn-v { font-size: 27px; font-weight: 650; letter-spacing: -.02em; line-height: 1.15; }
.hn-u { font-size: 11.5px; color: var(--muted); }
.hn-d { font-size: 13px; font-weight: 600; margin-left: auto; }
.sp { width: 100%; height: 54px; display: block; }
.sp-axis { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--dim); margin-top: -6px; }

/* C */
.c-body { display: grid; grid-template-columns: 1.15fr 1fr; gap: 16px; flex: 1 1 auto; }
.c-left { display: flex; flex-direction: column; gap: 6px; justify-content: center; }
.c-left .sp { height: 44px; }
.c-right { display: flex; flex-direction: column; gap: 14px; justify-content: center;
  border-left: 1px dashed var(--line); padding-left: 16px; }
.c-chg { font-size: 12px; color: var(--muted); }
.dial-k { font-size: 11px; color: var(--muted); letter-spacing: .04em; }
.dial-v { font-size: 19px; font-weight: 650; line-height: 1.2; }
.dial-band { margin: 5px 0 3px; }
.dial-band .band { width: 100%; height: 8px; display: block; }
.dial-n { font-size: 10.5px; color: var(--dim); }
.dim-row { display: flex; align-items: baseline; font-size: 12px; gap: 8px; }
.dim-row span { color: var(--ink-2); }
.dim-row b { margin-left: auto; font-weight: 600; }
.layers { display: grid; gap: 3px; }
.ly-row { display: grid; grid-template-columns: 68px 1fr 40px; align-items: center; gap: 6px; font-size: 11px; }
.ly-k { color: var(--ink-2); }
.ly-track { background: var(--paper-2); border-radius: 2px; height: 6px; display: block; overflow: hidden; }
.ly-track i { display: block; height: 100%; border-radius: 2px; }
.ly-track i.up { background: var(--up); }
.ly-track i.down { background: var(--down); }
.ly-v { text-align: right; }

/* D：图出血到底边，和文字完全分离，不叠加 */
.d-facts { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11.5px; color: var(--muted); }
.d-facts b { color: var(--ink); font-weight: 600; font-family: var(--font-mono); }
.d-chart { margin: 2px -20px -16px; padding: 0; }
.d-chart .sp { height: 88px; display: block; }

/* E */
.e-strip { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  margin: -16px -20px 4px; padding: 9px 20px; border-radius: var(--r-lg) var(--r-lg) 0 0;
  border-bottom: 1px solid var(--line); }
.e-strip.bad { background: var(--down-bg); border-bottom-color: var(--down); }
.e-strip.ok  { background: var(--up-bg); border-bottom-color: var(--up); }
.e-strip-h { font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.e-strip-v { font-size: 13px; font-weight: 650; }
.e-strip.bad .e-strip-v { color: var(--down); }
.e-strip.ok  .e-strip-v { color: var(--up); }
.e-strip-n { font-size: 11.5px; color: var(--ink-2); flex: 1 1 100%; line-height: 1.6; }
.e-main { display: flex; flex-direction: column; gap: 8px; }
.e-grid { display: grid; grid-template-columns: auto 1fr; gap: 14px; align-items: center; }
.e-grid .sp { height: 48px; }
.e-big { display: flex; flex-direction: column; gap: 2px; }
.e-facts { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11.5px; color: var(--muted);
  border-top: 1px dashed var(--line); padding-top: 8px; }
.e-facts b { color: var(--ink); font-weight: 600; margin-right: 3px; }
.e-facts b.up { color: var(--up); } .e-facts b.down { color: var(--down); }

@media (max-width: 820px) {
  .pair, .pv-note { grid-template-columns: 1fr; }
  .c-body { grid-template-columns: 1fr; }
  .c-right { border-left: 0; padding-left: 0; border-top: 1px dashed var(--line); padding-top: 10px; }
}
"""

    sections = []
    for key, name, fn, what, tradeoff in VARIANTS:
        gold, gs = fn()
        sections.append(f"""  <section class="pv">
    <div class="pv-head"><span class="pv-badge">方案 {key}</span><h2>{name}</h2></div>
    <div class="pair">{gold}{gs}</div>
    <div class="pv-note">
      <div><b>做法</b>{what}</div>
      <div><b>代价</b>{tradeoff}</div>
    </div>
  </section>""")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>今日卡片方案 · Dan's Investment Dashboard</title>
<link rel="stylesheet" href="../theme/theme.css">
<style>{css_extra}</style>
</head>
<body>
<div class="proto">
  <header>
    <div class="kicker">设计方案 · 不进构建</div>
    <h1>首页「今天」卡片 · 五个方案</h1>
    <p class="sub">下面全部用两个看板的真实数据（黄金 board.json 2026-11-09 / GS50 2026-11-11）。
      每个方案左边黄金、右边 GS50，鼠标悬停看整卡反馈。右上角「◐ 主题」可以切深色对比。</p>
  </header>
  {''.join(sections)}
  <section class="pv">
    <div class="pv-head"><span class="pv-badge">数据</span><h2>取数口径（供实现参考）</h2></div>
    <div class="pv-note">
      <div><b>黄金</b>hero.gold.value / chg_1d / chg_ytd、hero.gold_cny.value、hero.gold.spark（40 点）、
        insights.verdict、insights.points[0..1]、hero.outlook（四维结论）、hero.drivers。</div>
      <div><b>GS50</b>docs/data/YYYYMMDD.json：score / mood / median / excess / up / down / zt /
        amount_share / w（10 日波动）/ layers。走势线取最近 40 个文件的 score。</div>
    </div>
  </section>
</div>
<script src="../theme/site.js"></script>
</body>
</html>
"""
    OUT.write_text(html, encoding="utf-8")
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    build_html()
