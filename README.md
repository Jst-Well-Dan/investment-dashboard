# Dan's Investment Dashboard

个人投资研究入口：**一个首页看到全部研究，一天一个文件做复盘，所有新页面共用一套主题。**

- 线上：https://jst-well-dan.github.io/investment-dashboard/
- 目标与验收标准：见 `GOALS.md`
- 黄金看板、GS50 看板仍是独立仓库、独立 Actions，本站只做入口和链接（不复制、不改动）。

---

## 日常三件事

### 1. 写今天的复盘

```bat
new_journal.bat              :: 生成 journal\2026-11-18.md 并打开
new_journal.bat 2026-11-10   :: 补写某天
build.bat                    :: 重建 + 自动打开首页
```

日志是纯 Markdown，一天一个文件。可用的引用语法：

| 写法 | 效果 |
|---|---|
| `[[300308-consensus]]` | 链接到该研究的页面，显示它的短标题 |
| `[[ai-capex]]` | 同上（研究清单里的任意 `id`） |
| `[[300308]]` | 链接到分组页（分组 `id`） |
| `[[journal:2026-11-17]]` | 链到另一篇日志 |

`id` 就是 `research.yaml` 里每条研究的 `id`，日志里写错会原样保留 `[[xxx]]`，方便你发现。

### 2. 加一项新研究

1. 把 HTML 放到任何地方（**不用搬进这个仓库**），例如 `E:\...\my_report.html`
2. 在 `research.yaml` 的 `research:` 下加一条：

```yaml
  - id: my-report              # 唯一，用于 URL 和日志引用
    group: 300308              # 必须是 groups 里已有的 id
    title: 中际旭创 · 某某分析   # 显示在卡片和页面标题
    short: 某某分析             # 可选，标签/日志链接用的短名
    kind: report               # dashboard=持续更新看板 / report=一次性研究 / tracker=定期补数
    topics: [个股研究]          # 用于档案页筛选
    source: E:/.../my_report.html   # 本地文件绝对路径（构建时复制 + 清洗 + 注入顶栏）
    slug: my-report            # 发布后的文件名，可省略（默认用 id）
    date: 2026-11-18
    data_asof: 2026-10-26
    summary: 一句话结论（不是「这页有什么」，而是「我得出了什么」）
    theses:                    # 可选：这页产出的可跟踪判断
      - claim: 一句话判断
        status: 跟踪中           # 跟踪中 / 成立 / 存疑 / 证伪
        next_check: 2027-01-31  # 过期会在首页标红
        note: 反证条件或备注
```

3. `build.bat`

不需要改任何代码或模板。外链型研究用 `external: true` + `url: https://...`。

### 3. 发布

```bat
deploy.bat     :: 构建 → 检查通过 → commit → push
```

构建失败（发现本机路径 / 凭证 / 死链）时**不会**提交。

---

## 目录

```
Dan's Investment Dashboard/
├─ research.yaml          ★ 唯一事实源：所有研究条目 + 可跟踪判断
├─ journal/               复盘日志（YYYY-MM-DD.md，_template.md 是模板）
├─ theme/                 theme.css（设计令牌 + 组件）、site.js（主题切换 / 筛选）
├─ sitegen/               构建脚本
│   ├─ model.py           读 research.yaml、校验、派生 URL 与论点状态
│   ├─ sync.py            复制研究页：清洗本机路径 → 注入顶栏 → 扫描敏感串
│   ├─ render.py          首页 / 档案 / 分组页 / 日志页 / 主题样例页
│   └─ build.py           一条命令跑完整站 + 死链检查
├─ build.bat              构建（失败会停下并列出问题）
├─ new_journal.bat        新建今天的日志
├─ preview.bat            本地预览 http://127.0.0.1:8080/
├─ deploy.bat             构建 + 发布
├─ GOALS.md               目标、约束、验收标准
├─ index.html             跳转壳（→ docs/index.html，双击仓库根目录时用）
└─ docs/                  ← 发布产物（GitHub Pages 源）
```

`docs/` 是生成的，**不要手改**，改完下次构建就被覆盖。内容永远只有 `research.yaml` + `journal/` + `theme/` 三处是真源。

## 托管研究页是怎么处理的

源文件留在原目录，构建时对副本做三件事（`sitegen/sync.py`）：

1. **清洗**：把 `E:\...`、`C:\Users\...` 这类本机绝对路径替换为「（本机路径已隐去）」。有些页面的内嵌 JSON 里带 `.cache` 路径，不清洗就等于公开本机目录结构。
2. **注入顶栏**：一条固定顶栏（返回入口 / 分组 / 标题 / 数据截至 / 上一页下一页），用 `html{padding-top}` 让开高度，不动原页面的 `body` 布局和 ECharts 尺寸计算。顶栏会读取页面实际底色自动切浅色/深色。
3. **检查**：全站扫描本机路径、GitHub token、API key、AWS key 等，命中即中止构建并打印文件名和行号。

## 主题

`theme/theme.css` 是唯一的样式来源。规则：

- **涨=红、跌=绿**（A 股习惯），只用于价格与收益变动
- **实际=蓝、指引/预期=琥珀**，与涨跌色含义不重叠
- **观点状态**（跟踪中/成立/存疑/证伪）用第三组色，避免被读成行情
- 数字一律 `.num`（等宽 + `tabular-nums`）
- 默认浅色暖纸底；`data-theme="dark"` 切深色，两套共用同一批令牌

打开 `/theme.html` 能看到全部令牌与组件，那页就是主题的验收依据。

## 依赖

```bat
pip install -r requirements.txt
```

只要 `PyYAML` 和 `Markdown`，无前端构建、无 CDN、无 Node。产物是纯静态文件，`file://` 双击首页也能看（只有依赖 `fetch` 的功能会降级，目前没有）。

## 已知限制

- **首页「今天」是静态卡片**：黄金 / GS50 的最新一句话写在 `research.yaml` 的 `latest:` 里，需要你手动更新。要让它们自动同步，得在那两个仓库的构建脚本里各加一个 `summary.json` 输出（本期没做，避免碰其他项目）。
- **高盛研报那页没上线**：`report_300308_goldman.html` 含第三方研报原文摘录，公开前需要确认引用范围。加进 `research.yaml` 一行即可上线。
- **旧页面不迁主题**：黄金、GS50、300308 现有页面保留各自风格，只加了顶栏。新页面请用 `theme.css`。
