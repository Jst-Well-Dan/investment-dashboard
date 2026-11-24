"""SVG 图表原语 —— 只画图，不做业务判断。

所有图都画在 1120 宽的虚拟画布上（CSS 负责缩放到容器宽，窄屏横向滑动），
与 gs50 看板同一套做法：`<svg viewBox="0 0 1120 H">` + `width:100%`。

配色不在这里定义：全部是主题令牌名（var(--…)），真源在 Dan's Investment
Dashboard 的 theme/tokens.css（本站由 scripts/theme.css 同步进来；页面被托管进
站点时则走站点的 assets/tokens.css，同名令牌，所以两边一致）。
底 --paper / 面板 --card / 网格 --line-soft / 轴线 --line-strong；
主序列 --actual / 次序列 --series-5 / 第三 --series-3 / 中性 --muted。
令牌名写进 SVG 属性也能解析（Chrome / Firefox 实测都支持），所以明暗切换时
不用重画图，整页 reload 后颜色自动跟着 tokens.css 走。
"""
import json
import math

INK = "var(--ink)"
DIM = "var(--muted)"
GRID = "var(--line-soft)"
AXIS = "var(--line-strong)"
S1 = "var(--actual)"
S2 = "var(--series-5)"
S3 = "var(--series-3)"
NEU = "var(--muted)"
BAND = "var(--actual)"

FONT = ("var(--font-sans,-apple-system,'PingFang SC',"
        "'Microsoft YaHei',sans-serif)")
MONO = "var(--font-mono,ui-monospace,Menlo,Consolas,monospace)"

W = 1120
L, R = 62, 86           # 左边留给 y 轴刻度，右边留给末端读数
TITLE_H = 32            # 标题带
XB = 26                 # x 轴刻度带
GAP = 44                # 面板间距


# ------------------------------------------------------------------ 工具
def _f(v, nd=1):
    """数字格式化，去掉多余的小数点"""
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return ""
    s = f"{v:.{nd}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def nice_ticks(lo, hi, target=5):
    """线性轴刻度：把区间切成 1/2/2.5/5×10^k 的整齐步长"""
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    out, v = [], math.ceil(lo / step) * step
    while v <= hi + step * 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def log_ticks(lo, hi):
    """对数轴刻度：1/2/3/5/7 ×10^k，太密就退成 1/2/5"""
    cands = []
    for k in range(-3, 7):
        for m in (1, 2, 3, 5, 7):
            v = m * 10 ** k
            if lo * 0.999 <= v <= hi * 1.001:
                cands.append(v)
    # 太密（>9 个）只留 1/2/5
    if len(cands) > 9:
        cands = [v for v in cands if round(v / 10 ** round(math.log10(v)),
                                          6) in (1, 2, 5)]
    return cands


