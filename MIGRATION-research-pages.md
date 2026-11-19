# 研究页迁移规格（第二阶段）

> 第一阶段已完成：`index / archive / theme` + 5 个分组首页 + `theme.css` + `render.py` 全部统一到
> 「账本为骨，只留报头一处高音」。
>
> 本文是第二阶段的施工图：把 11 个带内联样式的托管研究页接进同一套令牌。
> 内容全部来自 `docs/research/**` 的实测（色值统计、圆角/阴影计数），不是估计。

---

## 0. 现状盘点（实测）

| 文件 | 体积 | 内联 CSS | 选择器 | `:root` 变量 | `:root` 外硬编码 hex | 圆角 | 阴影 | 底色 | ECharts |
|---|---|---|---|---|---|---|---|---|---|
| `300308/attribution.html` | 534KB | 6.5KB | 79 | 15 | 18 种 | 10 | 1 | 深 | 否 |
| `300308/consensus.html` | 175KB | 9.7KB | 120 | 14 | 31 种 | 13 | 1 | 深 | 否 |
| `300308/gk.html` | 110KB | 8.7KB | 105 | 14 | 22 种 | 12 | 1 | 深 | 否 |
| `300308/stages.html` | 76KB | 7.6KB | 89 | 15 | 18 种 | 10 | 1 | 深 | 否 |
| `300502/consensus.html` | 166KB | 9.7KB | 121 | 14 | 31 种 | 12 | 1 | 深 | 否 |
| `300502/gk.html` | 98KB | 8.7KB | 105 | 14 | 22 种 | 12 | 1 | 深 | 否 |
| `300308/structure.html` | 1193KB | 9.7KB | 112 | 0 | 30 种 | 14 | 2 | 浅 | **是** |
| `300308/structure-q.html` | 1146KB | 7.9KB | 93 | 0 | 26 种 | 12 | 2 | 浅 | **是** |
| `300502/structure.html` | 1185KB | 9.7KB | 112 | 0 | 30 种 | 14 | 2 | 浅 | **是** |
| `300502/structure-q.html` | 1143KB | 7.9KB | 93 | 0 | 26 种 | 12 | 2 | 浅 | **是** |
| `ai-chain/capex.html` | 192KB | 13.4KB | 185 | 17 | 19 种 | 13 | 3 | 浅 | 否 |

**三组，三种问题：**

- **A 组（6 页，深色）**：Tokyo Night 蓝紫配色 + 冷蓝黑底 `#0b0f14`。与「黑金」是两个品牌。
- **B 组（4 页，浅色）**：灰白 + 靛紫 `#6366f1`，4 页共用同一份内联 CSS（两两成对）。
- **C 组（1 页，浅色 `capex.html`）**：已经接近纸本（`#faf9f6 / #191813`），只差圆角与阴影。

**关键发现：涨跌方向是反的。** A 组与 C 组都是「绿涨红跌」：

```
A 组：  .pos{color:var(--green) /* #9ece6a 绿 */}   .neg{color:var(--red) /* f7768e */}  ← 正=绿
C 组：  --up:#1c7a4d (绿)   --down:#b02a1c (红)                                          ← 涨=绿
主题：  --up: 朱 28°   --down: 石绿 158°                                                 ← 涨=红
```

主题对全站只承认一种惯例（README 已写死「红涨绿跌」，A 股）。**迁移时必须显式翻转**，
否则同一个 `+2.17%` 在首页是朱色、在共识页是绿色。

---

## 1. 验收判据

迁移完成后，用下面四条卡：

1. **色值** `grep -c '#[0-9a-fA-F]\{6\}' docs/research/**/*.html` 的 `:root` 外命中数 = 0
   （ECharts 里的 `color:` 字符串除外，见 §4.3）。
2. **形状** 内联 CSS 里 `border-radius: 999px|≥6px` 命中数 = 0；`box-shadow` 命中数 = 0。
3. **语义** `.pos / .neg / .up / .down` 全部指向 `--up`（朱）/ `--down`（石绿），与首页一致。
4. **换肤** 在深色页面上按顶栏「◐ 主题」，页面与顶栏一起翻转（A 组要么随主题翻转，要么锁定深色并说明）。

---

## 2. 令牌映射表

### 2.1 A 组（深色 → 主题深色黑金）

