# Dan's Investment Dashboard

个人投资研究入口：**首页就是今日看板（黄金 + GS50），研究档案按板块 / 个股 / 方法论三段，判断跟踪到期可查。**

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
        next_check: 2027-01-31  # 过期会在判断跟踪页标朱
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

## 首页「今日看板」（= 两份看板快照）

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
- `tone` 只决定结论徽标的**方向**：`up`=▲ 利多、`down`=▼ 利空、留空=● 观察。
  三者都是墨色——行情色只落在右侧的数字上（红涨绿跌）。
- 想换看板栏版式，改 `scripts/sitegen/home.py` 的 `market_panel()` / `chart()` 和 `theme/theme.css` 的 `.market-boards / .market-panel` 段。

---

## 站点结构（三层）

| 页 | 装什么 | 不装什么 |
|---|---|---|
| `index.html` · **今日看板** | 只有 `today: true` 的两块看板（黄金 / GS50），并列、各自标注数据截至 | 不再有「研究入口」「下次复核」——那两块已分到各自的页 |
| `archive.html` · **研究档案** | 按 `scopes` 三段：板块 / 个股 / 方法论 | 市场看板不放进来（它们就是首页） |
| `theses.html` · **判断跟踪** | 顶部一条「下一组到期」日期带 + 跟踪中 / 已结算全量列表 | — |

档案的分段由 `groups[].scope` 决定：`scope` 缺省的分组（如 `market`）**不进档案**，只作为今日看板的数据源。
加作用域就在 `research.yaml` 的 `scopes:` 下加一条，再把分组的 `scope` 指过去。

### 判断的两个附加字段

```yaml
    theses:
      - claim: …
        status: 跟踪中
        origin: ai              # 可选：AI 代写的初稿。页面上显示「AI 初稿 · 待改写」
        next_check: 2027-01-31
        note: 反证条件或备注
        falsifier: …            # 可选：什么数据出现就算这条错了
        action: …               # 可选：这条对 / 错，我的动作怎么变
```

`origin: ai` 只是**来源标记**，不影响状态与到期计算。自己重写完这条判断后删掉这一行，页面上的虚线标记就消失。
判断跟踪页顶部会把还有多少条 AI 初稿统计出来，提醒还有多少要改。

### 重写那 6 条：三要素模板

现在 6 条全是 `origin: ai`，而且都只有「结论 + 一句备注」。缺的不是文笔，是**可操作性**。
一条能用的判断要同时回答三件事：

| 要素 | 字段 | 写不好会怎样 |
|---|---|---|
| **结论** | `claim` | 写成「A 和 B 有关系」——不可证伪，永远对 |
| **反证** | `falsifier` | 写成「若基本面恶化」——无法观测，永远不到期 |
| **动作** | `action` | 不写——判断对了 / 错了，我的行为一模一样，那就没必要记 |

`note` 保留为补充（口径、样本量、数据来源），不再是反证条件的唯一位置。

**改写示例（旭创共识那条）**

```yaml
# 改前（AI 写的）
- claim: 当前 11.7x 的 PE_NTM 已在近一年最低分位，若 FY2027 共识 655 亿不被下修，
         估值继续压缩的空间有限，风险转移到盈利端。
  note: 触发条件——FY2027 共识出现首次连续两月下修，则本条证伪。

# 改后（三要素齐）
- claim: 旭创现在的低 PE 不是「便宜」，是市场已经不信 FY2027 的 655 亿。
         在共识不动的前提下，估值继续压的空间有限。
  falsifier: 连续两个月 NTM 共识低于 655 亿（下修 > 5%），或 PE_NTM 跌破 9x。
  action: 下修 → 不再是估值问题，改为盯单季毛利率与北美 capex 指引；
          跌破 9x 但不伴随下修 → 加仓，因为分母没变而价格变了。
  next_check: 2026-12-31
  note: 样本 1 家公司、21 家覆盖；低分位不等于低估，分母仍是预测。
```

差别在于：改后这条**任何一个月底都能判定真假**，而且对错对应两个不同的动作。
改前那条只能靠「我觉得」结算。

**推进顺序建议**：先改两条最有用的（旭创共识、AI capex），因为这两条的反证条件本来就是可观测的；
`阶段切分` 那条样本量为 1，建议直接删掉而不是改写——它是研究结论，不是可跟踪判断。

---

## 目录

