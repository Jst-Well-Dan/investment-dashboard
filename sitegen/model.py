"""研究清单（research.yaml）的加载与派生逻辑。

这里只做「读 + 校验 + 派生 URL」，不写任何 HTML。
所有页面模板都必须从这里的 Entry / Group 拿数据，不允许在模板里手写研究信息（约束 C4）。
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

STATUS_LABEL = {
    "跟踪中": "track",
    "成立": "hold",
    "存疑": "doubt",
    "证伪": "dead",
}
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

    @property
    def css(self) -> str:
        cls = STATUS_LABEL.get(self.status, "track")
        if self.overdue:
            return "st-overdue"
        return "st-" + cls

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

    groups = {}
    for g in cfg.get("groups") or []:
        groups[g["id"]] = Group(
            id=g["id"], name=g["name"], topic=g.get("topic", ""),
            intro=g.get("intro", ""), code=g.get("code", ""),
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
                ))
    theses.sort(key=lambda t: (
        STATUS_ORDER.get(t.status, 9),
        t.next_check or dt.date(2100, 1, 1),
    ))

    return {
        "site": cfg.get("site") or {},
        "topics": cfg.get("topics") or [],
        "groups": [g for g in groups.values() if g.entries],
        "entries": [e for g in groups.values() for e in g.entries],
        "theses": theses,
    }