| 研究页 token | 现值 | → 主题 token | 主题值（深色） | 说明 |
|---|---|---|---|---|
| `--bg` | `#0b0f14` 冷蓝黑 | `--paper` | `#130f0a` 暖黑 | 冷→暖，这是品牌差异的根 |
| `--panel` | `#121821` | `--card` | `#1c1712` | |
| `--panel2` | `#151d29` | `--card-2` | `#211c17` | |
| `--line` | `#232c38` 冷灰蓝 | `--line` | `color-mix(#bd8f4e 22%, #1c1712)` | 换成暗金线 |
| `--line2` | `#1b2431` | `--line-soft` | `color-mix(#bd8f4e 12%, #1c1712)` | |
| `--text` | `#e6edf3` 冷白 | `--ink` | `#efe6d4` 暖白 | |
| `--muted` | `#8b98a8` | `--muted` | `#9a9285` | |
| `--dim` | `#63707f` | `--dim` | `#8b8274` | 现 3.8:1 不达标 → 5.0:1 |
| `--green` `#9ece6a` | 正 / 涨 | **`--up`** | `#e89e94` 朱 | **翻转** |
| `--red` `#f7768e` | 负 / 跌 | **`--down`** | `#82c69e` 石绿 | **翻转** |
| `--blue` `#7aa2f7` | 系列 1 | `--actual` / `--ind-t` | `#88b9ec` | |
| `--orange` `#e0af68` | 系列 2 | `--guide` / `--honey-t` | `#d7ac72` | |
| `--purple` `#bb9af7` | 系列 3 | `--series-3` | `#cda2da` | |
| `--cyan` `#7dcfff` | 系列 4 | 需新增 `--series-4` | — | 梅之后没有第 4 色，见 §5 |
| `--accent` `#e0af68` | 强调 | `--brand` | `#d7ac72` | |
| `--gold` `#e8c07d` | 强调 | `--brand` | 同上 | |
| `--gray` `#7a8290` | 中性 | `--muted` | | |

`:root` 外的 18–31 种硬编码色，按上表最近邻替换。最高频的四个是
`#c3cedb`→`--ink-2`、`#c9d4e0`→`--ink-2`、`#dbe4ee`→`--ink`、`#0d1319`→`--card-2`。

### 2.2 B 组（财报结构 4 页）

这 4 页没有 `:root`，颜色直接写在规则里。

| 现值 | 出现次数 | → 主题 token | 说明 |
|---|---|---|---|
| `#6366f1` `#4338ca` 靛紫 | 22 | `--actual`（靛 `#356697`） | 靛是「实际值」的语义色，正好对上 |
| `#eef2ff` `#fafaff` | 14 | `color-mix(in oklch, var(--ind-f) 8%, var(--card))` | 浅底配方，不要用 rgba |
| `#4b5563` `#555` `#666` | 12 | `--ink-2` / `--muted` | |
| `#d1d5db` `#eee` `#fafafa` | 9 | `--line` / `--card-2` | |
| `#f59e0b` `#fff7ed` | 3 | `--warn-bg` + `--up` 左边线 | `.guide-q` / `.guide-falsify` 的警示 |
| `#222` `#333` `#444` `#888` `#999` | 14 | `--ink` / `--ink-2` / `--muted` / `--dim` | |
| `#54a24b` / `#e45756` | 2 | `--down` / `--up` | Vega 默认色，同样要翻转核对 |

### 2.3 C 组（`capex.html`）

已经最接近，只改四处：

| 现值 | → |
|---|---|
| `--bg:#faf9f6` | `--paper:#f7f5f0` |
| `--panel:#fff` | `--card:#fffdf8` |
| `--panel2:#f4f2ec` | `--card-2:#faf6ec` |
| `--ink:#191813` / `--ink2:#4a4842` | `--ink:#1c1712` / `--ink-2:#4a433a` |
| `--up:#1c7a4d` 绿 / `--down:#b02a1c` 红 | `--up` 朱 / `--down` 石绿 **（翻转）** |
| `--actual:#2f6fb3` / `--guide:#b8791a` | `--actual` 靛 / `--guide` 蜜（语义已经对了） |
| `--accent:#7a5cc4` 紫 | `--brand` 蜜，或改成 `--series-3` 梅 |
| `--shadow: 0 1px 2px …` | **删除**，纸本无阴影 |
| `--actual-bg` / `--guide-bg` 的 `rgba()` | `color-mix(in oklch, … 8%/12%, var(--card))` |

---

## 3. 内联 CSS 替换清单

### 3.1 全部 11 页共有的四类改动

```css
/* ① 圆角 → 方角（A 组 10–14 处、B 组 12–14 处、C 组 13 处） */
.kpi, .card, .tbox, .panel, .chartbox, .guide-item,
.guide-core, .guide-falsify, .chip, .pill, pre, code, #tip
  { border-radius: 0; }

/* ② 阴影 → 无（共 15 处） */
* { box-shadow: none !important; }   /* 临时验证用；正式改在具体规则上删 */

/* ③ 胶囊按钮/chip → 下划线或方角细框 */
.chip { border-radius: 0; background: transparent; border-color: var(--line); }

/* ④ 悬停位移 → 只允许颜色变化 */
.card:hover, .panel:hover, .kpi:hover { transform: none; }
```

### 3.2 A 组专属

- `.pos` / `.neg` 两个类名保留（JS 里 `${up>=0?'pos':'neg'}` 直接生成），**只改声明**：
  ```css
  .pos { color: var(--up) !important; }    /* 正 → 朱 */
  .neg { color: var(--down) !important; }  /* 负 → 石绿 */
  ```
