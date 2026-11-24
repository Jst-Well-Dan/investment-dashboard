"""股债收益差专项看板：只回答「股票相对债券贵不贵」。

    python scripts/figures_ev.py 是作图库，页面由 build_ev.py 生成。

两条价差（上图）：
    ① 股债收益差    = 沪深300盈利收益率(1/PE_TTM) − 中债10Y     ← 全市场
    ② 红利股息差    = 中证红利股息率 − 中债10Y                  ← 只有红利

曾经的第三条 ③ 红利 vs 全市场 = ② − ① 已整条删除：利率被代数消掉后它不是独立指标
    （秩检验 = 2、预测力不叠加、分档胜率 53/60/56 接近掷硬币）。

窗口不统一：① 用 MA1210，② 用 MA726 —— 两条价差的均值回复速度、σ 稳定性都不同，
详见下方 WIN 常量的注释；为什么特意不统一、试着统一过什么结果，写在 README
「为什么两条价差的窗口不统一」一节。
"""
import numpy as np
import pandas as pd

import chartlib as C
from chartlib import (Panel, path, band, hline, endlabel, endlabels, legend,
                      badge, Hover, _f)
# _arr/_finite/_pad/_xaxis 原本放在 figures.py（8 图版），那个文件已删，
# 这里就地实现 —— 只有四个二十行的小工具，比拉一个只用到 5% 的模块干净。
def _arr(s):
    """Series → (dates, values)：索引统一成 YYYYMMDD 字符串，NaN 保留（线会断开）"""
    if isinstance(s.index, pd.DatetimeIndex) or (len(s) and isinstance(s.index[0], pd.Timestamp)):
        keep = [i for i, v in zip(s.index, s.values) if not pd.isna(v)]
        return [x.strftime("%Y%m%d") for x in keep], [float(s[x]) for x in keep]
    return list(s.index), [None if pd.isna(v) else float(v) for v in s.values]


def _finite(vals):
    xs = [v for v in vals if v is not None]
    return (min(xs), max(xs)) if xs else (0, 1)


def _pad(lo, hi, p=0.06):
    if hi <= lo:
        return lo - 1, hi + 1
    d = (hi - lo) * p
    return lo - d, hi + d


def _xaxis(panel, dates):
    """年份跨度 ≥4 年用年刻度，否则用日期刻度"""
    if not dates:
        return ""
    span = int(dates[-1][:4]) - int(dates[0][:4])
    return (C.xaxis_years(panel, dates) if span >= 4
            else C.xaxis_dates(panel, dates))

Y5 = 1210          # 五年窗口（与 metrics 一致）
Y3 = 726           # 三年窗口

# 每条价差用自己的窗口 —— 按各自的均值回复速度/σ 稳定性定，不是统一配一个数。
# ② 用 5 年窗口的后果是：1678 天里 z 只穿越 0 轴 1 次、95% 的时间为正、
# 最长连续为正 6.6 年 —— 那不是指标在报警，是 MA 在追一条上坡。
# 换成 3 年：穿越 66 次、z>0 降到 74%、最长连正缩到 3.3 年，带也早两年画出来。
# ① 保留 5 年不是因为它更好，是因为试过 3 年更差：
#   - σ 区间从 2.1 倍拉到 3.0 倍，z 的分母自己摆，2026-01 3y z = -2.13σ 报「便宜」，
#     之后 300 相对债跑输 17.6%（同一天 5y z = -0.46σ，沉默，没报错）；
#   - 2026 年内 3y 有 93 天触下轨，5y 一天没触。
# 详细对比见 README「为什么两条价差的窗口不统一」。
WIN = {"sp": Y5, "dv": Y3}


