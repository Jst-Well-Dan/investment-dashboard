#!/usr/bin/env python3
"""把站点主题送到独立部署的看板仓库（黄金 / GS50 / 本仓的 spread/）。

为什么需要：那几个看板各自构建、各自出单文件 HTML，不经过本站渲染。
它们要长得像本站内页，但不能靠 `../../assets/tokens.css` 这种只在本站成立的路。
做法：从 theme/ 生成一份**合并好的** theme.css（tokens 去掉 @font-face + 看板皮肤层），
落进各自的样式目录，由各自的构建脚本内联进单文件 HTML。

真源永远在本仓库的 theme/。改了色板先改这里，再跑本脚本；
`--check` 用来在提交前确认三个仓库的副本没有漂移。

用法：
    python scripts/sync_board_theme.py
    python scripts/sync_board_theme.py --check     # 只报告差异，不写
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "theme"

INVEST = Path("E:/Python_Doc/Investment")
TARGETS = {
    "黄金看板": INVEST / "20261107 黄金看板" / "web",
    "GS50": INVEST / "20261029 gs50_dashboard" / "scripts",
    # 股债收益差已于 2026-11 并入本仓库（spread/），不再指向旧的本地目录。
    "股债收益差": ROOT / "spread" / "scripts",
}

BANNER = """/* =============================================================================
   Dan's Investment Dashboard · 看板主题（同步产物，勿手改）
   -----------------------------------------------------------------------------
   由 Dan's Investment Dashboard / scripts/sync_board_theme.py 生成：
     theme/tokens.css（去掉 @font-face）+ theme/board-skin.css
   要改色板 / 字体 / 涨跌语义，去改站点仓库的那两个文件，然后重跑同步脚本。
   ========================================================================== */
"""


def build_theme_css() -> str:
    tokens = (THEME / "tokens.css").read_text(encoding="utf-8")
    # 看板不自托管 Newsreader（中文本来就回退系统字体），去掉 @font-face 省 280KB
    tokens = re.sub(r"@font-face\s*\{[^}]*\}\s*", "", tokens)
    skin = (THEME / "board-skin.css").read_text(encoding="utf-8")
    return BANNER + tokens.strip() + "\n\n" + skin.strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只报告漂移，不写文件")
    args = ap.parse_args()

    payload = build_theme_css()
    drift = 0
    for name, target in TARGETS.items():
        if not target.parent.exists():
            print(f"跳过（仓库不存在）：{name} → {target}")
            continue
        for fname, content in (("theme.css", payload),
                               ("theme.js", (THEME / "board-theme.js").read_text(encoding="utf-8"))):
            dst = target / fname
            if dst.exists() and dst.read_text(encoding="utf-8") == content:
                print(f"  ✓ {name}/{fname}")
                continue
            drift += 1
            if args.check:
                print(f"  ✗ {name}/{fname} 与站点 theme/ 不一致")
            else:
                dst.write_text(content, encoding="utf-8", newline="\n")
                print(f"  → 已同步 {name}/{fname}")
    if args.check and drift:
        print(f"\n{drift} 份副本已漂移：跑一次 python scripts/sync_board_theme.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