```
Dan's Investment Dashboard/
├─ research.yaml          ★ 唯一事实源：研究条目 + 可跟踪判断 + 今日卡片数据
├─ scripts/               所有可执行脚本（根目录不放 bat / py）
│   ├─ pull_latest.py     从两个看板抓数，写回 research.yaml 的 auto 块
│   └─ sitegen/           构建引擎
│       ├─ model.py       读 research.yaml、校验、派生 URL / 作用域 / 论点状态
│       ├─ sync.py        复制研究页：清洗本机路径 → 注入顶栏 → 扫描敏感串
│       ├─ home.py        首页看板（线圈、KPI、复核日期带）
│       ├─ render.py      今日看板 / 档案 / 判断跟踪 / 分组页 / 主题样本页
│       └─ build.py       一条命令跑完整站 + 死链检查
├─ scripts/               所有可执行脚本（根目录不放 bat / py）
│   ├─ pull_latest.py     从两个看板抓数，写回 research.yaml 的 auto 块
│   ├─ research_theme_apply.py  把 11 个研究页源文件接进令牌体系（一次性，可重跑）
│   └─ sitegen/           构建引擎
│       ├─ model.py       读 research.yaml、校验、派生 URL / 作用域 / 论点状态
│       ├─ sync.py        复制研究页：清洗本机路径 → 注入顶栏 → 扫描敏感串
│       ├─ home.py        首页看板（线圈、KPI、复核日期带）
│       ├─ render.py      今日看板 / 档案 / 判断跟踪 / 分组页 / 主题样本页
│       └─ build.py       一条命令跑完整站 + 死链检查
├─ theme/                 tokens.css（令牌）、theme.css（站点组件）、research.css（研究页共享层）、
│                         site.js（主题切换 / 筛选）、fonts/（自托管衬线）
├─ sources-snapshot/      11 个研究页源文件的原始快照（未接主题之前，用于回退）
├─ MIGRATION-research-pages.md  第二阶段施工图（令牌映射表与踩坑记录；迁移已落地，留作参照）
├─ index.html             跳转壳（→ docs/index.html，双击仓库根目录时用）
└─ docs/                  ← 发布产物（GitHub Pages 源）
```

`docs/` 是生成的，**不要手改**，改完下次构建就被覆盖。内容永远只有 `research.yaml` + `theme/` 两处是真源。

## 托管研究页是怎么处理的

源文件留在原目录（`research.yaml` 的 `source:` 指向它们），构建时对副本做三件事（`scripts/sitegen/sync.py`）：

1. **清洗**：把 `E:\...`、`C:\Users\...` 这类本机绝对路径替换为「（本机路径已隐去）」。有些页面的内嵌 JSON 里带 `.cache` 路径，不清洗就等于公开本机目录结构。
2. **注入顶栏**：一条固定顶栏（返回入口 / 分组 / 标题 / 数据截至 / 上一页下一页 / 明暗），用 `html{padding-top}` 让开高度，不动原页面的 `body` 布局和 ECharts 尺寸计算。
3. **检查**：全站扫描本机路径、GitHub token、API key、AWS key 等，命中即中止构建并打印文件名和行号。

样式统一**不在这条链里**，而是改源文件的一次性脚本：`scripts/research_theme_apply.py`。

```bash
python scripts/research_theme_apply.py --check   # 只看会改多少处
python scripts/research_theme_apply.py           # 就地改写 11 个源文件
python -m scripts.sitegen.build                  # 再构建
```

它做四件事（幂等，可重复跑）：

1. **内联 CSS 换令牌**：600 多个 hex 换成语义变量；圆角按档位收到 `--r-sm/--r-md/--r-lg`；投影删掉；`rgba()` 浅底换成 `color-mix(in oklch, …)`。
2. **页面脚本换令牌**：颜色串包成 `hx("#7aa2f7")`，配一份页内 `TOKENS` 表，运行期从 `getComputedStyle` 读真实色值——SVG 属性与 ECharts 选项不认 `var()`，只能运行期取。
3. **注入三个脚本**：令牌间接层、ECharts 主题（`echarts.init` 默认带主题，否则 Canvas 里的默认文字色改不到）、切肤重载（点顶栏「明暗」后 `location.reload()`，内联 SVG 与图表跟着换色）。
4. **删掉页内明暗按钮**：`capex.html` 原来有一个自己的按钮和 `ct-theme` 偏好键，与顶栏的 `#theme-btn` 打架，已删除。

改坏的回退点：11 个源文件的原始版本快照在 `sources-snapshot/`（未接主题之前，带 Tokyo Night / 靛紫 / 近纸本三套原样式）。

## 主题

样式拆成三层（改色只改第一层）：

| 文件 | 内容 | 谁引它 |
|---|---|---|
| `theme/tokens.css` | 自托管字体、色板、用途映射、字号与间距阶梯（纯变量） | 所有页面 |
| `theme/theme.css` | 站点组件（顶栏、今日看板、档案行、判断行、表格、图表容器…） | 首页 / 档案 / 判断 / 分组 / 主题页 |
| `theme/research.css` | 研究页共享层：历史变量名别名、形状收敛、涨跌语义、把研究页的同名类（`.foot / .kpi / .tag`）钉回它们自己的声明 | 11 个托管研究页 |