- `.up`（stages / attribution / 300502-consensus）同样处理。
- `stages.html` 的 `--sA…--sF` 六段系列色要整体重排到 `--actual / --guide / --series-3` + 三个新增系列色。
- 页面底 `body{background:var(--bg)}` 与 `thead th` 的吸顶背景要一起改，否则换肤后表头会漏色。

### 3.3 B 组专属

- 4 个文件是**两两成对**（`300308/structure` 与 `300502/structure` 的内联 CSS 逐字节相同，
  `structure-q` 同理）。建议抽成一份 `theme/research-structure.css` 由构建注入，
  四个文件各删 8–10KB 内联样式，改一次生效四处。
- `.guide-core / .guide-item / .guide-q / .guide-falsify` 这套「研报导读」是新组件，
  主题页目前没有。迁移时顺手补进 `theme.html` 的组件清单。
- ECharts 配色见 §4.3。

### 3.4 C 组专属

- 圆角 13 处、阴影 3 处是重点；配色基本已对。
- `nav a`、`.tbtn`、`.panel` 的圆角与投影全删。

---

## 4. 三处容易踩的坑

### 4.1 `sync.py` 的顶栏是另一份硬编码

`scripts/sitegen/sync.py` 的 `TOPBAR_STYLE` 里写死了 `#17130e / #a39b8e / #6a5330 / #bd8f4e / #ece6da`，
数值上等于 `theme.css` 的 `--band / --band-muted / --band-line / --brand-f / --band-ink`。
两个副本必须一起改，否则顶栏和页面各说各话。

### 4.2 吸顶表头要让开顶栏

A 组页面有 `thead th{position:sticky}`。`sync.py` 已经用 `thead th{top:44px!important}` 兜住，
但改成 `theme.css` 的 `--topbar-h` 后要改成 `calc(var(--topbar-h) + 0px)`。

### 4.3 ECharts 的颜色是 JS 字符串，CSS 改不到

`structure.html / structure-q.html`（4 个文件）有 28 处 `echarts` 引用，配色写成
`style:'fill:'+(…)` 这种字符串。两条路：

- **推荐**：在页面顶部读一次 CSS 变量，再传给图表：
  ```js
  const css = getComputedStyle(document.documentElement);
  const C = n => css.getPropertyValue(n).trim();
  // color: C('--actual')
  ```
  换肤时需要 `echarts` 实例重绘（监听 `#theme-btn` 点击）。
- **或**：图表配色单独冻结一套，声明「图表不随主题翻转」。功能可用，但换肤后图表会和外框打架。

### 4.4 别用 `!important` 覆盖整页

A 组已有的 `.pos / .neg` 带 `!important`。迁移后主题的 `.up / .down` 一旦也收紧，
两层 `!important` 会互相打架。正确做法是迁移时**把研究页的 `!important` 一起删掉**。

---

## 5. 需要先做的一个决定：第 4 色

主题色板是五个（蜜 / 朱 / 石绿 / 靛 / 梅），但研究页用到了 6–7 个系列：

- A 组：blue / orange / purple / cyan / green / red / gold / gray 共 8 个
- `stages.html`：`--sA…--sF` 六段
- 映射到主题后只有 靛 / 蜜 / 梅 三个可用系列色（朱与石绿已被涨跌占用）

**三个选项，必须先选一个再动手：**

| 方案 | 做法 | 代价 |
|---|---|---|
| **限制为三系列** | 超过三个系列的图改成小倍数图（facet）或折线分级 | 图表要重画，但色板不用扩 |
| **扩到五系列** | 在 OKLCH 里按同样的 L/C 加两个色相（如 青 200°、赭 50°），主题页同步登记 | 色板从 5 变 7，要重算对比度 |
| **系列用明度阶梯** | 同色相不同明度（`--actual` 的 L .50/.68/.86） | 不扩色板，但小图上难分辨 |

---

## 6. 施工顺序

1. **先做 B 组**（4 页）：内联 CSS 完全相同，抽成外链一次搞定 4 页，验证「删 10KB 内联样式页面不坏」。
2. **再做 C 组**（1 页）：配色已对，只删圆角阴影，半小时。
3. **最后做 A 组**（6 页）：要动配色语义（涨跌翻转）+ 系列色收窄，风险最高，放最后。
4. **ECharts 重配**贯穿在 B 组里一起做，因为它只出现在 B 组。
5. 每做完一组，把该组页面加进主题页的组件清单，跑一次 §1 的四条验收。

## 7. 不要做的事

- 不要把研究页的版式改成首页的账本版式。研究页是**长文档**，72ch 正文 + 图表容器 + 复盘导读是它对的地方；
  与主题统一的是**令牌、形状、涨跌语义**，不是版式。
- 不要为了统一而重写 1200 行页面的 HTML 结构。改 CSS 变量和 8 个高频类名就够了。
- 不要在迁移中途删 `docs/`。`docs/` 是产物，源文件在 `research.yaml` 指的原目录，改错了从源头重跑即可。
