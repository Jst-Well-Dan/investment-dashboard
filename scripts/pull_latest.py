#!/usr/bin/env python3
"""把两个看板今天的数据抓下来，写进 research.yaml 的 latest 自动块。

为什么要有这一步：本站是纯静态构建，build.py 不联网、不读别的仓库，
research.yaml 必须是唯一事实源。所以「最新数字」由这个脚本负责搬运，
构建时只消费，不猜测。

用法（在仓库根目录）：
    python scripts/pull_latest.py           # 拉黄金 + GS50 + 股债收益差，写回 research.yaml
    python scripts/pull_latest.py gold      # 只拉黄金
    python scripts/pull_latest.py gs50      # 只拉 GS50
    python scripts/pull_latest.py spread    # 只拉股债收益差（五年看板）

写回规则：只替换每条研究 latest: 下面
    # >>> auto
    …
    # <<< auto
之间的内容。手写的 text: / summary: 一个字都不动。
源文件找不到时打印提示并跳过，不会让 research.yaml 变成半截。
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "research.yaml"

# 两个看板的本地数据位置（可用环境变量覆盖）
GOLD_JSON = Path(os.environ.get(
    "DAN_GOLD_JSON", r"E:/Python_Doc/Investment/20261107 黄金看板/data/board.json"))
GS50_DIR = Path(os.environ.get(
    "DAN_GS50_DIR", r"E:/Python_Doc/Investment/20261029 gs50_dashboard/docs/data"))
# 五年看板（股债收益差）自己算好读数写成一份 JSON，这里只负责搬运，不重算口径。
SPREAD_JSON = Path(os.environ.get(
    "DAN_SPREAD_JSON", r"E:/Python_Doc/Investment/20261122 五年看板/docs/data/latest.json"))

AUTO_OPEN = "      # >>> auto（由 scripts/pull_latest.py 写入，不要手改）"
AUTO_CLOSE = "      # <<< auto"
SPARK_N = 40


# ------------------------------------------------------------------ 取数
def _num(v: float, dp: int = 2) -> str:
    return f"{v:,.{dp}f}"


def _sign(v: float, dp: int = 2, unit: str = "%") -> str:
    return f"{v:+.{dp}f}{unit}"


def _cycle_hint(cycle: dict) -> str:
    """「第16轮熊市 · 进行中」+「2026.01 → 2026.11 · 10 个月」→「第16轮 · 10 个月」。"""
    m = re.search(r"第\s*\d+\s*轮", cycle.get("value") or "")
    span = [x for x in (cycle.get("text") or "").split("·") if x.strip()]
    tail = span[-1].strip() if span else ""
    return " · ".join(x for x in (m.group(0) if m else "", tail) if x)


def _tail(text: str) -> str:
    """「157，高于历史均值 100，避险叙事偏强」→「高于历史均值 100」（去掉重复的首段）。"""
    parts = [x for x in text.split("，") if x]
    return parts[1] if len(parts) > 1 else (parts[0] if parts else "")


def _tone(v: float) -> str:
    """A 股口径：正=up（红），负=down（绿）。"""
    return "up" if v > 0 else ("down" if v < 0 else "flat")


def pull_gold() -> dict:
    d = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    g = d["hero"]["gold"]
    cny = d["hero"]["gold_cny"]
    ins = d["insights"]
    pts = {p["label"]: p for p in ins.get("points") or []}

    cycle = pts.get("周期状态", {})
    draw = pts.get("本轮累计", {})
    gpr = pts.get("地缘威胁", {})
    spark = [round(v, 1) for _, v in (g.get("spark") or [])][-SPARK_N:]

    metrics = [
        {"k": "国际金价", "v": _num(g["value"], 1), "u": "美元/盎司",
         "d": _sign(g["chg_1d"]) + " 单日", "tone": _tone(g["chg_1d"])},
        {"k": "年初至今", "v": _sign(g["chg_ytd"]), "u": "",
         "d": f"人民币金价 {_num(cny['value'], 1)}", "tone": _tone(g["chg_ytd"])},
        # KPI 卡片只有 3 列、列宽约 130px，这里只放最短的一行，
        # 年份区间交给走势线的两端轴标签，不在这里重复。
        {"k": draw.get("label") or "本轮回撤", "v": draw.get("value", "—"), "u": "",
         "d": _cycle_hint(cycle), "tone": {"bad": "down", "good": "up"}.get(draw.get("tone"), "flat")},
        {"k": gpr.get("label") or "地缘威胁", "v": gpr.get("value", "—"), "u": "",
         "d": _tail(gpr.get("text", "")), "tone": "flat"},
    ]
    verdict = ins.get("verdict", "")
    return {
        "date": g.get("date") or d.get("generated_at", "")[:10],
        "verdict": verdict,
        # 卡片的走势线/左边框用这个色：结论偏空=绿、偏多=红
        "tone": "down" if "空" in verdict or "跌" in verdict else
                ("up" if "多" in verdict or "涨" in verdict else ""),
        "text": (f"国际金价 {_num(g['value'], 1)} 美元/盎司（{_sign(g['chg_1d'])}）；"
                 f"年初至今 {_sign(g['chg_ytd'])}；人民币金价 {_num(cny['value'], 1)} 元/克。"),
        "metrics": metrics,
        "spark": spark,
        "spark_from": (g.get("spark") or [["", ""]])[-SPARK_N:][0][0],
    }


def pull_gs50() -> dict:
    files = sorted(glob.glob(str(GS50_DIR / "*.json")))
    if len(files) < 2:
        raise RuntimeError(f"{GS50_DIR} 下的日数据不足两个")
    cur = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    prev = json.loads(Path(files[-2]).read_text(encoding="utf-8"))
    delta = cur["score"] - prev["score"]
    spark = []
    for f in files[-SPARK_N:]:
        spark.append(round(json.loads(Path(f).read_text(encoding="utf-8"))["score"], 1))
    day = cur["day"]

    metrics = [
        {"k": "温度指数", "v": _num(cur["score"], 1), "u": "分",
         "d": f"{_sign(delta, 1, '')} 较昨日", "tone": _tone(delta)},
        {"k": "名单中位", "v": _sign(cur["median"]), "u": "",
         "d": f"超额 {_sign(cur['excess'], 2, 'pt')}", "tone": _tone(cur["median"])},
        {"k": "上涨家数", "v": f"{cur['up']}/{cur['n']}", "u": "",
         "d": f"涨停 {cur['zt']} 家", "tone": _tone(cur["up"] - cur["down"])},
        {"k": "成交额占比", "v": _num(cur["amount_share"], 1), "u": "%",
         "d": f"A {cur['n']} + 港 {cur.get('hk_n', 0)}", "tone": "flat"},
    ]
    return {
        "date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
        "verdict": f"{cur.get('mood', '')} · {round(cur['score'])} 分",
        "tone": "up" if delta > 0 else ("down" if delta < 0 else ""),
        "text": (f"{cur.get('mood','')} {round(cur['score'])} 分，名单中位 {_sign(cur['median'])}，"
                 f"跑赢沪深 300 {_sign(cur['excess'], 2, 'pt')}；占 A 股成交额 "
                 f"{_num(cur['amount_share'], 1)}%"
                 + (f"，10 日波动率 {_num(cur['w'], 2)}%。" if cur.get("w") else "。")),
        "metrics": metrics,
        "spark": spark,
        "spark_from": "",
    }


def pull_spread() -> dict:
    """五年看板已经把读数算好写在 docs/data/latest.json（同一次 build 里算的），
    这里只做格式转换 —— 不重算价差，避免两边口径各走一套。"""
    d = json.loads(SPREAD_JSON.read_text(encoding="utf-8"))
    win_sp, win_dv = d["win"]["sp"] // 242, d["win"]["dv"] // 242
    day = d["day"]
    # 全部 tone: flat —— 价差不是价格变动，涨跌色（朱/石绿）在这里会被读成
    # 「股债收益差涨了/跌了」。贵不贵的方向交给 z 的正负号与分位，不借行情色。
    metrics = [
        {"k": "股债收益差", "v": f"{d['sp']:.2f}", "u": "%",
         "d": f"{win_sp} 年中枢 {d['sp_mu']:.2f}", "tone": "flat"},
        {"k": "红利股息差", "v": f"{d['dv']:.2f}", "u": "%",
         "d": f"{win_dv} 年中枢 {d['dv_mu']:.2f}", "tone": "flat"},
        {"k": "z / 分位（①）", "v": f"{d['sp_z']:+.2f}σ", "u": "",
         "d": f"分位 {d['sp_pct']:.0f}% · 中债 10Y {d['cn']:.2f}%", "tone": "flat"},
        {"k": "z / 分位（②）", "v": f"{d['dv_z']:+.2f}σ", "u": "",
         "d": f"分位 {d['dv_pct']:.0f}%", "tone": "flat"},
    ]
    # 结论胶囊用中性形状（●）：z 的正负只说明「离自己中枢多远」，不是看多/看空
    verdict = f"① z {d['sp_z']:+.2f}σ · 分位 {d['sp_pct']:.0f}%"
    return {
        "date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
        "verdict": verdict,
        "tone": "flat",
        "text": (f"股债收益差 {d['sp']:.2f}%（{win_sp} 年中枢 {d['sp_mu']:.2f}，"
                 f"z {d['sp_z']:+.2f}σ，分位 {d['sp_pct']:.0f}%）；"
                 f"红利股息差 {d['dv']:.2f}%（{win_dv} 年中枢 {d['dv_mu']:.2f}，"
                 f"z {d['dv_z']:+.2f}σ，分位 {d['dv_pct']:.0f}%）。"),
        "metrics": metrics,
        "spark": d["spark"],
        "spark_from": d.get("spark_from", ""),
    }


# ------------------------------------------------------------------ 写回
def yaml_block(d: dict) -> list[str]:
    """生成 latest 下 auto 块的文本行（不含两个标记）。"""
    # 用 asof 而不是 date：latest.date 是手写的，同层再写一个 date 会撞键
    lines = [f"      asof: {d['date']}"]
    if d.get("verdict"):
        lines.append(f"      verdict: {_yaml_str(d['verdict'])}")
    if d.get("tone"):
        lines.append(f"      tone: {d['tone']}")
    # 用 text_auto 而不是 text：latest: 里手写的 text（你自己的一句话）优先，
    # 这里只提供「万一没手写」的兜底，同时避免同层重复 key。
    if d.get("text"):
        lines.append(f"      text_auto: {_yaml_str(d['text'])}")
    lines.append("      metrics:")
    for m in d["metrics"]:
        parts = [f"k: {m['k']}", f"v: {_yaml_str(m['v'])}",
                 f"u: {_yaml_str(m['u'])}", f"d: {_yaml_str(m['d'])}",
                 f"tone: {m['tone']}"]
        lines.append("        - {" + ", ".join(parts) + "}")
    sp = d["spark"]
    chunk = 10
    rows = [sp[i:i + chunk] for i in range(0, len(sp), chunk)]
    first = "      spark: [" + ", ".join(str(v) for v in rows[0]) + ("," if len(rows) > 1 else "]")
    lines.append(first)
    for i, r in enumerate(rows[1:], 1):
        tail = "]" if i == len(rows) - 1 else ","
        lines.append("        " + ", ".join(str(v) for v in r) + tail)
    if d.get("spark_from"):
        lines.append(f"      spark_from: {d['spark_from']}")
    return lines


def _yaml_str(s: str) -> str:
    """YAML 双引号字符串，转义反斜杠和引号。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def patch(text: str, entry_id: str, block: list[str]) -> tuple[str, bool]:
    """在 entry_id 对应的 latest: 下替换（或首次插入）auto 块。返回 (新文本, 是否改动)。"""
    lines = text.splitlines()
    try:
        id_line = next(i for i, ln in enumerate(lines)
                       if ln.strip() == f"- id: {entry_id}")
    except StopIteration:
        print(f"  ! research.yaml 里没有 id: {entry_id}，跳过")
        return text, False

    # latest: 必须在 id 之后、下一条研究之前
    latest_i = None
    for i in range(id_line + 1, len(lines)):
        s = lines[i]
        if s.strip().startswith("- id:") or (s and not s.startswith(" ")) or s.startswith("# ---"):
            break
        if s.strip() == "latest:":
            latest_i = i
            break
    if latest_i is None:
        print(f"  ! {entry_id} 没有 latest: 块，跳过")
        return text, False

    open_i = close_i = None
    for i in range(latest_i + 1, len(lines)):
        s = lines[i]
        indented = s.startswith(" " * 6) or not s.strip()
        if s.strip() and not indented:
            break
        if s.strip().startswith("# >>> auto"):
            open_i = i
        elif s.strip().startswith("# <<< auto"):
            close_i = i
            break

    body = [AUTO_OPEN] + block + [AUTO_CLOSE]
    if open_i is not None and close_i is not None:
        new = lines[:open_i] + body + lines[close_i + 1:]
    else:
        # 首次插入：放在 latest: 现有手写字段之后
        end = latest_i + 1
        while end < len(lines):
            s = lines[end]
            if not s.strip():
                break
            if not (s.startswith(" " * 6) or s.startswith(" " * 8)):
                break
            end += 1
        new = lines[:end] + body + lines[end:]
    return "\n".join(new) + ("\n" if text.endswith("\n") else ""), True


def main() -> int:
    which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    jobs = []
    if which in ("all", "gold"):
        jobs.append(("gold-dashboard", pull_gold, GOLD_JSON))
    if which in ("all", "gs50"):
        jobs.append(("gs50-dashboard", pull_gs50, GS50_DIR))
    if which in ("all", "spread"):
        jobs.append(("spread-dashboard", pull_spread, SPREAD_JSON))

    text = YAML_PATH.read_text(encoding="utf-8")
    changed = False
    for entry_id, fn, src in jobs:
        exists = src.exists() if isinstance(src, Path) else True
        if not exists:
            print(f"跳过 {entry_id}：找不到 {src}")
            continue
        try:
            data = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"跳过 {entry_id}：读取失败 {exc}")
            continue
        text, ok = patch(text, entry_id, yaml_block(data))
        changed = changed or ok
        if ok:
            print(f"更新 {entry_id}：{data['date']} · {len(data['spark'])} 个点")

    if changed:
        YAML_PATH.write_text(text, encoding="utf-8")
        print("\nresearch.yaml 已更新，接着跑 python -m scripts.sitegen.build。")
    else:
        print("\n没有改动。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
