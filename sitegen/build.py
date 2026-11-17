"""一条命令重建整站。

流程：读清单 → 同步并清洗托管页 → 渲染各页 → 全站扫描敏感串 → 复制资源。
任何一步发现问题都直接以非零码退出（约束 C5：不静默发布）。
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

from . import model, render, sync

ROOT = model.ROOT
DOCS = ROOT / "docs"
THEME = ROOT / "theme"
JOURNAL = ROOT / "journal"


def log(msg: str) -> None:
    print(msg, flush=True)


def build() -> int:
    cfg = model.load()
    site = cfg["site"]
    # 只精确到日：同一天重复构建产物字节一致（约束 C5 幂等）
    built_at = dt.date.today().isoformat()
    stats: list[dict] = []
    problems: list[str] = []

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)

    # ---------------------------------------------------- 静态资源
    (DOCS / "assets").mkdir()
    shutil.copy2(THEME / "theme.css", DOCS / "assets" / "theme.css")
    shutil.copy2(THEME / "site.js", DOCS / "assets" / "site.js")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")  # 关掉 GitHub Pages 的 Jekyll 处理

    # ---------------------------------------------------- 托管研究页
    for g in cfg["groups"]:
        # 只有「有源文件、会被复制到本组目录」的条目才参与上一页/下一页，
        # 否则会出现指向别的目录的死链。
        local = [e for e in g.entries if e.source and not e.external]
        for i, e in enumerate(local):
            prev = local[i - 1] if i > 0 else None
            next_ = local[i + 1] if i + 1 < len(local) else None
            try:
                info = sync.sync_entry(e, g, DOCS, prev, next_)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"[同步失败] {e.id}: {exc}")
                continue
            if info:
                stats.append(info)
                note = f"（清洗 {info['redacted']} 处）" if info["redacted"] else ""
                log(f"  同步 {e.id:<22} → {e.url}  {info['bytes'] / 1024:,.0f} KB{note}")

    # ---------------------------------------------------- 页面
    journals = render.load_journals(JOURNAL)
    latest_journal = (journals[0]["date"], journals[0]["title"], journals[0]["summary"]) if journals else None

    pages: list[tuple[str, str]] = []
    pages.append(("index.html", render.index_page(cfg, built_at, latest_journal,
                                                  len(journals), "journal/")))
    pages.append(("archive.html", render.archive_page(cfg, built_at)))
    pages.append(("theme.html", render.theme_page(cfg, built_at)))
    for g in cfg["groups"]:
        pages.append((g.url, render.group_page(cfg, g, built_at, depth=2)))

    # 日志
    jdir = DOCS / "journal"
    jdir.mkdir(parents=True, exist_ok=True)
    pages.append(("journal/index.html", render.journal_index_page(cfg, journals, built_at)))
    for i, j in enumerate(journals):
        prev_j = journals[i + 1] if i + 1 < len(journals) else None
        next_j = journals[i - 1] if i > 0 else None
        pages.append((f"journal/{j['date']}.html",
                      render.journal_entry_page(cfg, j, prev_j, next_j, built_at)))

    for rel, html in pages:
        p = DOCS / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")

    # ---------------------------------------------------- 检查
    log("")
    log("扫描发布产物…")
    for p in sorted(DOCS.rglob("*.html")):
        problems += sync.scan(p, str(p.relative_to(DOCS)))

    # 死链检查（站内相对链接）
    import re
    dead = []
    for p in sorted(DOCS.rglob("*.html")):
        txt = p.read_text(encoding="utf-8")
        for m in re.finditer(r'(?:href|src)="([^"#?:]+\.(?:html|css|js))"', txt):
            target = (p.parent / m.group(1)).resolve()
            if not target.exists():
                dead.append(f"{p.relative_to(DOCS)} → {m.group(1)}")
    for d in sorted(set(dead)):
        problems.append(f"[死链] {d}")

    # ---------------------------------------------------- 汇报
    log("")
    log(f"已生成 {len(pages)} 个页面、同步 {len(stats)} 个研究页、{len(journals)} 篇日志。")
    redacted = sum(s["redacted"] for s in stats)
    if redacted:
        log(f"清洗掉 {redacted} 处本机路径。")

    if problems:
        log("")
        log(f"❌ 发现 {len(problems)} 个问题，构建失败：")
        for p in problems:
            log("   " + p)
        log("")
        log("修好上面的问题再跑一次。发布产物不完整，不要直接 push。")
        return 1

    log("✅ 检查通过：无本机路径 / 凭证 / 死链。")
    return 0


def main() -> int:
    log(f"构建站点 → {DOCS}")
    log("")
    try:
        return build()
    except model.ConfigError as exc:
        log(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