# ------------------------------------------------------------------ 分档
# 分档阈值 = 该价差的滚动三分位，窗口与「中枢 / 分位」同长（① 1210 日、② 726 日）。
# 早先用的是全样本三分位 —— 有两个病：
#  1) 前视：每个观测的档位由「它之后的数据」决定；
#  2) 与页面上的「分位」不是一把尺子：分位按滚动窗口算、落档按全样本算，
#     于是出现「② 分位 13%，却落高档」这种自相矛盾的读数。
# 改成滚动阈值后，两者同窗口同口径，落档 ≈ 分位落在哪三分位区。
def roll_q(s, win):
    """三分位阈值（滚动，min_periods=win）：每天只用当天及以前 win 个观测"""
    return (s.rolling(win, min_periods=win).quantile(1 / 3),
            s.rolling(win, min_periods=win).quantile(2 / 3))


def bucket_labels(x, q):
    """低 / 中 / 高 → 0 / 1 / 2；阈值未满窗口（或 x 缺值）的日期记 -1

    边界与阈值同源：<= q1 低、(q1, q2] 中、> q2 高。
    q1 / q2 先 reindex 到 x 的索引，否则两边索引不同时 pandas 会取并集算对齐。
    """
    q1, q2 = q
    q1 = q1.reindex(x.index)
    q2 = q2.reindex(x.index)
    lab = pd.Series(-1, index=x.index)
    ok = q1.notna() & q2.notna() & x.notna()
    lab[ok & (x <= q1)] = 0
    lab[ok & (x > q1) & (x <= q2)] = 1
    lab[ok & (x > q2)] = 2
    return lab

# ------------------------------------------------------------------ 数据组装
def build(M):
    """把两条价差、带、z、未来 1 年超额收益都算好，一次给 build_ev 用

    为什么不复用 metrics.fig2 / fig5 的成品：那两个函数只给到「价差」，
    这里还要各自的五年带、z、以及「未来 1 年股票 vs 债券的真实超额」——
    后者是检验「价差高是否真能赚钱」的唯一凭据，必须同源同索引算。
    """
    f2, f5 = M["fig2"], M["fig5"]
    i = f2["sp_cn"].dropna().index.intersection(f5["sp_div"].dropna().index)
    i = i[i >= "20150101"]

    sp = f2["sp_cn"].reindex(i)                 # ① 300 EY − 中债（乐咕优先，拿不到退回 tushare）
    dv = f5["sp_div"].reindex(i)                # ② 红利股息 − 中债
    # 分子必须跟 ① 同源：走乐咕时 ey 是「利差 + 利率」反推出来的，
    # 直接用 100/PE_TTM 会让「图一说 5.78%、图二拆开对不上」
    ey = f2["ey"].reindex(i).ffill()             # 300 盈利收益率（与 ① 同源）
    dy = f5["div"].reindex(i)                    # 红利股息率
    cn = f2["cn10"].reindex(i).ffill()
    pe = f2["pe_used"].reindex(i).ffill()        # 与 ey 一致的 PE（乐咕时为反推值）

    def wrap(s, win=Y5):
        rm = s.rolling(win, min_periods=win).mean()
        rs = s.rolling(win, min_periods=win).std()
        return dict(rm=rm, rs=rs, up=rm + 1.5 * rs, dn=rm - 1.5 * rs,
                    z=(s - rm) / rs, win=win)

    # 未来 1 年：股票/红利相对债券的超额（债券用中证全债全收益）
    h = 242
    # 注意：metrics.idx() 返回 YYYYMMDD 字符串索引，别转 datetime，否则交集为空
    S = _idx_cached("H00300.CSI").reindex(i).ffill()
    B = _idx_cached("H11001.CSI").reindex(i).ffill()
    Dv = _idx_cached("H00922.CSI").reindex(i).ffill()
    rs_ = (S.shift(-h) / S - 1)
    rb_ = (B.shift(-h) / B - 1)
    rdd = (Dv.shift(-h) / Dv - 1)
    ex_s = (((1 + rs_) / (1 + rb_)) - 1) * 100          # 300 相对债
    ex_d = (((1 + rdd) / (1 + rb_)) - 1) * 100          # 红利相对债

    # 分位与中枢/σ 同窗口：窗口长度跟着该价差的 WIN 走，否则会出现
    # 「z 说在中枢上、分位说 74%」这种自相矛盾的读数
    def pct5(s, win=None):
        w = s.dropna().iloc[-(win or Y5):]
        return w.rank(pct=True).iloc[-1] * 100 if len(w) >= 60 else float("nan")

    return {
        "dates": list(i),
        "sp": sp, "dv": dv,
        "ey": ey, "dy": dy, "cn": cn, "pe": pe,
        "src": f2.get("src", "tushare"),
        "sp_tushare": f2["sp_tushare"].reindex(i),
        "b1": wrap(sp, WIN["sp"]), "b2": wrap(dv, WIN["dv"]),
        "win": dict(WIN),
        # 分档阈值：滚动三分位，与上面的带 / z / 分位同窗口
        "bk": {"sp": roll_q(sp, WIN["sp"]), "dv": roll_q(dv, WIN["dv"])},
        "ex_s": ex_s, "ex_d": ex_d,
        "now": {
            "sp": sp.iloc[-1], "dv": dv.iloc[-1],
            "ey": ey.iloc[-1], "dy": dy.iloc[-1], "cn": cn.iloc[-1],
            "pe": pe.iloc[-1],
            "sp_pct": pct5(sp, WIN["sp"]), "dv_pct": pct5(dv, WIN["dv"]),
            "sp_z": wrap(sp, WIN["sp"])["z"].iloc[-1],
            "sp_mu": wrap(sp, WIN["sp"])["rm"].iloc[-1],
            "sp_up": wrap(sp, WIN["sp"])["up"].iloc[-1],
            "sp_dn": wrap(sp, WIN["sp"])["dn"].iloc[-1],
            "dv_z": wrap(dv, WIN["dv"])["z"].iloc[-1],
            "dv_mu": wrap(dv, WIN["dv"])["rm"].iloc[-1],
            "dv_up": wrap(dv, WIN["dv"])["up"].iloc[-1],
            "dv_dn": wrap(dv, WIN["dv"])["dn"].iloc[-1],
        },
    }


