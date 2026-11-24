"""一条命令重建整站。

流程：读清单 → 同步并清洗托管页 → 渲染各页 → 全站扫描敏感串 → 复制资源。
任何一步发现问题都直接以非零码退出（约束 C5：不静默发布）。
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys

from . import model, render, sync

ROOT = model.ROOT
DOCS = ROOT / "docs"
THEME = ROOT / "theme"


def log(msg: str) -> None:
    print(msg, flush=True)


def build(partial: bool = False) -> int:
    """partial=True：源文件不在本机时，沿用 docs/ 里已有的旧产物。

    为什么要这个开关：research.yaml 里有的 source 指向本机目录（个股研究页在
    Investment_Workflow 下），GitHub Actions 上拿不到。云端只需要重出「依赖
    数据、每天会变」的页面（看板 + 首页/档案/判断），那 9 个研究页沿用上次提交的
    副本就够了。本地正常构建仍是全量：源文件缺失直接报错，绝不静默发布。
    """
    cfg = model.load()
    site = cfg["site"]
    # 只精确到日：同一天重复构建产物字节一致（约束 C5 幂等）
    built_at = dt.date.today().isoformat()
    stats: list[dict] = []
    problems: list[str] = []

    DOCS.mkdir(parents=True, exist_ok=True)

    # 删除之前先把「本机没源文件」的已有产物收进内存，partial 模式下原样放回。
    carried: dict[Path, bytes] = {}
    carried_ids: set[str] = set()
    if partial:
        for g in cfg["groups"]:
            for e in g.entries:
                if not e.source or e.external or e.source.exists():
                    continue
                keep = DOCS / e.url
                if keep.exists():
                    carried[keep] = keep.read_bytes()
                    carried_ids.add(e.id)
                else:
                    problems.append(
                        f"[缺源且无旧产物] {e.id}：{e.source} 不存在，docs/ 里也没有 {e.url}")

    for child in list(DOCS.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    # ---------------------------------------------------- 静态资源
    (DOCS / "assets").mkdir()
    shutil.copy2(THEME / "tokens.css", DOCS / "assets" / "tokens.css")
    shutil.copy2(THEME / "theme.css", DOCS / "assets" / "theme.css")
    shutil.copy2(THEME / "research.css", DOCS / "assets" / "research.css")
    shutil.copy2(THEME / "site.js", DOCS / "assets" / "site.js")
    if (THEME / "fonts").is_dir():  # 自托管字体：不走 CDN
        shutil.copytree(THEME / "fonts", DOCS / "assets" / "fonts")
    # theme/previews/ 是上一版首页「研究入口」的缩略图，那一块已删，不再发布。
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")  # 关掉 GitHub Pages 的 Jekyll 处理

    # ---------------------------------------------------- 托管研究页
    for g in cfg["groups"]:
        # 只有「有源文件、会被复制到本组目录」的条目才参与上一页/下一页，
        # 否则会出现指向别的目录的死链。上一页/下一页只在「确实有前后页」时给：
        # 看板页（spread / status）之间跳来跳去不是阅读顺序，反而比页脚链接更难用。
        local = [e for e in g.entries if e.source and not e.external]
        nav_ok = len(local) > 2  # 一组两页时它们本身就是一对互相链接的页面
        for i, e in enumerate(local):
            prev = local[i - 1] if (nav_ok and i > 0) else None
            next_ = local[i + 1] if (nav_ok and i + 1 < len(local)) else None
            try:
                info = sync.sync_entry(e, g, DOCS, prev, next_)
            except FileNotFoundError as exc:
                if e.id not in carried_ids:   # partial 模式下已经收进 carried，不算问题
                    problems.append(f"[同步失败] {e.id}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                problems.append(f"[同步失败] {e.id}: {exc}")
                continue
            if info:
                stats.append(info)
                note = f"（清洗 {info['redacted']} 处）" if info["redacted"] else ""
                log(f"  同步 {e.id:<22} → {e.url}  {info['bytes'] / 1024:,.0f} KB{note}")

    # partial：把本机缺源的产物放回去（这些页面这次没重出，但文件仍要在）
    for p, blob in carried.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
        log(f"  沿用 {p.relative_to(DOCS)}（本机无源，保留上次产物）")

    # ---------------------------------------------------- 页面
    pages: list[tuple[str, str]] = []
    pages.append(("index.html", render.index_page(cfg, built_at)))
    pages.append(("archive.html", render.archive_page(cfg, built_at)))
    pages.append(("theses.html", render.theses_page(cfg, built_at)))
    pages.append(("archive/theme.html", render.theme_page(cfg, built_at)))
    for g in cfg["archive_groups"]:
        pages.append((g.url, render.group_page(cfg, g, built_at, depth=2)))

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
        for m in re.finditer(r'(?:href|src)="([^"#?:]+\.(?:html|css|js|png|webp|svg))"', txt):
            target = (p.parent / m.group(1)).resolve()
            if not target.exists():
                dead.append(f"{p.relative_to(DOCS)} → {m.group(1)}")
    for d in sorted(set(dead)):
        problems.append(f"[死链] {d}")

    # ---------------------------------------------------- 汇报
    log("")
    log(f"已生成 {len(pages)} 个页面、同步 {len(stats)} 个研究页。")
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
    partial = "--partial" in sys.argv[1:]
    log(f"构建站点 → {DOCS}" + ("（partial：缺源页面沿用旧产物）" if partial else ""))
    log("")
    try:
        return build(partial=partial)
    except model.ConfigError as exc:
        log(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
