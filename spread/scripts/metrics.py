"""算指标 —— 8 张图的全部数值都在这里，页面只负责排版。

    python scripts/metrics.py      # 打印一遍本周读数，用来和原图对表

每个函数只吃 data/*.csv，不联网、不偷看未来。
口径与原图有差异的地方一律写进 NOTE，最后由页面「口径与数据来源」一节摊开。
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")

BOLL = 242                      # 布林线 / RSI 均线的窗口（一年交易日）
Y5 = 1210                       # 五年均线
TRADING_YEAR = 242              # 拟合年化用（原图 8.35% 对应 ≈243）

NOTE = {
    "anchor_band": "置信带 = MA1210 × exp(±1σ)，σ 取 log(指数/MA1210) 的 1210 日滚动标准差",
    "drawdown": "滚动回撤 = 当前点位 / 前 1210 个交易日的最高点位 − 1",
    "pe": "沪深300 PE_TTM / PB 取自 tushare index_dailybasic（2010 起连续，2005–2010 与 2012 有缺口，图上断开不补）",
    "spread": "股债性价比 = 乐咕 stock_ebs_lg 成品利差（首选）；拿不到时回退 1/PE_TTM − 10 年期国债收益率（中债 / 美债各算一条）",
    "spread_band": "股债性价比的中枢与 ±1.5σ 带：均值、σ 都取过去 1210 个交易日滚动（与图 1 五年之锚同窗口），满五年窗口后才开始画带；z = (当前 − 中枢) ÷ σ，|z| ≥ 1.5 就是碰到带边",
    "dividend": "TTM 股息率：每日「全收益涨幅 − 价格涨幅」视为分红，× 当日价折成金额，滚动 252 日求和后 ÷ 当日价；原图用 Choice 股息率，水平有偏差，比值与风险溢价两条线才可跨源比较",
    "boll": "布林线 = 比值 242 日均线 ± 2σ；%B = (比值 − 下轨) / (上轨 − 下轨)；带宽 = (上轨 − 下轨) / 中轨",
    "ret40": "40 日收益差 = A 的 40 日涨幅 − B 的 40 日涨幅；虚线是它自己的 242 日均线",
    "regress": f"对数线性拟合：ln(全收益) ~ 交易日序号，年化 = exp(斜率 × {TRADING_YEAR}) − 1，σ 为残差标准差",
}


# ------------------------------------------------------------------ 读盘
def idx(code):
    """读 data/idx/<code>.csv → Series（索引是 YYYYMMDD 字符串，升序）"""
    p = os.path.join(DATA, "idx", f"{code}.csv")
    d = pd.read_csv(p, dtype={"trade_date": str})
    s = d.sort_values("trade_date").drop_duplicates("trade_date")
    return s.set_index("trade_date")["close"].astype(float)


def rates():
    d = pd.read_csv(os.path.join(DATA, "rates.csv"), dtype={"日期": str})
    d = d.sort_values("日期").set_index("日期")
    return d["cn10y"].astype(float), d["us10y"].astype(float)


def hs300_basic():
    d = pd.read_csv(os.path.join(DATA, "hs300_basic.csv"), dtype={"trade_date": str})
    d = d.sort_values("trade_date").set_index("trade_date")
    return d


def legu_spread():
    """读 data/legu_spread.csv → 乐咕沪深300股债利差（百分数，已乘 100）。

    拿不到就返回 None，调用方自行退回「1/PE − 利率」。
    """
    p = os.path.join(DATA, "legu_spread.csv")
    if not os.path.exists(p):
        return None
    try:
        d = pd.read_csv(p, dtype={"date": str})
        d = d.dropna(subset=["date", "spread"])
        if not len(d):
            return None
        return d.sort_values("date").drop_duplicates("date").set_index("date")["spread"].astype(float)
    except Exception:
        return None


# ------------------------------------------------------------------ 通用指标
def rsi(x, n=14):
    d = x.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    return 100 - 100 / (1 + up.ewm(alpha=1 / n, adjust=False).mean()
                        / dn.ewm(alpha=1 / n, adjust=False).mean())


def cum(s, base=None):
    """相对起点的累计涨跌（%）"""
    s = s.dropna()
    if base:
        s = s[s.index >= base]
    return (s / s.iloc[0] - 1) * 100


def weekly(s):
    """日频 → 周频（周五收盘）"""
    t = s.copy()
    t.index = pd.to_datetime(t.index)
    return t.resample("W-FRI").last().dropna()


def tri_prism(a, b, start=None):
    """轮动三棱镜：比值布林、%B、带宽、40 日收益差、RSI14

    指标在**全历史**上算（布林线要有足够预热），画的时候只截 start 之后。

    RSI14 仍然算，但**不上图**：audit.py 需要它来验证「这栏该不该留」，
    结论是不该（与 40 日差相关 0.72、样本外无预测力），详见 README「指标审计」。
    """
    i = a.index.intersection(b.index)
    A, B = a[i], b[i]
    ratio = A / B
    m = ratio.rolling(BOLL, min_periods=60).mean()
    sd = ratio.rolling(BOLL, min_periods=60).std()
    up, dn = m + 2 * sd, m - 2 * sd
    pctb = (ratio - dn) / (up - dn)
    bw = (up - dn) / m * 100
    r40 = (A / A.shift(40) - 1) * 100 - (B / B.shift(40) - 1) * 100
    r40ma = r40.rolling(BOLL, min_periods=60).mean()
    r = rsi(ratio)
    rma = r.rolling(BOLL, min_periods=60).mean()
    w = i[i >= start] if start else i
    out = {
        "dates": list(w),
        "ca": cum(A, start), "cb": cum(B, start),
        "ratio": ratio.reindex(w), "ma": m.reindex(w),
        "up": up.reindex(w), "dn": dn.reindex(w),
        "pctb": pctb.reindex(w), "bw": bw.reindex(w),
        "r40": r40.reindex(w), "r40ma": r40ma.reindex(w),
        "rsi": r.reindex(w), "rsima": rma.reindex(w),
    }
    out["now"] = {
        "ca": out["ca"].iloc[-1], "cb": out["cb"].iloc[-1],
        "pctb": out["pctb"].dropna().iloc[-1], "bw": out["bw"].dropna().iloc[-1],
        "r40": out["r40"].dropna().iloc[-1], "r40ma": out["r40ma"].dropna().iloc[-1],
        "rsi": out["rsi"].dropna().iloc[-1], "rsima": out["rsima"].dropna().iloc[-1],
    }
    return out


def roll_max_dd(s, win=Y5):
    """当前点位 / 前 win 个交易日最高点 − 1（原图「滚动5年最大回撤」的口径）"""
    arr = s.values
    out = np.full(len(arr), np.nan)
    for i in range(win - 1, len(arr)):
        out[i] = (arr[i] / arr[i - win + 1:i + 1].max() - 1) * 100
    return pd.Series(out, index=s.index)


def log_fit(s, start):
    """对数线性拟合：返回现值、拟合值、上下轨、R²、年化、年化波动"""
    t = s[s.index >= start].dropna()
    t.index = pd.to_datetime(t.index)
    x = np.arange(len(t), dtype=float)
    y = np.log(t.values)
    slope, icept = np.polyfit(x, y, 1)
    fit = icept + slope * x
    resid = y - fit
    sig = resid.std(ddof=2)
    r2 = 1 - resid.var() / y.var()
    daily = t.pct_change().dropna()
    return {
        "dates": t.index.strftime("%Y%m%d"),
        "actual": t.values,
        "fit": np.exp(fit),
        "up": np.exp(fit + 1.5 * sig),
        "dn": np.exp(fit - 1.5 * sig),
        "r2": r2,
        "cagr": (np.exp(slope * TRADING_YEAR) - 1) * 100,
        "vol": daily.std() * np.sqrt(TRADING_YEAR) * 100,
        "sigma_band": sig,
    }


# ------------------------------------------------------------------ 8 张图的数值
def fig1_anchor():
    """中证A股全收益 五年之锚"""
    s = idx("H00985.CSI")
    ma = s.rolling(Y5, min_periods=Y5).mean()
    lr = np.log(s / ma)
    sig = lr.rolling(Y5, min_periods=Y5).std()
    dev = (s / ma - 1) * 100
    return {
        "price": s, "ma": ma, "dev": dev,
        "up": ma * np.exp(sig), "dn": ma * np.exp(-sig),
        "rsi_w": rsi(weekly(s)),
        "dd5": roll_max_dd(s),
        "now": {"dev": dev.iloc[-1], "price": s.iloc[-1], "ma": ma.iloc[-1],
                "rsi": rsi(weekly(s)).iloc[-1], "dd5": roll_max_dd(s).iloc[-1],
                "dd5_min": roll_max_dd(s).min()},
    }


def fig2_valuation():
    """中美视角下的 A股股债性价比（5 个面板）

    ① 的分子优先用乐咕 stock_ebs_lg 的成品股债利差；拿不到（文件缺失、覆盖不足、
    明显落后于 PE 的日期）就退回 100/PE_TTM − 中债 10Y。走乐咕时盈利收益率反推
    ey = sp + cn，这样「价差 = 分子 − 利率」在面板上仍然成立，不会自相矛盾。
    """
    s = idx("000300.SH")
    b = hs300_basic()
    cn, us = rates()
    pe = b["pe_ttm"].astype(float).replace(0, np.nan)
    pb = b["pb"].astype(float).replace(0, np.nan)
    price = s.reindex(pe.index).ffill()
    keep = pe.index[pe.index >= "20150101"]
    pe, pb = pe.reindex(keep), pb.reindex(keep)
    price = price.reindex(keep)
    cnx = cn.reindex(keep).ffill()
    usx = us.reindex(keep).ffill()
    sp_tushare = 100 / pe - cnx

    # 乐咕优先：覆盖率够、且没有明显落后于 tushare 的 PE 日期才用
    sp, ey_src, src, lag = sp_tushare, 100 / pe, "tushare", 0
    lg = legu_spread()
    if lg is not None and len(lg):
        lgx = lg.reindex(keep).ffill()
        lag = int((keep > lg.index[-1]).sum())      # 乐咕落在后面几个交易日
        if lgx.notna().mean() >= 0.98 and lag <= 5:
            sp = lgx
            ey_src = sp + cnx                        # 反推，保证 sp = ey − cn
            src = "legu"

    # 五年滚动中枢与 ±1.5σ：min_periods 就是 1210，带从满五年窗口后才开始画
    # （2015 起的样本要到 2020 底才凑满，之前的半截窗口噪声大，画出来会锚人）
    rm = sp.rolling(Y5, min_periods=Y5).mean()
    rs = sp.rolling(Y5, min_periods=Y5).std()
    return {
        "dates": keep,
        "price": price, "pe": pe, "pb": pb,
        "pe_used": 100 / ey_src, "ey": ey_src,
        "sp": sp, "sp_tushare": sp_tushare, "sp_cn": sp,
        "sp_us": 100 / pe - usx,
        "cn10": cnx, "us10": usx,
        "mu": rm, "sd": rs,
        "band_up": rm + 1.5 * rs, "band_dn": rm - 1.5 * rs,
        "z": (sp - rm) / rs,
        "src": src, "legu_lag": lag,
        "now": {"pe": (100 / ey_src).iloc[-1], "pb": pb.iloc[-1],
                "sp_cn": sp.iloc[-1], "sp_us": (100 / pe - usx).iloc[-1],
                "cn10": cnx.iloc[-1], "us10": usx.iloc[-1],
                "mu": rm.iloc[-1], "sd": rs.iloc[-1],
                "band_up": (rm + 1.5 * rs).iloc[-1],
                "band_dn": (rm - 1.5 * rs).iloc[-1],
                "z": ((sp - rm) / rs).iloc[-1]},
    }


def fig6_size():
    """规模风格轮动三棱镜：沪深300全收益 vs 中证2000全收益"""
    a, b = idx("H00300.CSI"), idx("932000CNY010.CSI")
    i = a.index.intersection(b.index)
    A, B = a[i], b[i]
    return tri_prism(A, B, start="20190101")


def fig7_style():
    """成长100R vs 价值100R 三棱镜"""
    a, b = idx("480080.CNI"), idx("480081.CNI")
    i = a.index.intersection(b.index)
    A, B = a[i], b[i]
    return tri_prism(A, B, start="20190101")


def ttm_dividend(tr, pr):
    """TTM 股息率 = Σ(过去 252 日每日分红收益率 × 当日价 / 今日价)

    每日分红收益率 = 全收益日涨幅 − 价格日涨幅，只在除权日非零；
    乘 P_s/P_t 把它折成「以今日价格计的 TTM 分红额 ÷ 今日价格」，
    这样分子是阶梯、分母每天动，曲线就连续了（原图 Choice 也是这个效果）。
    """
    i = tr.index.intersection(pr.index)
    T, P = tr[i], pr[i]
    d = (T.pct_change() - P.pct_change()).fillna(0)
    win = 252
    num = (d * P).rolling(win, min_periods=win - 20).sum()      # Σ 分红额（阶梯）
    dy = num / P * 100                                          # ÷ 今日价格
    return dy.where((dy > 0.05) & (dy < 25))


def fig8_dividend():
    """中证红利股息率追踪"""
    cn, _ = rates()
    out = {}
    for key, pr, tr in (("div", "000922.CSI", "H00922.CSI"),
                        ("hs", "000300.SH", "H00300.CSI")):
        p, t = idx(pr), idx(tr)
        i = p.index.intersection(t.index)
        out[key] = ttm_dividend(t[i], p[i])
        out[key + "_date"] = i
    i = out["div_date"].intersection(out["hs_date"])
    i = i[i >= "20150101"]                       # 2016 前后才有稳定的双边序列
    d, h = out["div"].reindex(i), out["hs"].reindex(i)
    cnx = cn.reindex(i).ffill()
    rel = (d / h).replace([np.inf, -np.inf], np.nan)
    return {
        "dates": i, "div": d, "hs": h, "rel": rel,
        "sp_div": d - cnx, "sp_hs": h - cnx,
        "now": {"div": d.dropna().iloc[-1], "hs": h.dropna().iloc[-1],
                "rel": rel.dropna().iloc[-1],
                "sp_div": (d - cnx).dropna().iloc[-1],
                "sp_hs": (h - cnx).dropna().iloc[-1],
                "cn10": cnx.iloc[-1]},
    }


def fig9_div_vs_all():
    """中证红利 vs 中证A股（全收益）三棱镜"""
    a, b = idx("H00922.CSI"), idx("H00985.CSI")
    i = a.index.intersection(b.index)
    A, B = a[i], b[i]
    return tri_prism(A, B, start="20190101")


def fig10_regress():
    """中证红利全收益 对数回归曲线"""
    f = log_fit(idx("H00922.CSI"), "20160101")
    f["now"] = {"actual": f["actual"][-1], "fit": f["fit"][-1],
                "up": f["up"][-1], "dn": f["dn"][-1],
                "pos": (f["actual"][-1] - f["fit"][-1]) / (f["up"][-1] - f["fit"][-1])}
    return f


def fig11_div_hk():
    """红利 A股 vs 港股高股息 三棱镜"""
    a, b = idx("H00922.CSI"), idx("H20915.CSI")
    i = a.index.intersection(b.index)
    A, B = a[i], b[i]
    return tri_prism(A, B, start="20190101")


def oos_r2(X, y, train=500, step=20, min_start=600):
    """滚动样本外 R²。基准是「预测恒等于 0」，所以负值 = 还不如不预测。

    从 audit.py 搬过来的 —— 那边整套审计随 8 图版一起下线了，
    但 build_ev.py 还要用它给「价差有没有预测力」打分。
    """
    n = len(y)
    pred = np.full(n, np.nan)
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    for t in range(min_start, n - step, step):
        lo = max(0, t - train)
        ytr = y[lo:t]
        ok = np.isfinite(ytr)
        if ok.sum() < 100:
            continue
        Xtr = np.column_stack([np.ones(ok.sum())] +
                              [X[lo:t][ok][:, k] for k in range(X.shape[1])])
        try:
            beta, *_ = np.linalg.lstsq(Xtr, ytr[ok], rcond=None)
        except np.linalg.LinAlgError:
            continue
        Xte = np.column_stack([np.ones(step)] +
                              [X[t:t + step][:, k] for k in range(X.shape[1])])
        pred[t:t + step] = Xte @ beta
    m = np.isfinite(pred) & np.isfinite(y)
    if m.sum() < 100:
        return np.nan
    sse = ((y[m] - pred[m]) ** 2).sum()
    sst = (y[m] ** 2).sum()
    return float(1 - sse / sst)


def all_metrics():
    """只算 spread.html 要的三块：估值（fig2）、股息率与价差（fig5）、价差主表。

    fig1 / fig3 / fig4 / fig6 / fig7 / fig8 是 8 图版的东西，
    那些图 2026-11-22 已随精简下线，函数仍留在本文件里（回测/复核时还能调用），
    但不再进 all_metrics()，省掉每次出页面前的一堆无用计算。
    """
    return {
        "fig2": fig2_valuation(),
        "fig5": fig8_dividend(),
    }


if __name__ == "__main__":
    M = all_metrics()
    for k, v in M.items():
        n = v.get("now", {})
        print(f"\n== {k} ==")
        for kk, vv in n.items():
            print(f"   {kk:10s} {vv:.2f}" if isinstance(vv, (int, float)) else f"   {kk:10s} {vv}")
