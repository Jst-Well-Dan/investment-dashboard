"""股债收益差页面：只回答「股票相对债券贵不贵」。

    python scripts/build_ev.py          # → docs/spread.html

两条价差，同一套算法（收益率 − 10 年中债）：
    ① 股债收益差 = 沪深300 盈利收益率(1/PE_TTM) − 中债 10Y     全市场
    ② 红利股息差 = 中证红利股息率 − 中债 10Y                  只有红利

页面纪律：图上不放解释性长文。结论一律变成表格里的数字，
读法靠标题、图例和一句脚注交代。
"""
import datetime as dt
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DOCS = os.path.join(ROOT, "docs")
sys.path.insert(0, HERE)

import chartlib as C

HERE = os.path.dirname(os.path.abspath(__file__))


def _theme(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


THEME_CSS = _theme("theme.css")
THEME_JS = _theme("theme.js")
THEME_BTN = ('<button class="theme-toggle" type="button" aria-pressed="false" '
             'title="切换浅色 / 深色">◐<span class="tt-lab">深色</span></button>')
import metrics as MT
import figures_ev as FE
from pagelib import CSS, JS, cards_html, fig_html, sec_head, esc

CST = dt.timezone(dt.timedelta(hours=8))


# ------------------------------------------------------------------ 统计
def stats(D):
    """每条价差：去重叠 IC、三档结果、样本外 R²

    分档阈值 = 该价差自己的滚动三分位（① 1210 日、② 726 日），与页面上的
    「中枢 / 分位」同窗口。早先用的是全样本三分位，有两个病：
      1) 前视：每个观测的档位由它之后的数据决定（README 里已为 z 分档认过一次账）；
      2) 与「分位」不是一把尺：分位按滚动窗口、落档按全样本，同一天会给出
         「分位 13%」+「落高档」这种自相矛盾的读数。
    改成滚动阈值后，落档 ≈ 分位落在哪三分位区，一张表只用一套语言。
    """
    out = {}
    for key, tgt in (("sp", "ex_s"), ("dv", "ex_d")):
        x, y = D[key], D[tgt]
        d = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
        r = d.x.corr(d.y)
        sub = d.iloc[::242]                      # 去重叠：每 242 个交易日抽一点
        r_nd = sub.x.corr(sub.y) if len(sub) > 4 else float("nan")
        q = D["bk"][key]                        # (q1, q2) 逐日滚动阈值
        lab = FE.bucket_labels(d.x, q)
        buckets = []
        for j, lb in enumerate(("低", "中", "高")):
            v = d.y[lab == j]
            buckets.append(dict(lab=lb, n=len(v), mu=v.mean(), md=v.median(),
                                win=(v > 0).mean() * 100,
                                lo=pd.Series(v).quantile(.05),
                                hi=pd.Series(v).quantile(.95)))
        out[key] = dict(r=r, r_nd=r_nd, n=len(d), n_nd=len(sub),
                        q=q,                     # 逐日滚动阈值：落档与分档表同源
                        mu=d.y.mean(), win=(d.y > 0).mean() * 100,
                        buckets=buckets,
                        oos=MT.oos_r2(d.x.values.reshape(-1, 1), d.y.values,
                                      train=500, step=60, min_start=800))
    out["_qlast"] = {k: (D["bk"][k][0].iloc[-1], D["bk"][k][1].iloc[-1])
                     for k in ("sp", "dv")}
    return out


def _tone(z):
    """价差大 = 股票便宜 = 好。±0.5σ 以内算中性。"""
    if z > 0.5:
        return "var(--down)"
    if z < -0.5:
        return "var(--up)"
    return "var(--muted)"


def _monotone(b):
    return b[0]["mu"] < b[1]["mu"] < b[2]["mu"]


# ------------------------------------------------------------------ 表
def table_spreads(D, S):
    """两条价差当下的位置。IC 给去重叠值 —— 重叠值大一个量级，会误导。"""
    n = D["now"]
    head = ('<thead><tr><th style="width:26%">价差</th><th style="width:12%">现在</th>'
            '<th style="width:13%">中枢</th><th style="width:9%">z</th>'
            '<th style="width:10%">分位</th><th style="width:10%">IC⁻</th>'
            '<th>构成</th></tr></thead>')
    W = D["win"]
    rows = [
        ("① 股债收益差", "sp", "300 盈利收益率 − 中债 10Y", W["sp"]),
        ("② 红利股息差", "dv", "红利股息率 − 中债 10Y", W["dv"]),
    ]
    out = []
    for name, k, note, win in rows:
        z = n[k + "_z"]
        out.append(
            f'<tr><td><b>{esc(name)}</b></td>'
            f'<td class="num">{n[k]:.2f}%</td>'
            f'<td class="num dim2">{n[k + "_mu"]:.2f}'
            f'<span class="dim2" style="font-size:11px"> / {win // 242}y</span></td>'
            f'<td class="num" style="color:{_tone(z)}">{z:+.2f}σ</td>'
            f'<td class="num">{n[k + "_pct"]:.0f}%</td>'
            f'<td class="num dim2">{S[k]["r_nd"]:+.2f}</td>'
            f'<td class="dim2">{esc(note)}</td></tr>')
    return f'<div class="tw"><table>{head}<tbody>{"".join(out)}</tbody></table></div>'


def table_delta(D):
    """折线图回答不了「谁在动」—— 这张表给两条价差的十年位移。"""
    n = D["now"]
    first = {k: D[k].dropna().iloc[0] for k in ("ey", "dy", "cn", "sp", "dv")}
    rows = [
        ("沪深300 盈利收益率", first["ey"], n["ey"], False),
        ("中债 10 年", first["cn"], n["cn"], False),
        ("① 股债收益差", first["sp"], n["sp"], True),
        ("中证红利股息率", first["dy"], n["dy"], False),
        ("② 红利股息差", first["dv"], n["dv"], True),
    ]
    out = []
    for name, a_, b_, bold in rows:
        d = b_ - a_
        w = ' style="font-weight:600"' if bold else ""
        col = "var(--down)" if d > 0 else "var(--up)"
        out.append(f'<tr{w}><td>{esc(name)}</td>'
                   f'<td class="num dim2">{a_:.2f}%</td>'
                   f'<td class="num">{b_:.2f}%</td>'
                   f'<td class="num" style="color:{col}">{d:+.2f}</td></tr>')
    head = ('<thead><tr><th style="width:46%">%</th><th style="width:18%">2015 年初</th>'
            '<th style="width:18%">现在</th><th style="width:18%">变化</th></tr></thead>')
    return f'<div class="tw"><table>{head}<tbody>{"".join(out)}</tbody></table></div>'


def table_buckets(D, S):
    """分档结果。每档一行，只留均值和胜率 —— 5~95 分位在图上已经画了。"""
    head = ('<thead><tr><th style="width:24%">价差 → 目标</th><th style="width:9%">档</th>'
            '<th style="width:10%">n</th><th style="width:14%">1 年超额</th>'
            '<th style="width:14%">胜率</th><th style="width:12%">区间</th>'
            '<th>形态</th></tr></thead>')
    LBL = {"sp": "① 股债收益差 → 300 / 债",
           "dv": "② 红利股息差 → 红利 / 债"}
    out = []
    for k, name in LBL.items():
        mono = _monotone(S[k]["buckets"])
        for j, b in enumerate(S[k]["buckets"]):
            nm = f'<b>{esc(name)}</b>' if j == 0 else ""
            shape = ""
            if j == 0:
                shape = ('<span style="color:var(--down)">单调</span>' if mono else
                         '<span style="color:var(--guide)">非单调</span>')
            tone = "var(--down)" if b["mu"] > 0 else "var(--up)"
            out.append(
                f'<tr><td>{nm}</td><td>{b["lab"]}</td>'
                f'<td class="num dim2">{b["n"]}</td>'
                f'<td class="num" style="color:{tone};font-weight:600">{b["mu"]:+.1f}%</td>'
                f'<td class="num dim2">{b["win"]:.0f}%</td>'
                f'<td class="num dim2">{b["lo"]:+.0f} ~ {b["hi"]:+.0f}</td>'
                f'<td>{shape}</td></tr>')
    return f'<div class="tw"><table>{head}<tbody>{"".join(out)}</tbody></table></div>'


def table_verdict(D, S):
    """两条价差各自的位置。

    「落档」与「分位」现在是一把尺子：都按该价差自己的滚动三分位（① 1210 日、② 726 日）。
    早先落档按全样本绝对值三分位、分位按滚动窗口，同一天会出现
    「② 分位 13%、却落高档」这种自相矛盾的读数，而且全样本阈值还带前视。
    落档因此直接等于「当前分位落在哪三分位区」，不再另判一次。
    z 与分位仍照旧列出，但只当「离自己中枢多远」的读数，不翻方向。
    """
    n = D["now"]
    rows = [("① 股债收益差", "sp"), ("② 红利股息差", "dv")]
    out = []
    for name, k in rows:
        z, pct = n[k + "_z"], n[k + "_pct"]
        q1, q2 = S["_qlast"][k]
        x = n[k]
        # 与 stats() / fig_buckets 的分档边界完全一致：<= q1 低、(q1, q2] 中、> q2 高
        j = 0 if x <= q1 else (1 if x <= q2 else 2)
        b = S[k]["buckets"][j]
        tone = "var(--down)" if b["mu"] > 0 else "var(--up)"
        mus = [b["mu"] for b in S[k]["buckets"]]
        mono = "单调" if _monotone(S[k]["buckets"]) else (
            "非单调 · 中档更高" if mus.index(max(mus)) == 1 else "非单调 · 低档更高")
        out.append(f'<tr><td><b>{esc(name)}</b></td>'
                   f'<td class="num">{x:.2f}%</td>'
                   f'<td class="num dim2">{z:+.2f}σ</td>'
                   f'<td class="num dim2">{pct:.0f}%</td>'
                   f'<td style="color:{tone};font-weight:600">{b["lab"]}档</td>'
                   f'<td class="num" style="color:{tone}">{b["mu"]:+.1f}%'
                   f'<span class="dim2" style="font-size:11px"> / {b["win"]:.0f}%</span></td>'
                   f'<td class="num dim2">{mono}</td></tr>')
    head = ('<thead><tr><th style="width:24%">价差</th><th style="width:11%">现在</th>'
            '<th style="width:11%">z</th><th style="width:10%">分位</th>'
            '<th style="width:12%">落档</th>'
            '<th style="width:19%">该档历史 · 1 年超额 / 胜率</th>'
            '<th style="width:13%">形态</th></tr></thead>')
    return f'<div class="tw"><table>{head}<tbody>{"".join(out)}</tbody></table></div>'


# ------------------------------------------------------------------ 页面
def build(day=None):
    M = MT.all_metrics()
    D = FE.build(M)
    S = stats(D)
    n = D["now"]
    last = D["dates"][-1] if day is None else day

    H = C.Hover()
    svg_sp = FE.fig_spread(D, H)
    svg_split = FE.fig_split(D, H)
    svg_bk = FE.fig_buckets(D, H)

    W = D["win"]
    ov = cards_html([
        ("股债收益差", f"{n['sp']:.2f}%", [
            (f"{W['sp']//242} 年中枢", f"{n['sp_mu']:.2f}"),
            ("z 值", f"{n['sp_z']:+.2f}σ"),
            ("分位", f"{n['sp_pct']:.0f}%")],
         "up" if n["sp_z"] > 0 else "down"),
        ("红利股息差", f"{n['dv']:.2f}%", [
            (f"{W['dv']//242} 年中枢", f"{n['dv_mu']:.2f}"),
            ("z 值", f"{n['dv_z']:+.2f}σ"),
            ("分位", f"{n['dv_pct']:.0f}%")],
         "up" if n["dv_z"] > 0 else "down"),
        ("300 盈利收益率", f"{n['ey']:.2f}%", [
            ("PE_TTM", f"{n['pe']:.2f}"),
            ("1 ÷ PE_TTM", "")], ""),
        ("中债 10Y", f"{n['cn']:.2f}%", [
            ("2015 年初", "3.63%"),
            ("变化", "−2.04")], ""),
        ("红利股息率", f"{n['dy']:.2f}%", [
            ("2015 年初", "2.43%"),
            ("变化", "+1.86")], ""),
    ])

    body = [f"""
<header class="page">
  <h1>股票相对债券，贵不贵<span class="dim"> · {last[:4]}-{last[4:6]}-{last[6:]}</span></h1>
</header>
{ov}
<p class="keyline">涨红跌绿 · 悬停读值 · ①② 都等于「收益率 − 中债 10Y」</p>"""]

    # ---- 1
    body.append(sec_head(1, "两条价差", "各自窗口 + ±1.5σ 带"))
    body.append(table_spreads(D, S))
    body.append(fig_html(svg_sp, 1,
                         "中枢跟着利率漂移，不锚死固定阈值 —— 否则会得出「现在永远比过去便宜」。"
                         "两条窗口不统一是故意的（① 5 年、② 3 年）：统一用 3 年会让① 的 σ 摆动拉大、误报变多，"
                         "2026-01 3y z 报到 −2.13σ 说便宜、之后却跑输 17.6%。理由见 README"))

    # ---- 2
    body.append(sec_head(2, "谁在动", "分子 vs 利率"))
    body.append(table_delta(D))
    body.append(fig_html(svg_split, 2, "两条线同时抬升时，价差可能原地不动"))

    # ---- 3
    body.append(sec_head(3, "后来赚了吗", "按分位分三档（不是按绝对值，也不是按 z），看未来 1 年"))
    body.append(table_buckets(D, S))
    body.append(fig_html(svg_bk, 3,
                         "柱子 = 该档全部样本的 1 年超额收益分布，横线 = 中位数，圆点 = 均值"))

    # ---- 结论
    body.append(sec_head(None, "所以现在贵不贵", "", sid="verdict"))
    body.append(table_verdict(D, S))
    body.append('<p class="keyline">落档 = 当前分位落在哪三分位区：阈值与该价差的中枢、分位同窗口同口径'
                '（① 1210 日 · ② 726 日，且只用当天及以前的数据，无前视）'
                ' · 该档历史 = 这一档全部样本的未来 1 年超额均值 / 跑赢中证全债的比例'
                ' · z 与分位只读「离自己中枢多远」，不翻方向</p>')

    # ---- 口径
    body.append(sec_head(None, "口径", "", sid="caliber"))
    src_row = ("乐咕 <code>stock_ebs_lg</code> 成品利差（首选）：盈利收益率反推为「利差 + 中债 10Y」，"
               "所以「价差 = 分子 − 利率」在图二上仍成立" if D["src"] == "legu" else
               "<b>乐咕不可用，已回退</b>：<code>100 ÷ PE_TTM − 中债 10Y</code>（tushare <code>index_dailybasic</code>）")
    body.append(f"""
<div class="tw"><table class="caliber"><tbody>
<tr><td>股债收益差</td><td>{src_row}</td></tr>
<tr><td>红利股息率</td><td>近似值：全收益日涨幅 − 价格日涨幅，滚动 252 日求和 ÷ 当日价。
当前 {n['dy']:.2f}%，Choice 口径 3.6% —— 看方向，别看绝对值</td></tr>
<tr><td>红利股息差</td><td><code>红利股息率 − 中债 10Y</code></td></tr>
<tr><td>中枢窗口</td><td>① 1210 日（5 年）、② 726 日（3 年）—— <b>不统一是故意的</b>。
② 用 5 年窗会让 z 在 95% 的时间为正（均线在追一条上坡）；
① 用 3 年窗会让 σ 摆动范围从 2.1 倍拉到 3.0 倍，z 被虚假推远（2026-01 报 −2.13σ，
之后 300 相对债跑输 17.6%）。完整对比见 README「为什么两条价差的窗口不统一」</td></tr>
<tr><td>±1.5σ 带</td><td>逐条配窗口：① 1210 日、② 726 日，满窗口才画 —— ② 的 2017–2020 留白是刻意的</td></tr>
<tr><td>分位</td><td>与该价差自己的中枢窗口同长（① 取最近 1210 日、② 取最近 726 日）</td></tr>
<tr><td>分档（低/中/高）</td><td>阈值 = 该价差自己的滚动三分位，窗口与分位同长（① 1210 日、② 726 日），
且每天只用当天及以前 win 个观测（无前视）。所以「落档」就是用分位那把尺标的：
<code>&le; q1</code> 低、<code>(q1, q2]</code> 中、<code>&gt; q2</code> 高</td></tr>
<tr><td>未来 1 年超额</td><td>242 交易日，<code>(1 + 股票) ÷ (1 + 中证全债) − 1</code></td></tr>
<tr><td>起点 2015</td><td>两条腿的同源起点；tushare <code>index_dailybasic</code> 在 2012 与 2005–2010 有空表</td></tr>
</tbody></table></div>
<p class="keyline">去重叠后独立样本只剩 11 个点 · ① 的样本外 R² 为正，但依赖这十年利率单向下行</p>""")

    body.append(f"""
<footer>
  数据 akshare <code>stock_ebs_lg</code>（乐咕股债利差）、<code>bond_zh_us_rate</code>、
  tushare <code>index_daily</code> / <code>index_dailybasic</code>。设计思路源自
  <a href="https://xueqiu.com/3559889031/418007204">雪球 · 张翼轸（EarlETF）</a>
  的中美视角股债性价比；本页重算数据、重写图形。<br>
  {dt.datetime.now(CST).strftime("%Y-%m-%d %H:%M")} CST · 数据日
  {last[:4]}-{last[4:6]}-{last[6:]} · 自包含，可离线打开
</footer>""")

    side = f"""
<aside class="side">
  <div class="side-card">
    <div class="sc"><span class="lb">两条价差</span><span class="dt">{last[4:6]}/{last[6:]}</span></div>
    <div class="side-row"><span>① 股债收益差</span>
      <b class="{'up' if n['sp_z']>0 else 'down'}">{n['sp']:.2f}%</b></div>
    <div class="side-row"><span>　z / 分位</span>
      <b style="color:{_tone(n['sp_z'])}">{n['sp_z']:+.2f}σ / {n['sp_pct']:.0f}%</b></div>
    <div class="side-row"><span>② 红利股息差</span>
      <b class="{'up' if n['dv_z']>0 else 'down'}">{n['dv']:.2f}%</b></div>
    <div class="side-row"><span>　z / 分位</span>
      <b style="color:{_tone(n['dv_z'])}">{n['dv_z']:+.2f}σ / {n['dv_pct']:.0f}%</b></div>
  </div>
  <div class="side-card">
    <div class="sc"><span class="lb">分子与利率</span></div>
    <div class="side-row"><span>300 盈利收益率</span><b>{n['ey']:.2f}%</b></div>
    <div class="side-row"><span>中债 10Y</span><b>{n['cn']:.2f}%</b></div>
    <div class="side-row"><span>红利股息率</span><b>{n['dy']:.2f}%</b></div>
    <div class="side-row"><span>300 PE_TTM</span><b>{n['pe']:.2f}</b></div>
  </div>
  <div class="side-card">
    <div class="sc"><span class="lb">目录</span></div>
    <nav class="toc" id="toc">
      <a href="#t1"><i>1</i>两条价差</a>
      <a href="#t2"><i>2</i>谁在动</a>
      <a href="#t3"><i>3</i>后来赚了吗</a>
      <a href="#verdict"><i>✦</i>所以贵不贵</a>
      <a href="#caliber"><i>○</i>口径</a>
      <a href="status.html"><i>◷</i>数据状态</a>
    </nav>
  </div>
</aside>"""

    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>股债收益差 · {last[:4]}-{last[4:6]}-{last[6:]}</title>
<meta name="description" content="股债收益差 / 红利股息差 —— 股票相对债券贵不贵。" />
<meta name="color-scheme" content="light dark" />
<style>{THEME_CSS}</style><style>{CSS}</style><script>{THEME_JS}</script></head>
<body>
<nav class="bar"><div class="bar-in">
  <a class="brand" href="spread.html"><span class="dot"></span>股债收益差</a>
  <span class="sp"></span>
  <a class="btn on" href="spread.html">看板</a>
  <a class="btn" href="status.html">数据状态</a>
  {THEME_BTN}
</div></nav>
<div class="shell">
{side}
<main>
{"".join(body)}
</main>
</div>
<div id="tip" role="tooltip"></div>
<script type="application/json" id="hvdata">{H.json()}</script>
<script>{C.HOVER_JS}</script>
{JS}
</body></html>"""

    os.makedirs(DOCS, exist_ok=True)
    out = os.path.join(DOCS, "spread.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"  → docs/spread.html  ({len(page.encode())/1024:.0f} KB · "
          f"3 图 / 6 面板 · 数据日 {last})")
    write_latest(D, last)
    return out


def write_latest(D, last):
    """给仪表盘首页写一份读数摘要（docs/data/latest.json）。

    仪表盘是纯静态构建，不联网、也不该装 pandas 去重算价差，所以由这里把
    「今天的两条价差 + z + 分位 + 一根走势线」摊成 JSON，那边 pull_latest.py 直接读。
    字段含义与页面一致（同一次 build 里算出来的），不另起一套口径。
    """
    import json

    n = D["now"]
    sp = D["sp"].dropna()
    # 首页走势线只要 ~40 个采样点：按等距抽样，末点必须是当日值
    step = max(len(sp) // 39, 1)
    idx = list(range(0, len(sp), step))
    if idx[-1] != len(sp) - 1:
        idx.append(len(sp) - 1)
    spark = [round(float(sp.iloc[i]), 3) for i in idx]

    payload = {
        "day": last,
        "built": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "sp": round(float(n["sp"]), 3),
        "dv": round(float(n["dv"]), 3),
        "sp_z": round(float(n["sp_z"]), 3),
        "sp_pct": round(float(n["sp_pct"]), 1),
        "sp_mu": round(float(n["sp_mu"]), 3),
        "dv_z": round(float(n["dv_z"]), 3),
        "dv_pct": round(float(n["dv_pct"]), 1),
        "dv_mu": round(float(n["dv_mu"]), 3),
        "cn": round(float(n["cn"]), 3),
        "dy": round(float(n["dy"]), 3),
        "pe": round(float(n["pe"]), 3),
        "ey": round(float(n["ey"]), 3),
        "win": D["win"],
        "src": D.get("src", ""),
        "spark": spark,
        "spark_from": str(sp.index[0]),
    }
    d = os.path.join(DOCS, "data")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "latest.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"  → docs/data/latest.json（首页读数摘要 · 数据日 {last}）")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