`theme.css` 开头 `@import url("tokens.css")`，所以引了它就不必再引令牌。研究页刻意**不引**
`theme.css`——那一层有 `.foot / .kpi / .tag / .verdict` 等站点组件，会和研窗体里的同名类打架。

形态是**印刷纸本 + 黑金**：纸色做正文，暖黑做书脊（顶栏与页脚），金只做细线和字。

**色板**在 OKLCH 里生成：固定明度与彩度、只转色相，所以每个颜色一样重。主题色是蜜金 74°。

| 色板值 | 色相 | 浅色·文字 | 浅色·色块 | 深色·文字 | 用途 |
|---|---|---|---|---|---|
| 蜜 Honey | 74° | `#835a18` | `#bd8f4e` | `#d7ac72` | 主题色 · 指引 / 预期 |
| 朱 Cinnabar | 28° | `#924c44` | `#cf8075` | `#e89e94` | 涨 · 风险侧栏 · 已到期 |
| 石绿 Jade | 158° | `#29734e` | `#5eab81` | `#82c69e` | 跌 |
| 靛 Indigo | 250° | `#356697` | `#679dd4` | `#88b9ec` | 实际值 · 口径框 |
| 梅 Plum | 318° | `#7a5186` | `#b284c0` | `#cda2da` | 图表第三系列 |
| 青 Qing | 204° | `#007378` | `#38abb1` | `#67c6cb` | 图表第四系列 |
| 赭 Ochre | 50° | `#8e522e` | `#ca865f` | `#e3a480` | 图表第五系列 |

青与赭是后补的两色，只为多系列图表存在（朱与石绿被涨跌占着）。它们不承担业务含义。

用途 → 色板值只有一层映射（`--up` / `--down` / `--actual` / `--guide` / `--brand`），页面里不写死色值。规则：

- **没有外壳**。卡片、看板栏、档案行一律方角、无边框、无阴影、无悬停位移；分栏靠墨线与发丝线，不靠留白和投影。今日看板不是「两张卡」，而是两条并排的账本栏，中间一条竖向发丝线。
- **数据区里金只表示指引**。KPI、表格、图表里出现金色就是预期或指引；数据区里的链接与强调一律用墨色下划线。金色留给顶栏、页脚、小节标记和图表里的预期柱。
- **结论不占行情色**。涨跌色只落在数字上；结论与状态用形状区分——结论是 ▲▼●（墨色），状态是空心圈 / 实心 / 半圆 / 删除线，只有「已到期」借朱。这样「利空」不会和「跌」撞成同一个绿。
- **手动才动**。页面加载时没有任何动画，走势线是静态的绝对值走势（画的是价格，不是涨跌，所以也是墨色）；动效只由用户操作触发，150–250ms。
- **浅底在 OKLCH 里混色**（`color-mix(in oklch, 色块档 9%, 卡片)`），不用 rgba 叠在暖纸色上，所以口径框不会发灰。
- 数字一律 `.num`（等宽 + `tabular-nums`）；大数字与分组页标题用自托管的 Newsreader 衬线。
- 浅色为默认（顶栏与页脚是「中」档黑金带）；`data-theme="dark"` 切到完整黑金，分隔线混入 22% 的金，所以是暗金光而不是灰线。

打开 `/archive/theme.html`（存档页，不在导航里）能看到色相环、四档色值，以及**各页真正在用的每一个组件**（今日看板、复核日期带、判断行、档案行、筛选与分组、KPI、表格、提示框、图表容器、长文本）。那页就是主题的验收依据：改令牌之前先在那里确认它不是多余的。

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
- **研究页的样式统一是一次性脚本改的源文件**（`scripts/research_theme_apply.py`）。下次从 skill 重新生成页面（`report_pack.py`）会**覆盖**这些改动，届时要把同样的令牌化逻辑搬进 `.pi/skills/report-*/scripts/*_template.html`。
  这是刻意的取舍：先把站内 11 页改对、可验收，再改生成器。
- **切明暗会重载页面**：研究页的 SVG / ECharts 是脚本画的，切肤后必须重画；用 `location.reload()` 换可靠，代价是丢滚动位置与已展开的 `<details>`。
- **`300308/consensus` 页里有三段模板没有的手写块**（数据与口径 / 图层与操作 / 事件与分段规则）。现有的 HTML 保留着；下次用 `consensus.py` 重生该页会丢这三段，需要先补进模板。