_IC = {}


def _idx_cached(ts):
    if ts not in _IC:
        import metrics as MT
        _IC[ts] = MT.idx(ts)
    return _IC[ts]


# ------------------------------------------------------------------ 图一：主图
def fig_spread(D, H):
    """主图两栏：① 股债收益差（5 年带）、② 红利股息差（3 年带）

    刻意不画 z 的第四条线 —— z 已经在每栏标题上写了数字，
    再画一条「零轴附近抖动的 z」只会让人分不清「价差」和「价差的标准化」。
    """
    dates = D["dates"]
    n = len(dates)
    stack = []

    LABEL = {"sp": "① 股债收益差", "dv": "② 红利股息差"}
    SPEC = [
        ("sp", "① 股债收益差", "300 盈利收益率 − 中债 10Y　·　MA1210", "var(--actual)", 300),
        ("dv", "② 红利股息差", "红利股息率 − 中债 10Y　·　MA726（3 年）", "var(--down)", 280),
    ]

    heights = [h for *_, h in SPEC]
    tops = C.layout(heights)
    total = C.total_height(heights)

    for k, (key, title, note, color, hh) in enumerate(SPEC):
        s = D[key]
        b = D["b" + str(k + 1)]
        vals = _arr(s)[1]
        up = _arr(b["up"])[1]
        dn = _arr(b["dn"])[1]
        mu = _arr(b["rm"])[1]
        z = b["z"].iloc[-1]
        ztone = "var(--series-5)" if abs(z) >= 1.5 else "var(--muted)"

        lo, hi = _finite([v for v in vals + up + dn if v is not None])
        lo, hi = _pad(lo, hi, 0.09)
        p = Panel(tops[k], hh, lo, hi, n=n, title=title, sub=note,
                  yfmt=lambda v: _f(v, 1) + "%", zero=True)
        stack.append(p.frame())
        if up and up[-1] is not None:
            stack.append(band(p, dn, up, color=color, opacity=0.10))
            stack.append(path(p, up, color=color, width=0.8, opacity=0.40))
            stack.append(path(p, dn, color=color, width=0.8, opacity=0.40))
            stack.append(path(p, mu, color=color, width=1.1, dash="5 4"))
        stack.append(hline(p, 0, color="var(--muted)", dash="3 4"))
        stack.append(path(p, vals, color="var(--ink)", width=1.5))
        stack.append(endlabel(p, vals[-1], _f(vals[-1], 2) + "%", color=color))
        stack.append(badge(
            p, f"z {z:+.2f}σ · 分位 {D['now'][key + '_pct']:.0f}%",
            color=ztone, corner="lt"))
        stack.append(_xaxis(p, dates) if k == len(SPEC) - 1 else "")
        stack.append(H.add(dates, p, [
            (LABEL[key], vals, 2), ("中枢", mu, 2),
            ("上轨 +1.5σ", up, 2), ("下轨 −1.5σ", dn, 2)]))

    foot = ("中枢 = 该价差自己的滚动均线（① MA1210 · ② MA726）"
            " + ±1.5σ 带　·　z = (当前 − 中枢) ÷ σ")
    return C.svg(stack, total, footer=foot)


