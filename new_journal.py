#!/usr/bin/env python3
"""按模板新建今天的复盘日志，已存在则直接打开。

用法：
    python new_journal.py            # 今天
    python new_journal.py 2026-11-17 # 指定日期（补写）
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JOURNAL = ROOT / "journal"
TEMPLATE = JOURNAL / "_template.md"


def open_path(p: Path) -> None:
    if os.name == "nt":
        os.startfile(str(p))  # noqa: S606
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(p)], check=False)


def main() -> int:
    day = sys.argv[1].strip() if len(sys.argv) > 1 else dt.date.today().isoformat()
    try:
        d = dt.date.fromisoformat(day)
    except ValueError:
        print(f"日期格式不对：{day}（要 YYYY-MM-DD）")
        return 2

    JOURNAL.mkdir(exist_ok=True)
    target = JOURNAL / f"{d.isoformat()}.md"

    if target.exists():
        print(f"已存在，直接打开：{target}")
        open_path(target)
        return 0

    text = TEMPLATE.read_text(encoding="utf-8")
    if not text.startswith("---"):
        text = f"---\ntitle: {d.isoformat()} 复盘\nsummary: \n---\n\n" + text
    target.write_text(text, encoding="utf-8")
    print(f"已创建：{target}")
    print("写完跑 build.bat 就会出现在站点上。")
    open_path(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
