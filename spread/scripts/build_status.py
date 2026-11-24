"""数据状态页：每个接口最近一次抓取的成败、数据截至哪天、有多旧。

    python scripts/build_status.py        # → docs/status.html

两条判断依据同时看，缺一不可：

1. **台账**（data/fetch_manifest.json）—— 记「上次抓的时候成没成」。
   文件 mtime 不可信：CI 每次全新 checkout，mtime 永远是「刚刚」。
2. **现读磁盘**（data/*.csv）—— 记「现在手里到底有什么」。
   台账会撒谎：删了文件但没重跑，台账仍写着 ok。所以硬规则是
   **台账说 ok/skip 但磁盘没数据 → 一律改判 fail**。

只监控 spread.html 真正在用的 8 个接口。删掉的那些（8 图版遗留的九个指数、
中证官网 PE 兜底）不在这里出现，也不再抓。
"""
import datetime as dt
import html
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")
sys.path.insert(0, HERE)

CSS = open(os.path.join(HERE, "status.css"), encoding="utf-8").read()
THEME_CSS = open(os.path.join(HERE, "theme.css"), encoding="utf-8").read()
THEME_JS = open(os.path.join(HERE, "theme.js"), encoding="utf-8").read()
THEME_BTN = ('<button class="theme-toggle" type="button" aria-pressed="false" '
             'title="切换浅色 / 深色">◐<span class="tt-lab">深色</span></button>')

CST = dt.timezone(dt.timedelta(hours=8))
UTC = dt.timezone.utc

STATUS_LABEL = {"ok": "成功", "skip": "跳过", "stale": "降级", "fail": "失败"}
FREQ_LABEL = {"d": "日频", "w": "周频", "m": "月频", "q": "季频"}
GROUP_LABEL = {"tushare": "tushare · 指数日线", "akshare": "akshare · 利率 / 乐咕"}

# 只在 spread.html 用到的接口。顺序即页面顺序。
ORDER = [
    "ak:legu", "basic:hs300", "ak:rates",
    "ts:000300.SH", "ts:000922.CSI", "ts:H00922.CSI",
    "ts:H00300.CSI", "ts:H11001.CSI",
]

# 数据日期超过这么多天没往前走，标黄（日频给足周末 + 假期余量）
LATE_DAYS = {"d": 12, "w": 30, "m": 120, "q": 150}

# 每个接口喂给页面的哪一节 —— 页面上的功能对照表直接读这张表
FEEDS = {
    "ak:legu": ("01 三条价差", "乐咕成品股债利差，① 首选源"),
    "basic:hs300": ("01 三条价差", "PE_TTM → 100/PE = 300 盈利收益率（乐咕不可用时的回退）"),
    "ak:rates": ("01 · 02", "中债 10Y，三条价差共同的减项"),
    "ts:000300.SH": ("01", "与 PE 曲线同源校验"),
    "ts:000922.CSI": ("01", "红利股息率的价格腿（算分红用）"),
    "ts:H00922.CSI": ("01 · 03", "红利全收益腿；03 的分档目标"),
    "ts:H00300.CSI": ("03 后来赚了吗", "「股票 / 债」的分子"),
    "ts:H11001.CSI": ("03 后来赚了吗", "「股票 / 债」的分母"),
}

DATE_COL = ("trade_date", "日期", "tradeDate")


# ------------------------------------------------------------------ 台账
def load_manifest():
    p = os.path.join(DATA, "fetch_manifest.json")
    if not os.path.exists(p):
        return {"items": {}, "run": {}}
    try:
        with open(p, encoding="utf-8") as fh:
            m = json.load(fh)
        if isinstance(m.get("items"), dict):
            return m
    except Exception:
        pass
    return {"items": {}, "run": {}}


