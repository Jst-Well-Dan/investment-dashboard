# 首页工作台

- Target: docs/index.html
- Source: scripts/sitegen/home.py, scripts/sitegen/render.py, theme/theme.css, theme/site.js
- Mode: Operate。每天复盘市场快照、打开待验证判断、进入研究。
- 用户已批准 design-previews/research-workbench-concept.png 的工作台布局；本轮明确要求保留 docs/theme.html 的原有色板，并新增 DESIGN.md。
- 不重新设计研究原文；不更改投资判断、数字或刷新数据。不引入框架、CDN、构建依赖。

## Direction contract

THESIS: 首页从研究报纸变成个人工作台。今日看板独占整行、两个看板并列同时完整展示（无 tab 切换）；下一行是按检查日期归组的复核队列；下方只有少量研究入口，而非全文档案。

OWN-WORLD: 沿用蜜金、朱、石绿、靛、梅的全部浅深色值，纸底与暖黑带也不变。靛色用于实际走势，蜜金用于导航选中与预期。独立功能面板以细边框、12px 圆角与24px 间距分隔，无发光投影。正文与首页数据使用系统无衬线，同宽数字。

STORY: 先看到数据截至日期与实际变化，随后查看最近一组待检查判断，展开可读完整判断及反证条件，最后从真实研究图表进入原文。全量研究和全量判断各有入口。

FIRST VIEWPORT: 桌面单列纵向布局：紧凑顶栏、32px 今日复盘标题、48px 主数值；今日看板一行内两栏并列（发丝线分隔），各自约220px 趋势图；复核面板在下一行，左栏日期与入口、右栏逐条判断。移动端按市场→复核→研究顺序单列。主操作是展开判断、打开原文与查看采样值（不再有看板切换）。

FORM: 用户指定并批准的工作台原型，配色服从主题色板约束，不做随机候选。交互签名为并列看板的同时可见与真实采样点查看；主题样本页移到 docs/archive/theme.html 并从主导航移除。保留无JS内容、键盘导航与明暗模式。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## 验收

构建成功、数据口径清楚、无虚构图表；桌面/移动端及浅深模式截图与交互检查。没有获得子代理授权，因此由当前会话执行并明确记录单会话审查。不改既有未提交内容之外的无关文件。