# ------------------------------------------------------------------ 面板
class Panel:
    """一块绘图区：负责刻度、网格、坐标映射。

    y0 是上边（大值），y1 是下边（小值）—— 这样 xy() 可以直接吐屏幕坐标。
    """

    def __init__(self, top, height, lo, hi, *, log=False, n=1,
                 title="", sub="", yfmt=None, ylab="", yticks=None,
                 grid=True, zero=False, right=None):
        self.top, self.h = top, height
        self.x0, self.x1 = L, W - (R if right is None else right)
        self.y0 = top + TITLE_H
        self.y1 = self.y0 + height
        self.lo, self.hi = lo, hi
        self.log = log
        self.n = n
        self.title, self.sub, self.ylab = title, sub, ylab
        self.yfmt = yfmt or (lambda v: _f(v, 0))
        self.grid = grid
        self.zero = zero
        self.yticks = yticks if yticks is not None else (
            log_ticks(lo, hi) if log else nice_ticks(lo, hi, 5))

    # 映射
    def x(self, i):
        return self.x0 if self.n <= 1 else self.x0 + (self.x1 - self.x0) * i / (self.n - 1)

    def y(self, v):
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return None
        if self.log:
            v = max(v, 1e-9)
            a, b = math.log(self.lo), math.log(self.hi)
            t = (math.log(v) - a) / (b - a) if b > a else 0
        else:
            t = (v - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0
        return self.y1 - t * (self.y1 - self.y0)

    def pt(self, i, v):
        yy = self.y(v)
        return None if yy is None else (self.x(i), yy)

    # 绘制：底 + 网格 + y 轴 + 标题
    def frame(self):
        o = [f'<rect x="{self.x0}" y="{self.y0}" width="{self.x1 - self.x0}" '
             f'height="{self.y1 - self.y0}" fill="var(--card-2)" rx="3"/>']
        if self.title:
            o.append(f'<text x="{self.x0}" y="{self.top + 17}" fill="{INK}" '
                     f'font-size="14" font-weight="600" '
                     f'font-family="{FONT}">{esc(self.title)}</text>')
        if self.sub:
            o.append(f'<text x="{self.x1}" y="{self.top + 17}" fill="{DIM}" '
                     f'font-size="12" text-anchor="end" '
                     f'font-family="{MONO}">{esc(self.sub)}</text>')
        for v in self.yticks:
            yy = self.y(v)
            if yy is None or yy < self.y0 - 1 or yy > self.y1 + 1:
                continue
            if self.grid:
                o.append(f'<line x1="{self.x0}" x2="{self.x1}" y1="{yy:.1f}" y2="{yy:.1f}" '
                         f'stroke="{GRID}" stroke-width="1"/>')
            o.append(f'<text x="{self.x0 - 9}" y="{yy + 4:.1f}" fill="{DIM}" font-size="11.5" '
                     f'text-anchor="end" font-family="{MONO}">{esc(self.yfmt(v))}</text>')
        if self.zero and self.lo < 0 < self.hi:
            yy = self.y(0)
            o.append(f'<line x1="{self.x0}" x2="{self.x1}" y1="{yy:.1f}" y2="{yy:.1f}" '
                     f'stroke="var(--line-strong)" stroke-width="1"/>')
        if self.ylab:
            o.append(f'<text x="{self.x0 - 9}" y="{self.y0 - 7}" fill="{DIM}" font-size="11" '
                     f'text-anchor="end" font-family="{MONO}">{esc(self.ylab)}</text>')
        return "".join(o)


# ------------------------------------------------------------------ 图元
def _decimate(n, cap=1500):
    """点数远超像素宽度时抽稀：保留首尾 + 等距采样，5000 点→1500 点肉眼看不出差别"""
    if n <= cap:
        return list(range(n)), None
    step = n / cap
    keep = sorted({int(k * step) for k in range(cap)} | {0, n - 1})
    return keep, set(keep)


def path(panel, vals, *, color=S1, width=1.5, dash=None, opacity=1.0, cap=1500):
    """折线；NaN 处断开（不画，也不跳到 0）"""
    segs, cur = [], []
    keep, kset = _decimate(len(vals), cap)
    for i, v in enumerate(vals):
        if kset is not None and i not in kset:
            continue
        p = panel.pt(i, v)
        if p is None:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) > 1:
        segs.append(cur)
    if not segs:
        return ""
    d = "".join("M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in s) for s in segs)
    a = f' stroke-dasharray="{dash}"' if dash else ""
    op = f' opacity="{opacity}"' if opacity != 1 else ""
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round" stroke-linecap="round"{a}{op}/>')


def band(panel, lo_vals, hi_vals, *, color=BAND, opacity=0.13, cap=900):
    """上下轨之间的填充带（置信区间 / 布林带）"""
    top, bot = [], []
    keep, kset = _decimate(panel.n, cap)
    for i in keep:
        a = panel.y(hi_vals[i]) if hi_vals[i] is not None else None
        b = panel.y(lo_vals[i]) if lo_vals[i] is not None else None
        if a is None or b is None:
            continue
        top.append((panel.x(i), a))
        bot.append((panel.x(i), b))
    if len(top) < 2:
        return ""
    d = ("M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in top)
         + "L" + "L".join(f"{x:.0f},{y:.0f}" for x, y in reversed(bot)) + "Z")
    return f'<path d="{d}" fill="{color}" opacity="{opacity}"/>'


def hline(panel, v, *, color="var(--muted)", dash="4 4", width=1):
    yy = panel.y(v)
    if yy is None or yy < panel.y0 - 1 or yy > panel.y1 + 1:
        return ""
    return (f'<line x1="{panel.x0}" x2="{panel.x1}" y1="{yy:.1f}" y2="{yy:.1f}" '
            f'stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')


def endlabel(panel, v, text, *, color=S1, dy=0):
    """右端读数：小圆点钉在真实值上，文字可再 dy 错开（两条线靠得近时不打架）"""
    yy = panel.y(v)
    if yy is None:
        return ""
    return (f'<circle cx="{panel.x1}" cy="{yy:.1f}" r="2.6" fill="{color}"/>'
            f'<text x="{panel.x1 + 9}" y="{yy + dy + 4:.1f}" fill="{color}" font-size="12" '
            f'font-family="{MONO}" font-weight="600">{esc(text)}</text>')


def endlabels(panel, items, *, gap=15, pad=5):
    """右侧末端读数（多条）：圈钉在真值上，文字按最小间距 gap 上下推开

    两条线末尾贴得很近时（61% / 67%），单独调 dy 不够用，这里统一避让。
    items = [(值, 文本, 颜色), ...]
    """
    pts = [(panel.y(v), t, c) for v, t, c in items]
    pts = [p for p in pts if p[0] is not None]
    if not pts:
        return ""
    labs = sorted(pts, key=lambda p: p[0])
    ys = [p[0] for p in labs]
    for i in range(1, len(ys)):
        if ys[i] - ys[i - 1] < gap:
            ys[i] = ys[i - 1] + gap
    if ys and ys[-1] > panel.y1 - pad:                 # 溢出下边界就整体上移
        shift = ys[-1] - (panel.y1 - pad)
        ys = [y - shift for y in ys]
    out = []
    for (y0, t, c), y in zip(labs, ys):
        out.append(f'<circle cx="{panel.x1}" cy="{y0:.1f}" r="2.6" fill="{c}"/>')
        out.append(f'<text x="{panel.x1 + 9}" y="{y + 4:.1f}" fill="{c}" font-size="12" '
                   f'font-family="{MONO}" font-weight="600">{esc(t)}</text>')
    return "".join(out)


def _txt_w(s, size=12):
    """估算文本像素宽：CJK / 全角算一个字宽，ASCII 算 0.58 字宽"""
    w = 0.0
    for ch in str(s):
        w += size * (1.0 if ord(ch) > 0x2E80 else 0.58)
    return w


def legend(panel, items, *, x=None, y=None):
    """图例：左上角，带半透明底（宽度按实际字宽估，CJK 不再溢出）"""
    x = panel.x0 + 10 if x is None else x
    y = panel.y0 + 6 if y is None else y
    bw = max(_txt_w(t) for t, _, _ in items) + 46
    bh = 8 + len(items) * 18
    o = [f'<rect x="{x}" y="{y}" width="{bw:.0f}" height="{bh}" rx="4" '
         f'fill="var(--card)" opacity="0.92" stroke="{AXIS}"/>']
    for k, (t, c, dash) in enumerate(items):
        yy = y + 14 + k * 18
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<line x1="{x + 8}" x2="{x + 26}" y1="{yy}" y2="{yy}" '
                 f'stroke="{c}" stroke-width="2"{da}/>')
        o.append(f'<text x="{x + 32}" y="{yy + 4}" fill="{INK}" font-size="12" '
                 f'font-family="{FONT}">{esc(t)}</text>')
    return "".join(o)


