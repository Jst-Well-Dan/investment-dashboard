# Dan's Investment Dashboard

个人投资研究入口：**一个首页看到全部研究、今天两个看板的实时结论、所有在跟踪的判断。**

- 线上：https://jst-well-dan.github.io/investment-dashboard/
- 目标与验收标准：见 `GOALS.md`
- 黄金看板、GS50 看板仍是独立仓库、独立 Actions，本站只做入口和链接（不复制、不改动）。

---

## 日常两件事

### 1. 刷新今天的数据

在仓库根目录跑：

```bash
python scripts/pull_latest.py        # 从黄金 / GS50 的数据里抓今天的数字，写回 research.yaml
python -m scripts.sitegen.build      # 重建整站 + 检查
```

`scripts/pull_latest.py` 只替换 `research.yaml` 里每条研究 `latest:` 下 `# >>> auto` 到 `# <<< auto`
之间的内容；你手写的 `text:` / `summary:` 一个字都不动。源文件找不到时会跳过并提示，
不会把 `research.yaml` 写成半截。

### 2. 加一项新研究

1. 把 HTML 放到任何地方（**不用搬进这个仓库**），例如 `E:\...\my_report.html`
2. 在 `research.yaml` 的 `research:` 下加一条：

```yaml
  - id: my-report              # 唯一，用于 URL 和站内引用
    group: 300308              # 必须是 groups 里已有的 id
    title: 中际旭创 · 某某分析   # 显示在卡片和页面标题
    short: 某某分析             # 可选，标签/链接用的短名
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

3. `python -m scripts.sitegen.build`

不需要改任何代码或模板。外链型研究用 `external: true` + `url: https://...`。

### 3. 发布

```bash
python -m scripts.sitegen.build && git add -A && git commit -m "build: $(date +%F)" && git push
```

构建失败（发现本机路径 / 凭证 / 死链）时**不会**走到 commit。

---

## 首页「今天」卡片

显示什么由 `research.yaml` 里两条看板条目的 `latest:` 决定：

```yaml
    latest:
      date: 2026-11-11                       # 手写：一句话对应的日期
      text: 升温 69 分，名单跑赢沪深 300 …    # 手写：你自己的一句话结论
      # >>> auto（由 pull_latest.py 写入，不要手改）
      asof: 2026-11-11                       # 数据实际截止日
      verdict: "升温 · 69 分"                 # 右上角徽标
      tone: up                               # 卡片左边框色：up=红 / down=绿
      metrics:                               # 第 1 个是大数字，后 3 个是 KPI 列
        - {k: 温度指数, v: "68.9", u: "分", d: "+8.7 较昨日", tone: up}
        …
      spark: [46.9, 37.5, …]                 # 40 个点，画成 inline SVG 走势线
      # <<< auto
```

- 手写的 `text:` **优先**；没写时退回 auto 块里的 `text_auto:`，再退回条目的 `summary:`。
- `auto` 块缺失也能构建，会自动退回旧的纯文字卡（不会报错）。
- `tone` 决定颜色：`up`=涨/利多（红）、`down`=跌/利空（绿）、留空=中性。
- 想换卡片版式，改 `scripts/sitegen/render.py` 的 `today_card()` 和 `theme/theme.css` 的 `.today` 段。
  备选方案（5 种）在 `design/today-cards.html`，跑 `python design/gen_today.py` 可以重生成。

---

## 目录

```
Dan's Investment Dashboard/
├─ research.yaml          ★ 唯一事实源：研究条目 + 可跟踪判断 + 今日卡片数据
├─ scripts/               所有可执行脚本（根目录不放 bat / py）
│   ├─ pull_latest.py     从两个看板抓数，写回 research.yaml 的 auto 块
│   └─ sitegen/           构建引擎
│       ├─ model.py       读 research.yaml、校验、派生 URL 与论点状态
│       ├─ sync.py        复制研究页：清洗本机路径 → 注入顶栏 → 扫描敏感串
│       ├─ render.py      首页 / 档案 / 分组页 / 主题样本页
│       └─ build.py       一条命令跑完整站 + 死链检查
├─ theme/                 theme.css（设计令牌 + 组件）、site.js（主题切换 / 筛选）
├─ design/                设计稿（不进构建）：today-cards.html 是今日卡片备选方案
├─ GOALS.md               目标、约束、验收标准
├─ index.html             跳转壳（→ docs/index.html，双击仓库根目录时用）
└─ docs/                  ← 发布产物（GitHub Pages 源）
```