# ------------------------------------------------------------------ 图二：分解
def fig_split(D, H):
    """两栏：把两条价差拆成「分子」和「利率」

    价差一动不动不代表什么都没发生 —— 可能是股息率涨了、利率也涨了。
    这一图就是拆开看谁在动。
    """
    dates = D["dates"]
    n = len(dates)
    heights = [250, 250]
    tops = C.layout(heights)
    total = C.total_height(heights)
    stack = []

    PAIRS = [
        ("① 盈利收益率 − 利率", "300 盈利收益率", "中债 10Y",
         D["ey"], D["cn"], "var(--series-5)", "var(--actual)"),
        ("② 红利股息率 − 利率", "中证红利股息率", "中债 10Y",
         D["dy"], D["cn"], "var(--down)", "var(--actual)"),
    ]

    for k, (title, a_name, b_name, a, b, ca, cb) in enumerate(PAIRS):
        av, bv = _arr(a)[1], _arr(b)[1]
        lo, hi = _finite([v for v in av + bv if v is not None])
        lo, hi = _pad(lo, hi, 0.10)
        p = Panel(tops[k], heights[k], lo, hi, n=n, title=title,
                  sub=f"{a_name} {a.iloc[-1]:.2f}% · {b_name} {b.iloc[-1]:.2f}%",
                  yfmt=lambda v: _f(v, 1) + "%", zero=False)
        stack.append(p.frame())
        stack.append(path(p, bv, color=cb, width=1.3))
        stack.append(path(p, av, color=ca, width=1.6))
        stack.append(endlabels(p, [(av[-1], f"{a.iloc[-1]:.2f}%", ca),
                                   (bv[-1], f"{b.iloc[-1]:.2f}%", cb)], gap=16))
        stack.append(legend(p, [(a_name.split("：")[-1], ca, None),
                                (b_name.split("：")[-1], cb, None)]))
        stack.append(_xaxis(p, dates) if k == 1 else "")
        stack.append(H.add(dates, p, [(a_name, av, 2), (b_name, bv, 2)]))

    foot = "价差 = 分子 − 利率"
    return C.svg(stack, total, footer=foot)