def badge(panel, text, *, color="var(--ink-2)", corner="lt"):
    """角标：把当前读数写在图上（%B / 带宽 / 偏离率）"""
    x = panel.x0 + 8 if "l" in corner else panel.x1 - 8
    y = panel.y0 + 8 if "t" in corner else panel.y1 - 28
    anchor = "start" if "l" in corner else "end"
    bw = _txt_w(text, 11.5) + 12
    bx = x - 5 if "l" in corner else x - bw + 5
    return (f'<rect x="{bx:.0f}" y="{y}" width="{bw:.0f}" height="20" rx="4" '
            f'fill="var(--card-2)" opacity="0.95" stroke="{AXIS}"/>'
            f'<text x="{x}" y="{y + 14}" fill="{color}" font-size="11.5" '
            f'text-anchor="{anchor}" font-family="{MONO}">{esc(text)}</text>')


def xaxis_years(panel, dates, every=None):
    """x 轴按年刻度：每年第一根 K 线处画竖线 + 年份"""
    o, ticks = [], []
    for i, d in enumerate(dates):
        if d[4:6] == "01" and (i == 0 or dates[i - 1][:4] != d[:4]):
            ticks.append((i, d[:4]))
    if not ticks:
        return ""
    if every is None:
        span = int(dates[-1][:4]) - int(dates[0][:4])
        every = 1 if span <= 8 else 2 if span <= 14 else 4
    skip = set()
    for k in range(len(ticks) - 1, -1, -every):
        skip.add(ticks[k][0])
    for i, yr in ticks:
        xx = panel.x(i)
        o.append(f'<line x1="{xx:.0f}" x2="{xx:.0f}" y1="{panel.y0}" y2="{panel.y1}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        if i in skip:
            o.append(f'<text x="{xx:.0f}" y="{panel.y1 + 16}" fill="{DIM}" font-size="11.5" '
                     f'text-anchor="middle" font-family="{MONO}">{yr}</text>')
    return "".join(o)


def xaxis_dates(panel, dates, n=6):
    """x 轴按日期：等距取 n 个刻度（年份跨度不足 3 年时用）"""
    if not dates:
        return ""
    o = []
    step = max((len(dates) - 1) // (n - 1), 1)
    for i in range(0, len(dates), step):
        xx = panel.x(i)
        o.append(f'<line x1="{xx:.0f}" x2="{xx:.0f}" y1="{panel.y0}" y2="{panel.y1}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        lab = dates[i][:4] + "/" + dates[i][4:6]
        o.append(f'<text x="{xx:.0f}" y="{panel.y1 + 16}" fill="{DIM}" font-size="11" '
                 f'text-anchor="middle" font-family="{MONO}">{lab}</text>')
    return "".join(o)


# ------------------------------------------------------------------ 组装
def svg(panels, height, *, footer=""):
    """把若干面板拼成一张 svg"""
    body = "".join(panels)
    if footer:
        body += (f'<text x="{W - 6}" y="{height - 6}" fill="var(--dim)" font-size="10.5" '
                 f'text-anchor="end" font-family="{MONO}">{esc(footer)}</text>')
    return (f'<svg viewBox="0 0 {W} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img">{body}</svg>')


def total_height(heights):
    """heights = 各面板绘图区高度列表 → 整张图的总高（含底部刻度带）"""
    tops = layout(heights)
    return tops[-1] + TITLE_H + heights[-1] + 42


def layout(heights):
    """依次给出每个面板的 top 坐标"""
    tops, cur = [], 0
    for k, h in enumerate(heights):
        tops.append(cur)
        cur += TITLE_H + h + XB + (GAP if k < len(heights) - 1 else 0)
    return tops


# ------------------------------------------------------------------ 悬浮
class Hover:
    """收集所有图的悬停数据，最后一次性塞进页面。

    每块面板挂一个透明 rect（就是它的绘图区），mousemove 时换算成下标。
    只在 ≤1200 个采样点上传数据，避免 payload 过大；线本身仍是全分辨率。
    """

    def __init__(self):
        self.items = []

    def add(self, dates, panel, series, *, unit="", dec=2, label=""):
        """dates 等长于各序列；series = [(名字, 数值列表, 小数位), ...]"""
        n = len(dates)
        step = max(n // 400, 1)
        idx = list(range(0, n, step))
        if idx[-1] != n - 1:
            idx.append(n - 1)
        hid = f"h{len(self.items)}"
        self.items.append({
            "id": hid, "label": label,
            "x0": round(panel.x0, 1), "x1": round(panel.x1, 1),
            "y0": round(panel.y0, 1), "y1": round(panel.y1, 1),
            "w": W, "unit": unit,
            "d": [dates[i] for i in idx],
            "s": [[nm, [None if vals[i] is None or (isinstance(vals[i], float)
                                                    and math.isnan(vals[i]))
                        else round(float(vals[i]), 3) for i in idx], dd]
                  for nm, vals, dd in series],
        })
        return (f'<rect class="hv" x="{panel.x0}" y="{panel.y0}" '
                f'width="{panel.x1 - panel.x0}" height="{panel.y1 - panel.y0}" '
                f'fill="transparent" data-hv="{hid}"/>')

    def json(self):
        return json.dumps(self.items, ensure_ascii=False, separators=(",", ":"))


HOVER_JS = r"""
(function(){
  var el = document.getElementById('hvdata');
  if (!el) return;
  var DATA = JSON.parse(el.textContent);
  var byId = {}; DATA.forEach(function(d){ byId[d.id] = d; });
  var tip = document.getElementById('tip'), active = null;
  function show(ev){
    var t = ev.target;
    if (!t || !t.getAttribute || !t.getAttribute('data-hv')) { hide(); return; }
    var d = byId[t.getAttribute('data-hv')];
    if (!d) { hide(); return; }
    var svg = t.ownerSVGElement;
    var r = svg.getBoundingClientRect();
    var sc = r.width / d.w;
    var vx = (ev.clientX - r.left) / sc;
    var p = (vx - d.x0) / (d.x1 - d.x0);
    p = Math.max(0, Math.min(1, p));
    var i = Math.round(p * (d.d.length - 1));
    var dt = d.d[i], rows = [];
    for (var k = 0; k < d.s.length; k++){
      var v = d.s[k][1][i], dd = d.s[k][2];
      rows.push('<span style="color:var(--muted)">' + d.s[k][0] + '</span> ' +
                '<b style="color:var(--ink);font-family:var(--font-mono,ui-monospace),monospace">' +
                (v === null ? '—' : v.toFixed(dd) + d.unit) + '</b>');
    }
    tip.innerHTML = '<div style="color:var(--muted);font:600 11px var(--font-mono,ui-monospace),monospace;' +
                    'letter-spacing:.06em;margin-bottom:4px">' +
                    dt.slice(0,4)+'-'+dt.slice(4,6)+'-'+dt.slice(6,8) + '</div>' +
                    rows.join('<br>');
    tip.style.opacity = 1;
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var x = ev.clientX + 16, y = ev.clientY - th - 12;
    if (x + tw > innerWidth - 8) x = ev.clientX - tw - 16;
    if (y < 8) y = ev.clientY + 20;
    tip.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    active = d.id;
  }
  function hide(){ tip.style.opacity = 0; active = null; }
  document.addEventListener('mousemove', function(ev){
    if (ev.target && ev.target.getAttribute && ev.target.getAttribute('data-hv')) show(ev);
    else if (active) hide();
  }, {passive:true});
  document.addEventListener('touchstart', function(ev){
    if (ev.target && ev.target.getAttribute && ev.target.getAttribute('data-hv')) show(ev.touches[0]);
  }, {passive:true});
  window.addEventListener('scroll', function(){ if (active) hide(); }, {passive:true});
})();
"""