`docs/` 是生成的，**不要手改**，改完下次构建就被覆盖。内容永远只有 `research.yaml` + `theme/` 两处是真源。

## 托管研究页是怎么处理的

源文件留在原目录，构建时对副本做三件事（`scripts/sitegen/sync.py`）：

1. **清洗**：把 `E:\...`、`C:\Users\...` 这类本机绝对路径替换为「（本机路径已隐去）」。有些页面的内嵌 JSON 里带 `.cache` 路径，不清洗就等于公开本机目录结构。
2. **注入顶栏**：一条固定顶栏（返回入口 / 分组 / 标题 / 数据截至 / 上一页下一页），用 `html{padding-top}` 让开高度，不动原页面的 `body` 布局和 ECharts 尺寸计算。顶栏是黑金带，纯 CSS，不注入脚本。
3. **检查**：全站扫描本机路径、GitHub token、API key、AWS key 等，命中即中止构建并打印文件名和行号。

## 主题

`theme/theme.css` 是唯一的样式来源。形态是**印刷纸本 + 黑金**：纸色做正文，暖黑做书脊（顶栏与页脚），金只做细线和字。

**色板**在 OKLCH 里生成：固定明度与彩度、只转色相，所以每个颜色一样重。主题色是蜜金 74°。

| 色板值 | 色相 | 浅色·文字 | 浅色·色块 | 深色·文字 | 用途 |
|---|---|---|---|---|---|
| 蜜 Honey | 74° | `#835a18` | `#bd8f4e` | `#d7ac72` | 主题色 · 指引 / 预期 |
| 朱 Cinnabar | 28° | `#924c44` | `#cf8075` | `#e89e94` | 涨 · 风险框 · 已到期 |
| 石绿 Jade | 158° | `#29734e` | `#5eab81` | `#82c69e` | 跌 |
| 靛 Indigo | 250° | `#356697` | `#679dd4` | `#88b9ec` | 实际值 · 口径框 |
| 梅 Plum | 318° | `#7a5186` | `#b284c0` | `#cda2da` | 备用：图表第三条系列 |

用途 → 色板值只有一层映射（`--up` / `--down` / `--actual` / `--guide` / `--brand`），页面里不写死色值。规则：

- **数据区里金只表示指引**。KPI、表格、图表里出现金色就是预期或指引；数据区里的链接与强调一律用墨色下划线。金色留给顶栏、页脚、小节标记和图表里的预期柱。
- **判断状态不占色板**：跟踪中空心圈、成立实心、存疑半圆、证伪删除线，颜色都是墨色；只有「已到期」借朱。
- **浅底在 OKLCH 里混色**（`color-mix(in oklch, 色块档 9%, 卡片)`），不用 rgba 叠在暖纸色上，所以口径框不会发灰。
- 数字一律 `.num`（等宽 + `tabular-nums`）；大数字用衬线（Cambria / Georgia）。
- 浅色为默认（顶栏与页脚是「中」档黑金带）；`data-theme="dark"` 切到完整黑金，分隔线混入 22% 的金，所以是暗金光而不是灰线。

打开 `/theme.html` 能看到色相环、四档色值与全部组件，那页就是主题的验收依据。

## 依赖

```bash
pip install -r requirements.txt
```

只要 `PyYAML`，无前端构建、无 CDN、无 Node。产物是纯静态文件，`file://` 双击首页也能看。

## 本地预览

```bash
python -m http.server 8080 --directory docs
```

## 已知限制

- **「今天」的数字要手动刷一次**：跑 `python scripts/pull_latest.py` 才会更新，构建本身不联网、不读别的仓库。
  这是刻意的——`research.yaml` 是唯一事实源，构建必须离线可复现。
- **高盛研报那页没上线**：`report_300308_goldman.html` 含第三方研报原文摘录，公开前需要确认引用范围。加进 `research.yaml` 一行即可上线。
- **旧页面不迁主题**：黄金、GS50、300308 现有页面保留各自风格，只加了顶栏。新页面请用 `theme.css`。