def parse_iso(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def rel(delta):
    """12 分钟前 / 3 小时前 / 2 天前"""
    sec = delta.total_seconds()
    if sec < 90:
        return "刚刚"
    if sec < 5400:
        return f"{int(sec // 60)} 分钟前"
    if sec < 129600:
        return f"{int(sec // 3600)} 小时前"
    return f"{int(sec // 86400)} 天前"


# ------------------------------------------------------------------ 现读盘
def probe(path):
    """读一次 CSV，返回 (行数, 最新数据日, 最新值, 列名) —— 不信任台账，直接看盘"""
    if not os.path.exists(path):
        return None
    try:
        d = pd.read_csv(path, dtype=str)
    except Exception:
        return None
    if not len(d):
        return 0, None, None, None
    dc = next((c for c in DATE_COL if c in d.columns), None)
    last = None
    if dc:
        last = str(d[dc].dropna().max())
    num = None
    for c in ("close", "spread", "pe_ttm", "cn10y"):
        if c in d.columns:
            v = pd.to_numeric(d[c], errors="coerce").dropna()
            if len(v):
                num = float(v.iloc[-1])
            break
    return len(d), last, num, dc


def build_rows(m):
    today = dt.datetime.now(CST).date()
    rows = []
    for key in ORDER:
        it = m["items"].get(key, {})
        path = os.path.join(ROOT, it.get("path", "")) if it.get("path") else None
        pr = probe(path) if path else None

        status = it.get("status", "missing")
        note = it.get("message", "")

        # 硬规则：台账说成功但磁盘没东西，实际就是失败
        if status in ("ok", "skip") and (pr is None or pr[0] == 0):
            status = "fail"
            note = "台账记录成功，但磁盘上没有可用数据"

        # 数据日期太旧 → 降级为 stale（除非本来就是 fail）
        data_date, late = pr[1] if pr else None, False
        if status in ("ok", "skip") and data_date:
            try:
                gap = (today - dt.date(int(data_date[:4]), int(data_date[4:6]),
                                       int(data_date[6:8]))).days
                if gap > LATE_DAYS.get(it.get("freq", "d"), 12):
                    status = "stale"
                    late = True
                    note = (note + " · " if note else "") + f"数据停在 {gap} 天前"
            except Exception:
                pass

        rows.append(dict(
            key=key,
            group=it.get("group", "tushare"),
            label=it.get("label", key),
            freq=it.get("freq", "d"),
            status=status,
            path=it.get("path", ""),
            n=pr[0] if pr else 0,
            data_date=data_date,
            value=pr[2] if pr else None,
            last_success=parse_iso(it.get("last_success")),
            last_check=parse_iso(it.get("last_check")),
            note=note,
            late=late,
        ))
    return rows


# ------------------------------------------------------------------ 渲染
def esc(t):
    return html.escape(str(t), quote=False)


def stamp(t):
    return t.astimezone(CST).strftime("%Y-%m-%d %H:%M") if t else "—"


def when(t):
    if not t:
        return '<span class="when y">从未</span>'
    d = dt.datetime.now(UTC) - t
    hrs = d.total_seconds() / 3600
    cls = "y" if hrs > 48 else ("o" if hrs > 12 else "g")
    return f'<span class="when {cls}">{rel(d)}</span>'


def fmt_num(v, unit=""):
    if v is None:
        return "—"
    if abs(v) >= 1000:
        return f"{v:,.2f}"
    return f"{v:.2f}"


def page(m, rows):
    counts = {"ok": 0, "skip": 0, "stale": 0, "fail": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    run = m.get("run", {})
    total_data = sum(r["n"] for r in rows)
    dates = [r["data_date"] for r in rows if r["data_date"]]
    newest = max(dates) if dates else None
    oldest = min(dates) if dates else None

    # ---------- 告警条
    bad = [r for r in rows if r["status"] == "fail"]
    stale = [r for r in rows if r["status"] == "stale"]
    alerts = []
    if bad:
        no_data = [r["label"] for r in bad if not r["n"]]
        has_old = [r["label"] for r in bad if r["n"]]
        if has_old:
            alerts.append(
                f'<div class="alert"><b>{len(has_old)} 个接口本次抓取失败</b>，'
                f'但磁盘上有旧数据，页面仍能出，只是不会更新：'
                f'{esc("、".join(has_old))}</div>')
        if no_data:
            alerts.append(
                f'<div class="alert crit"><b>{len(no_data)} 个接口完全没有数据</b>，'
                f'依赖它的图会缺线或整段空白：{esc("、".join(no_data))}</div>')
    if stale:
        alerts.append(
            f'<div class="alert warn"><b>{len(stale)} 个接口数据偏旧</b>：'
            f'{esc("、".join(r["label"] for r in stale))}</div>')
    if not alerts:
        alerts.append('<div class="alert ok"><b>全部接口正常</b>'
                      '—— 八个数据源都在，最近一次抓取没有失败。</div>')

    rows_html = []
    for r in rows:
        unit = "%" if r["key"] in ("ak:rates", "ak:legu") else ("" if "hs300" in r["key"] else "")
        rows_html.append(f"""
<tr>
  <td><span class="dot {r['status']}"></span><span class="st {r['status']}">{STATUS_LABEL.get(r['status'], r['status'])}</span></td>
  <td><div class="lb">{esc(r['label'])}</div><code class="k">{esc(r['key'])}</code></td>
  <td><span class="freq">{FREQ_LABEL.get(r['freq'], r['freq'])}</span></td>
  <td>{when(r['last_success'])}<span class="exact">{stamp(r['last_success'])}</span></td>
  <td class="num {'late' if r['late'] else ''}">{r['data_date'] or '—'}</td>
  <td class="num">{fmt_num(r['value'])}{unit}</td>
  <td class="num dim2">{r['n']:,}</td>
  <td class="note2">{esc(r['note'])}</td>
</tr>""")

    feeds = []
    for key in ORDER:
        it = next((r for r in rows if r["key"] == key), None)
        if not it:
            continue
        sec, role = FEEDS.get(key, ("—", "—"))
        feeds.append(f'<tr><td><code class="k">{esc(key)}</code></td>'
                     f'<td>{esc(sec)}</td><td class="dim2">{esc(role)}</td></tr>')

    ran = parse_iso(run.get("at"))
    only = run.get("only", "all")
    only_txt = "" if only in (None, "all", "") else \
        f'<span class="chip">本次只刷了 <b>{esc(only)}</b></span>'
    trig = {"cli": "手动", "cron": "定时", "rebuild": "重出页面"}.get(
        run.get("trigger", ""), run.get("trigger", "—"))

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<title>数据状态 · {newest or '—'}</title>
<style>{THEME_CSS}</style><style>{CSS}</style><script>{THEME_JS}</script></head>
<body>
<nav class="bar"><div class="bar-in">
  <a class="brand" href="spread.html"><span class="dot main"></span>股债收益差</a>
  <span class="sp"></span>
  <a class="btn" href="spread.html">看板</a>
  <a class="btn on" href="status.html">数据状态</a>
  {THEME_BTN}
</div></nav>

<div class="wrap">
<header class="page">
  <h1>数据状态</h1>
  <p class="lede">{len(rows)} 个接口 · 判断依据是台账（抓取成败）加现场读盘（
  磁盘上到底有什么），两者不一致时以后者为准。</p>
</header>

<div class="stats">
  <div class="stat"><div class="k">成功</div><div class="v g">{counts.get('ok',0)}</div>
    <div class="f">台账 status = ok 且磁盘有数据</div></div>
  <div class="stat"><div class="k">跳过</div><div class="v b">{counts.get('skip',0)}</div>
    <div class="f">未到 TTL 或上游无新数据</div></div>
  <div class="stat"><div class="k">降级</div><div class="v o">{counts.get('stale',0)}</div>
    <div class="f">有旧数据但偏旧 / 上游报错</div></div>
  <div class="stat"><div class="k">失败</div><div class="v r">{counts.get('fail',0)}</div>
    <div class="f">磁盘无数据，或台账与磁盘不符</div></div>
</div>

{"".join(alerts)}

<div class="meta-bar">
  <span>最近一次抓取 <b>{stamp(ran)}</b>（{trig}）</span>
  <span>数据区间 <b>{oldest or '—'}</b> ~ <b>{newest or '—'}</b></span>
  <span>合计 <b>{total_data:,}</b> 行</span>
  {only_txt}
</div>

<div class="tw"><table>
<thead><tr>
  <th style="width:6%">状态</th><th style="width:24%">接口</th><th style="width:6%">频率</th>
  <th style="width:15%">最近抓取</th><th style="width:9%">数据截至</th>
  <th style="width:11%">最新值</th><th style="width:8%">行数</th><th>备注</th>
</tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table></div>

<h2>这些数据喂给页面的哪一节</h2>
<div class="tw"><table class="feeds">
<thead><tr><th style="width:22%">接口</th><th style="width:22%">页面位置</th><th>作用</th></tr></thead>
<tbody>{"".join(feeds)}</tbody>
</table></div>

<h2>怎么判断</h2>
<div class="tw"><table class="rules">
<tbody>
<tr><td style="width:16%"><span class="st ok">成功</span></td>
<td>台账记录 ok 或 skip，<b>并且</b>磁盘上的 CSV 有数据、日期没超期。</td></tr>
<tr><td><span class="st skip">跳过</span></td>
<td>本次没真去抓 —— 只是没到 TTL（日频 0.33 天，即 8 小时），或上游没新数据。
<b>不是问题</b>，能看到「最近抓取」是刚刚就说明脚本跑过了。</td></tr>
<tr><td><span class="st stale">降级</span></td>
<td>上游报错但本地有旧数据，页面照出；或数据日期超过 {LATE_DAYS['d']} 天没往前走。
先看备注那一列写了什么。</td></tr>
<tr><td><span class="st fail">失败</span></td>
<td>磁盘上没有这个文件 / 是空表，或者台账写着 ok 但磁盘对不上。
后者是最容易骗过人的情况，所以每次出页都重新读盘。</td></tr>
</tbody></table></div>

<div class="fix">
<b>重抓：</b><code>python scripts/run_daily.py</code>（增量）·
<code>--full</code>（全量）· <code>--only idx</code>（只刷指数日线）<br>
<b>只重出状态页：</b><code>python scripts/build_status.py</code>
</div>

<footer>
  台账 <code>data/fetch_manifest.json</code> · 生成时间
  {dt.datetime.now(CST).strftime("%Y-%m-%d %H:%M")} CST<br>
  数据来自 tushare <code>index_daily</code> / <code>index_dailybasic</code>
  与 akshare <code>bond_zh_us_rate</code>。
</footer>
</div>
</body></html>"""


def main():
    m = load_manifest()
    rows = build_rows(m)
    out = page(m, rows)
    os.makedirs(DOCS, exist_ok=True)
    p = os.path.join(DOCS, "status.html")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(out)
    c = {}
    for r in rows:
        c[r["status"]] = c.get(r["status"], 0) + 1
    print(f"  → docs/status.html（{len(rows)} 个接口 · "
          f"成功 {c.get('ok',0)} / 跳过 {c.get('skip',0)} / "
          f"降级 {c.get('stale',0)} / 失败 {c.get('fail',0)}）")


if __name__ == "__main__":
    main()
