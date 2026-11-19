"""研究清单（research.yaml）的加载与派生逻辑。

这里只做「读 + 校验 + 派生 URL」，不写任何 HTML。
所有页面模板都必须从这里的 Entry / Group 拿数据，不允许在模板里手写研究信息（约束 C4）。
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent

STATUS_ORDER = {"跟踪中": 0, "存疑": 1, "成立": 2, "证伪": 3}
KIND_LABEL = {"dashboard": "看板", "report": "研究", "tracker": "追踪"}


@dataclass
class Thesis:
    claim: str
    status: str
    next_check: dt.date | None
    note: str
    entry_id: str
    entry_title: str
    entry_url: str
    group_name: str
    falsifier: str = ""     # 什么数据出现就算这条错了（可观测）
    action: str = ""        # 这条对 / 错，我的动作会怎么变（决策含义）
    origin: str = ""        # "ai" = AI 写的初稿，待自己重写；留空 = 自己写的

    @property
    def draft(self) -> bool:
        return self.origin == "ai"

    @property
    def css(self) -> str:
        # 状态类只用于「已到期」着色；其余四种状态靠 .badge 的形状区分，
        # 所以这里只返回 st-overdue，不再生成 st-track / st-hold 这类空类。
        return "st-overdue" if self.overdue else ""

    @property
    def overdue(self) -> bool:
        return self.next_check is not None and self.next_check < dt.date.today()

    @property
    def days_left(self) -> int | None:
        if self.next_check is None:
            return None
        return (self.next_check - dt.date.today()).days


@dataclass
class Entry:
    id: str
    title: str
    kind: str
    group: str
    slug: str
    date: dt.date
    raw: dict
    source: Path | None = None
    external: bool = False
    url: str = ""            # 构建后填：站内相对路径（从 docs/ 根算）
    topics: list[str] = field(default_factory=list)
    short: str = ""
    summary: str = ""
    data_asof: str = ""

    @property
    def kind_label(self) -> str:
        return KIND_LABEL.get(self.kind, self.kind)

    @property
    def latest(self) -> dict:
        return self.raw.get("latest") or {}

    @property
    def href(self) -> str:
        """从站点根出发的链接。"""
        return self.url


@dataclass
class Group:
    id: str
    name: str
    topic: str
    intro: str
    code: str = ""
    scope: str = ""          # 研究档案里的作用域；留空 = 不进档案（例如市场看板）
    entries: list[Entry] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"research/{self.id}/index.html"

    @property
    def latest_date(self) -> dt.date:
        return max((e.date for e in self.entries), default=dt.date(1970, 1, 1))


class ConfigError(SystemExit):
    pass


def _parse_date(v, where: str) -> dt.date:
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v))
    except Exception:
        raise ConfigError(f"[research.yaml] {where} 的日期格式不对：{v!r}（要 YYYY-MM-DD）")


def load(path: Path | None = None) -> dict:
    path = path or ROOT / "research.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))

    scope_defs = cfg.get("scopes") or []
    scope_ids = {s["id"] for s in scope_defs}

    groups = {}
    for g in cfg.get("groups") or []:
        scope = g.get("scope", "")
        if scope and scope not in scope_ids:
            raise ConfigError(f"[research.yaml] groups[{g['id']}] 的 scope 不在 scopes 里：{scope}")
        groups[g["id"]] = Group(
            id=g["id"], name=g["name"], topic=g.get("topic", ""),
            intro=g.get("intro", ""), code=g.get("code", ""), scope=scope,
        )

    seen: set[str] = set()
    for item in cfg.get("research") or []:
        where = f"research[{item.get('id')}]"
        eid = item["id"]
        if eid in seen:
            raise ConfigError(f"[research.yaml] id 重复：{eid}")
        seen.add(eid)
        if item["group"] not in groups:
            raise ConfigError(f"[research.yaml] {where} 的 group 不存在：{item['group']}")

        source = Path(item["source"]) if item.get("source") else None
        external = bool(item.get("external"))
        slug = item.get("slug") or eid

        if not external and not source and not item.get("url"):
            raise ConfigError(f"[research.yaml] {where} 必须给 source / url / external 之一")

        e = Entry(
            id=eid,
            title=item["title"],
            kind=item.get("kind", "report"),
            group=item["group"],
            slug=slug,
            date=_parse_date(item["date"], where),
            raw=item,
            source=source,
            external=external,
            topics=list(item.get("topics") or []),
            short=item.get("short") or item["title"],
            summary=(item.get("summary") or "").strip(),
            data_asof=str(item.get("data_asof") or ""),
        )
        if external:
            e.url = item["url"]
        elif source:
            e.url = f"research/{e.group}/{slug}.html"
        else:
            e.url = item["url"].lstrip("/")
        groups[e.group].entries.append(e)

    # 分组内按日期倒序
    for g in groups.values():
        g.entries.sort(key=lambda x: (x.date, x.id), reverse=True)

    theses: list[Thesis] = []
    for g in groups.values():
        for e in g.entries:
            for t in e.raw.get("theses") or []:
                theses.append(Thesis(
                    claim=t["claim"],
                    status=t.get("status", "跟踪中"),
                    next_check=_parse_date(t["next_check"], f"{e.id}.theses") if t.get("next_check") else None,
                    note=t.get("note", ""),
                    entry_id=e.id,
                    entry_title=e.title,
                    entry_url=e.url,
                    group_name=g.name,
                    falsifier=t.get("falsifier", ""),
                    action=t.get("action", ""),
                    origin=t.get("origin", ""),
                ))
    theses.sort(key=lambda t: (
        STATUS_ORDER.get(t.status, 9),
        t.next_check or dt.date(2100, 1, 1),
    ))

    all_groups = [g for g in groups.values() if g.entries]

    # 研究档案按作用域分段；没有 scope 的分组只作为「今日看板」的来源，不进档案。
    scopes = []
    for s in scope_defs:
        inside = [g for g in all_groups if g.scope == s["id"]]
        if inside:
            members = [e for g in inside for e in g.entries]
            # 作用域块带成员主题的并集，否则按主题筛选时整块会连同标题一起消失
            topics = sorted({t for e in members for t in e.topics})
            scopes.append({
                "id": s["id"], "name": s["name"], "intro": s.get("intro", ""),
                "groups": inside, "entries": members, "topics": topics,
            })
    archive_groups = [g for g in all_groups if g.scope]

    return {
        "site": cfg.get("site") or {},
        "topics": cfg.get("topics") or [],
        "groups": all_groups,
        "scopes": scopes,
        "archive_groups": archive_groups,
        "entries": [e for g in all_groups for e in g.entries],
        "theses": theses,
    }
