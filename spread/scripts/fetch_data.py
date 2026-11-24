"""抓数：所有指数日线 + 沪深300估值 + 中美利率 → data/*.csv

    python scripts/fetch_data.py            # 增量（只补尾部缺失）
    python scripts/fetch_data.py --force    # 全量重拉
    python scripts/fetch_data.py --only idx # 只跑某一组（idx/basic/rates/legu）

源分工（见页面「口径与来源」一节）：
    股债收益差     akshare stock_ebs_lg        乐咕乐股成品利差，首选
    指数日线      tushare index_daily         抓一次存一份，之后只补尾巴
    沪深300 PE/PB tushare index_dailybasic    PE 兜底：乐咕拿不到时自己拼
    中债/美债10Y  akshare bond_zh_us_rate     中债登 + 财政部
    指数 PE 兜底  中证官网 perf 接口           tushare 没有时用它补

每次运行都会往 data/fetch_manifest.json 记一笔台账（谁、何时、成功没、为什么跳过），
docs/status.html 直接读它 + 现读 CSV 渲染，所以「数据截至」永远等于磁盘上的真实内容。
落盘后一切重算都离线，页面只读 CSV。
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")
IDX = os.path.join(DATA, "idx")
MANIFEST = os.path.join(DATA, "fetch_manifest.json")

END = "20991231"          # 让 tushare 自己截到最新交易日
START = "20040101"

UTC = dt.timezone.utc
CST = dt.timezone(dt.timedelta(hours=8))

# ------------------------------------------------------------------ 接口登记表
# 指数日线：ts_code → (短名, 用途)
#   tushare 里中证全收益的口径是 H 打头（H00985 = 中证全指全收益）
INDEX = {
    # 只登记 spread.html 真正在用的五个。删掉的八个（000985 / H00985 / 932000CNY010 /
    # 480080 / 480081 / H20915 / 930950 / 930897 / H11023）是 8 图版与四问版的下线遗留，
    # 那些页面已不存在，继续抓只是浪费额度。要用回来就在这张表里加一行 + 跑 --full。
    "000300.SH":  ("沪深300",        "股债收益差分子：PE_TTM → 盈利收益率"),
    "000922.CSI": ("中证红利",       "红利股息率的价格腿"),
    "H00922.CSI": ("中证红利全收益",  "红利股息率的全收益腿 · 分档检验目标"),
    "H00300.CSI": ("沪深300全收益",  "分档检验：股票相对债的超额收益"),
    "H11001.CSI": ("中证全债",       "分档检验的债券基准"),
}

# 非指数日线的三个整表
EXTRA = {
    "ak:legu": dict(group="akshare", label="乐咕沪深300股债利差", freq="d",
                    path="data/legu_spread.csv", unit="%", col="spread"),
    "basic:hs300": dict(group="tushare", label="沪深300 PE / PE_TTM / PB", freq="d",
                        path="data/hs300_basic.csv", unit="倍", col="pe_ttm"),
    "ak:rates": dict(group="akshare", label="中美 10 年期国债收益率", freq="d",
                     path="data/rates.csv", unit="%", col="cn10y"),
}

FREQ_LABEL = {"d": "日频", "w": "周频", "m": "月频", "q": "季频"}
FREQ_TTL = {"d": 0.33, "w": 2.0, "m": 12.0, "q": 30.0}
GROUP_LABEL = {
    "tushare": "tushare（指数日线 + 估值）",
    "akshare": "akshare（利率）",
}
STATUS_LABEL = {"ok": "成功", "skip": "跳过", "stale": "降级", "fail": "失败"}


# ------------------------------------------------------------------ 台账
def now_iso():
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_manifest():
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, encoding="utf-8") as fh:
                m = json.load(fh)
            if isinstance(m.get("items"), dict):
                return m
        except Exception:
            pass
    return {"schema": 1, "updated_at": None,
            "run": {"at": None, "force": False, "trigger": "cli", "counts": {}},
            "items": {}}


def save_manifest(m):
    m["updated_at"] = m["run"]["at"] or now_iso()
    os.makedirs(DATA, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1, sort_keys=True)


def touch(m, key, *, group, label, freq, path, status, message, unit="", col=""):
    """记一笔：成功就同时更新 last_success，降级保留上一次成功时间"""
    at = now_iso()
    it = m["items"].setdefault(key, {})
    it.update({
        "group": group, "label": label, "freq": freq,
        "ttl_days": FREQ_TTL.get(freq, 1.0),
        "status": status, "last_check": at, "last_attempt": at,
        "path": path, "message": message, "unit": unit, "col": col,
    })
    if status in ("ok", "skip"):
        it["last_success"] = at


# ------------------------------------------------------------------ 工具
def env():
    """读 .env：tushare_token（官方 56 位）/ tushare_key（镜像 tsr_…）"""
    out = {}
    for p in (os.path.join(ROOT, ".env"), os.path.join(ROOT, "..", ".env")):
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8").read().replace("\r", "").split("\n"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out.setdefault(k.strip().lower(), v.strip())
    return out


def pro_api():
    import tushare as ts
    kv = env()
    tok = kv.get("tushare_token") or os.environ.get("TUSHARE_TOKEN")
    if not tok:
        sys.exit("找不到 tushare_token：在本目录 .env 里写 tushare_token=xxx")
    return ts.pro_api(tok)


def today_str():
    return pd.Timestamp.now().strftime("%Y%m%d")


DATE_COL = ("trade_date", "date", "日期", "tradeDate")


def describe(df, col):
    """一行摘要：行数 + 最新日期 = 最新值"""
    if not len(df):
        return "0 行"
    dc = next((c for c in DATE_COL if c in df.columns), df.columns[0])
    d = df.sort_values(dc)
    last_date = str(d.iloc[-1][dc])
    if col and col in d.columns:
        v = pd.to_numeric(d[col], errors="coerce").dropna()
        if len(v):
            return f"{len(df):,} 行  最新 {last_date} = {v.iloc[-1]:,.2f}"
    return f"{len(df):,} 行  最新 {last_date}"


# ------------------------------------------------------------------ 指数日线
def save_idx(code, df):
    df = df.drop_duplicates("trade_date").sort_values("trade_date")
    df.to_csv(os.path.join(IDX, f"{code}.csv"), index=False)
    return df


def fetch_idx(pro, code, force=False):
    """返回 (status, df, message)；status 用台账那套词"""
    path = os.path.join(IDX, f"{code}.csv")
    had = os.path.exists(path)
    if had and not force:
        old = pd.read_csv(path, dtype={"trade_date": str})
        if len(old):
            last = old.trade_date.max()
            if last >= today_str():
                return "skip", old, describe(old, "close") + "（未到 TTL）"
            gap_start = (pd.Timestamp(last) - pd.Timedelta(days=30)).strftime("%Y%m%d")
            new = pro.index_daily(ts_code=code, start_date=gap_start, end_date=END)
            if len(new):
                df = save_idx(code, pd.concat([old, new]))
                return "ok", df, describe(df, "close") + f"（补 {len(new)} 行）"
            return "skip", old, describe(old, "close") + "（上游无新数据）"
    df = pro.index_daily(ts_code=code, start_date=START, end_date=END)
    if not len(df):
        return ("stale" if had else "fail"), pd.read_csv(path) if had else pd.DataFrame(), \
               "返回空表 —— 检查代码或额度"
    df = save_idx(code, df)
    return "ok", df, describe(df, "close") + "（全量）"


# ------------------------------------------------------------------ 沪深300 估值
def fetch_hs300_basic(pro, force=False):
    """index_dailybasic 按年分片（单次区间长了会截断或空表）"""
    path = os.path.join(DATA, "hs300_basic.csv")
    had = os.path.exists(path)
    got, have = [], None
    if had and not force:
        have = pd.read_csv(path, dtype={"trade_date": str})
    y0 = 2005
    if have is not None and len(have):
        y0 = max(2005, int(have.trade_date.max()[:4]) - 1)
        got.append(have)
    for y in range(y0, pd.Timestamp.now().year + 1):
        for attempt in range(4):
            try:
                d = pro.index_dailybasic(ts_code="000300.SH",
                                        start_date=f"{y}0101", end_date=f"{y}1231")
                break
            except Exception:
                time.sleep(2 + attempt * 3)
                d = pd.DataFrame()
        if len(d):
            got.append(d)
        time.sleep(0.5)
    if not got:
        return ("stale" if had else "fail"), None, "全部年份返回空"
    df = pd.concat(got).drop_duplicates("trade_date").sort_values("trade_date")
    df.to_csv(path, index=False)
    return "ok", df, describe(df, "pe_ttm")


# ------------------------------------------------------------------ 中债 / 美债
def fetch_legu():
    """乐咕 stock_ebs_lg：直接给沪深300股债利差，不用自己拼 PE 与利率。

    同一个东财系接口，系统代理挂着时连不上 —— 与 fetch_rates 一样临时摘代理。
    存盘前把小数（0.0627）统一乘 100 成百分数，和 rates.csv 一个量纲。
    """
    import akshare as ak
    path = os.path.join(DATA, "legu_spread.csv")
    had = os.path.exists(path)
    saved = {k: os.environ.pop(k) for k in
             ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
             if k in os.environ}
    try:
        raw = ak.stock_ebs_lg()
    except Exception as e:
        return ("stale" if had else "fail"), None, f"接口报错：{str(e)[:70]}"
    finally:
        os.environ.update(saved)
    if raw is None or not len(raw):
        return ("stale" if had else "fail"), None, "返回空表"
    need = {"日期", "沪深300指数", "股债利差", "股债利差均线"}
    if not need.issubset(raw.columns):
        return ("stale" if had else "fail"), None, \
               f"字段已变更：{list(raw.columns)[:6]}"
    df = raw[list(need)].rename(columns={"日期": "date", "沪深300指数": "csi300",
                                        "股债利差": "spread", "股债利差均线": "spread_avg"})
    df = df[["date", "csi300", "spread", "spread_avg"]]
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y%m%d")
    for c in ("csi300", "spread", "spread_avg"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "spread"]).drop_duplicates("date").sort_values("date")
    if not len(df):
        return ("stale" if had else "fail"), None, "全是空值"
    df[["spread", "spread_avg"]] = df[["spread", "spread_avg"]] * 100
    df.to_csv(path, index=False)
    return "ok", df, describe(df, "spread")


def fetch_rates():
    """akshare bond_zh_us_rate 底层走东财，系统代理挂着时会连不上 —— 临时摘掉代理再试。"""
    import akshare as ak
    path = os.path.join(DATA, "rates.csv")
    had = os.path.exists(path)
    saved = {k: os.environ.pop(k) for k in
             ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
             if k in os.environ}
    try:
        df = ak.bond_zh_us_rate(start_date="20050101")
    except Exception as e:
        return ("stale" if had else "fail"), None, f"接口报错：{str(e)[:70]}"
    finally:
        os.environ.update(saved)
    keep = ["日期", "中国国债收益率10年", "美国国债收益率10年"]
    df = df[keep].rename(columns={"中国国债收益率10年": "cn10y",
                                  "美国国债收益率10年": "us10y"})
    df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y%m%d")
    df = df.dropna(subset=["日期"]).sort_values("日期")
    df.to_csv(path, index=False)
    return "ok", df, describe(df, "cn10y")


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="", help="idx / basic / rates / legu")
    ap.add_argument("--trigger", default="cli", help="记录触发方式（cli / cron / rebuild）")
    # --only 只跑一组时，run.only 会记下来，状态页据此说明「本次只刷新了这几个」
    a = ap.parse_args()
    os.makedirs(IDX, exist_ok=True)
    only = a.only

    m = load_manifest()
    m["run"] = {"at": now_iso(), "force": bool(a.force), "trigger": a.trigger,
                "only": only or "all", "counts": {}}
    t0 = time.time()

    def record(key, **kw):
        touch(m, key, **kw)
        st = m["items"][key]["status"]
        m["run"]["counts"][st] = m["run"]["counts"].get(st, 0) + 1

    if not only or only == "idx":
        print("== 指数日线 ==")
        pro = pro_api()
        for code, (nm, _) in INDEX.items():
            key = f"ts:{code}"
            try:
                st, df, msg = fetch_idx(pro, code, a.force)
                print(f"  {code:16s} {nm:16s} [{st:5s}] {msg}")
            except Exception as e:
                had = os.path.exists(os.path.join(IDX, f"{code}.csv"))
                st, msg = ("stale" if had else "fail"), f"{type(e).__name__}: {str(e)[:60]}"
                print(f"  {code:16s} {nm:16s} [{st:5s}] {msg}")
            record(key, group="tushare", label=nm, freq="d",
                   path=f"data/idx/{code}.csv", status=st, message=msg,
                   unit="点", col="close")
            time.sleep(0.35)

    if not only or only == "legu":
        print("== 乐咕股债利差 ==")
        e = EXTRA["ak:legu"]
        try:
            st, df, msg = fetch_legu()
        except Exception as ex:
            st, msg = "fail", f"{type(ex).__name__}: {str(ex)[:60]}"
        print(f"  [{st:5s}] {msg}")
        record("ak:legu", status=st, message=msg, **{k: e[k] for k in
               ("group", "label", "freq", "path", "unit", "col")})

    if not only or only == "basic":
        print("== 沪深300 PE/PB ==")
        e = EXTRA["basic:hs300"]
        try:
            st, df, msg = fetch_hs300_basic(pro_api(), a.force)
        except Exception as ex:
            st, msg = "fail", f"{type(ex).__name__}: {str(ex)[:60]}"
        print(f"  [{st:5s}] {msg}")
        record("basic:hs300", status=st, message=msg, **{k: e[k] for k in
               ("group", "label", "freq", "path", "unit", "col")})

    if not only or only == "rates":
        print("== 中美10年国债 ==")
        e = EXTRA["ak:rates"]
        try:
            st, df, msg = fetch_rates()
        except Exception as ex:
            st, msg = "fail", f"{type(ex).__name__}: {str(ex)[:60]}"
        print(f"  [{st:5s}] {msg}")
        record("ak:rates", status=st, message=msg, **{k: e[k] for k in
               ("group", "label", "freq", "path", "unit", "col")})

    m["run"]["elapsed"] = round(time.time() - t0, 1)
    save_manifest(m)
    c = m["run"]["counts"]
    print(f"\n台账已写入 data/fetch_manifest.json · "
          f"成功 {c.get('ok',0)} / 跳过 {c.get('skip',0)} / "
          f"降级 {c.get('stale',0)} / 失败 {c.get('fail',0)} · "
          f"{m['run']['elapsed']}s")


if __name__ == "__main__":
    main()
