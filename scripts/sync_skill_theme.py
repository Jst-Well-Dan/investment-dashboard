#!/usr/bin/env python3
"""把站点主题同步进各 skill 的 assets/，让 skill 生成的页面是单文件自足的。

为什么需要：skill 产出的 HTML 要能直接双击打开、单独发给别人，所以它不能靠
`<link href="../../assets/tokens.css">`——那个相对路径只在站点目录里成立。
做法是 skill 里存一份主题副本，生成时内联进 `<style id="theme-tokens">`。

真源永远在本仓库的 theme/。改了色板先改这里，再跑本脚本；
`--check` 用来在 CI / 提交前确认副本没有漂移。

用法：
    python scripts/sync_skill_theme.py
    python scripts/sync_skill_theme.py --check     # 只报告差异，不写
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "theme"
FILES = ("tokens.css", "research.css")

# 各 skill 的 assets/ 目录（相对本仓库的上级）
SKILLS_ROOT = Path("E:/Python_Doc/Investment_Workflow/8-个股研究/20261011 光模块/.pi/skills")
TARGETS = (
    SKILLS_ROOT / "report-consensus" / "assets",
    SKILLS_ROOT / "report-gk" / "assets",
    SKILLS_ROOT / "report-structure" / "assets",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只报告哪份副本已漂移，不写文件")
    args = ap.parse_args()

    drift = 0
    for target in TARGETS:
        if not target.parent.exists():
            print(f"跳过（skill 不存在）：{target}")
            continue
        for name in FILES:
            src = THEME / name
            dst = target / name
            same = dst.exists() and dst.read_bytes() == src.read_bytes()
            if same:
                print(f"  ✓ {dst.relative_to(SKILLS_ROOT)}")
                continue
            drift += 1
            rel = dst.relative_to(SKILLS_ROOT)
            if args.check:
                print(f"  ✗ {rel} 与 theme/{name} 不一致")
            else:
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  → 已同步 {rel}")

    if args.check:
        if drift:
            print(f"\n{drift} 份副本已漂移，跑 python scripts/sync_skill_theme.py 同步。")
            return 1
        print("\n全部一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