# ------------------------------------------------------------------ 图三：三档
def fig_buckets(D, H):
    """把历史按价差分三档，看每档之后 1 年股票（或红利）相对债券赚多少

    这张图是这个页面唯一「可执行」的部分：它不问「信号灵不灵」，
    只问「价差在低/中/高档时，历史上接下来一年的结果分别长什么样」。
    """
    specs = [
        ("sp", "① 股债收益差 → 未来 1 年　300 / 中证全债",
         D["sp"], D["ex_s"], "var(--actual)"),
        ("dv", "② 红利股息差 → 未来 1 年　红利 / 中证全债",
         D["dv"], D["ex_d"], "var(--down)"),
    ]

    heights = [270, 270]
    tops = C.layout(heights)
    total = C.total_height(heights)
    stack = []

    for k, (key, title, x, y, color) in enumerate(specs):
        d = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
        # 分三档：阈值用滚动三分位（与「中枢 / 分位」同窗口、当天及以前），
        q1, q2 = D["bk"][key]
        lab = bucket_labels(d.x, (q1, q2))
        buckets = [(f"低档\n< {q1.iloc[-1]:.2f}%", d[lab == 0]),
                   ("中档", d[lab == 1]),
                   (f"高档\n> {q2.iloc[-1]:.2f}%", d[lab == 2])]
        ys = [b.y.values for _, b in buckets]
        lo = min(v.min() for v in ys) - 2
        hi = max(v.max() for v in ys) + 2
        lo, hi = _pad(lo, hi, 0.05)

        p = Panel(tops[k], heights[k], lo, hi, n=3, title=title,
                  sub="箱 = 25~75 分位　横线 = 中位数　圆点 = 均值　须 = 5~95",
                  yfmt=lambda v: _f(v, 0) + "%", zero=True, yticks=None)
        stack.append(p.frame())

        bw = 150
        for j, (lab, b) in enumerate(buckets):
            cx = p.x0 + (p.x1 - p.x0) * (j + 0.5) / 3
            v = b.y.values
            p05, p25, p50, p75, p95 = np.percentile(v, [5, 25, 50, 75, 95])
            mu = v.mean()
            def yy(t):
                return p.y(t)
            # 须
            stack.append(f'<line x1="{cx:.0f}" y1="{yy(p05):.1f}" x2="{cx:.0f}" '
                         f'y2="{yy(p95):.1f}" stroke="{color}66" stroke-width="1.4"/>')
            for q in (p05, p95):
                stack.append(f'<line x1="{cx-9:.0f}" y1="{yy(q):.1f}" '
                             f'x2="{cx+9:.0f}" y2="{yy(q):.1f}" stroke="{color}66" '
                             f'stroke-width="1.4"/>')
            # 箱
            stack.append(f'<rect x="{cx-bw/2:.0f}" y="{yy(p75):.1f}" width="{bw}" '
                         f'height="{abs(yy(p25)-yy(p75)):.1f}" fill="{color}22" '
                         f'stroke="{color}77" stroke-width="1"/>')
            # 中位线
            stack.append(f'<line x1="{cx-bw/2:.0f}" y1="{yy(p50):.1f}" '
                         f'x2="{cx+bw/2:.0f}" y2="{yy(p50):.1f}" stroke="{color}" '
                         f'stroke-width="2.6"/>')
            # 均值点
            stack.append(f'<circle cx="{cx:.0f}" cy="{yy(mu):.1f}" r="4.5" '
                         f'fill="var(--paper)" stroke="var(--ink)" stroke-width="2"/>')
            # 读数
            stack.append(f'<text x="{cx:.0f}" y="{yy(p95)-8:.1f}" fill="{color}" '
                         f'font-size="13" font-weight="700" text-anchor="middle" '
                         f'font-family="{C.MONO}">均值 {mu:+.1f}%</text>')
            stack.append(f'<text x="{cx:.0f}" y="{p.y1+13:.0f}" fill="{C.DIM}" '
                         f'font-size="11.5" text-anchor="middle">{lab}</text>')
            stack.append(f'<text x="{cx:.0f}" y="{yy(p05)+15:.1f}" fill="var(--dim)" '
                         f'font-size="11" text-anchor="middle">n={len(v)} · '
                         f'胜率 {(v>0).mean()*100:.0f}%</text>')
        stack.append(hline(p, 0, color="var(--muted)", dash="4 4"))

    foot = ("分档 = 价差相对自己的滚动三分位（① 1210 日 · ② 726 日，当天及以前）"
            "　·　重叠样本，视为同期历史分布而非独立事件")
    return C.svg(stack, total, footer=foot)
