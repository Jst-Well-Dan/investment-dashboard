"""页面骨架零件：深色 CSS、滚动高亮 JS、卡片与图容器。

从 build_charts.py 里抽出来的 —— 那个文件已经删了（8 图版不再维护），
但 spread.html 还需要这套样式，所以独立成模块。
"""
import html

import pandas as pd


def esc(t):
    return html.escape(str(t), quote=False)


def f(v, nd=2, sign=False):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return (f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}")


def cls(v, flip=False):
    """涨红跌绿（A 股习惯）；flip=True 时反过来"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    up = v > 0
    if flip:
        up = not up
    return "up" if up else ("down" if v < 0 else "")




CSS = """
/* 色板 / 字体 / 涨跌语义来自 theme.css（与 Dan's Investment Dashboard 同一份），
   这里只写版式，一律引 var(--…)。 */
:root{--mono:var(--font-mono);--sans:var(--font-sans);--bar:56px;--side:212px}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
-webkit-font-smoothing:antialiased}
::selection{background:var(--sel-bg);color:var(--ink)}
*{scrollbar-width:thin;scrollbar-color:var(--line-strong) transparent}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--line-strong);border-radius:9px;border:2px solid var(--paper)}
::-webkit-scrollbar-thumb:hover{background:var(--line-strong)}
:focus-visible{outline:2px solid var(--brand);outline-offset:2px;border-radius:7px}

.bar{position:sticky;top:0;z-index:60;padding:7px 0;background:color-mix(in oklch, var(--paper) 90%, transparent);
backdrop-filter:blur(14px) saturate(1.25);border-bottom:1px solid var(--line)}
.bar-in{max-width:1380px;margin:0 auto;height:calc(var(--bar) - 14px);display:flex;
align-items:center;gap:9px;padding:0 22px}
.brand{display:flex;align-items:center;gap:9px;font-size:14px;font-weight:600;
white-space:nowrap;color:var(--ink);text-decoration:none}
.brand .dot{width:8px;height:8px;border-radius:99px;background:var(--accent);
outline:1px solid var(--line-strong);outline-offset:2px}
.bar .sp{flex:1}
.bar .theme-toggle{flex:0 0 auto;margin-left:2px}
.btn{display:inline-flex;align-items:center;gap:7px;min-height:38px;padding:9px 15px;
border:1px solid var(--line-strong);border-radius:9px;background:var(--card);color:var(--ink-2);
font:500 13.4px/1 inherit;text-decoration:none;white-space:nowrap;cursor:pointer;
transition:background .16s,border-color .16s,color .16s}
.btn:hover{background:var(--paper-2);border-color:var(--line-strong);color:var(--card)}
.btn.pri{background:var(--guide-bg);border-color:var(--brand-f);color:var(--brand)}
.btn.pri:hover{background:var(--guide-bg);border-color:var(--brand-f)}
.btn.off{background:var(--card-2);border-color:var(--line);color:var(--muted);cursor:default;pointer-events:none}
.btn svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:1.7;
stroke-linecap:round;stroke-linejoin:round}
.prog{position:absolute;left:0;right:0;bottom:-1px;height:2px}
.prog i{display:block;height:2px;width:100%;background:var(--actual);transform:scaleX(0);
transform-origin:left;transition:transform .12s linear}

.shell{max-width:1380px;margin:0 auto;padding:26px 22px 96px;display:grid;
grid-template-columns:var(--side) minmax(0,1fr);gap:36px;align-items:start}
main{min-width:0;max-width:1118px}
.side{position:sticky;top:calc(var(--bar) + 16px);max-height:calc(100vh - var(--bar) - 32px);
overflow:auto;padding-right:2px}
.side-card{background:var(--panel);border:1px solid var(--line);border-radius:11px;
padding:12px 13px 13px;margin-bottom:18px}
.side-card .sc{display:flex;align-items:baseline;justify-content:space-between;gap:7px;
padding-bottom:7px;margin-bottom:3px;border-bottom:1px solid var(--line);
font:600 14px/1.2 var(--mono)}
.side-card .sc .lb{font:600 12.4px/1 inherit;color:var(--dim);letter-spacing:.06em}
.side-row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
margin-top:8px;font-size:12.6px;color:var(--dim)}
.side-row b{font:600 13px/1.4 var(--mono);color:var(--ink-2);font-variant-numeric:tabular-nums}
.side-row b.up{color:var(--up)} .side-row b.down{color:var(--down)}
.toc{display:flex;flex-direction:column;gap:1px}
.toc a{position:relative;display:flex;align-items:center;gap:9px;padding:6px 10px;
border-radius:0 7px 7px 0;color:var(--dim);text-decoration:none;font-size:13.2px;
line-height:1.45;transition:background .14s,color .14s}
.toc a i{font:500 12.4px/1 var(--mono);font-style:normal;color:var(--dim);width:13px;
text-align:right;transition:color .14s}
.toc a:hover{background:var(--paper-2);color:var(--ink-2)}
.toc a.on{background:var(--card-2);color:var(--ink)}
.toc a.on i{color:var(--accent)}
.toc a.on::before{content:'';position:absolute;left:0;top:7px;bottom:7px;width:2px;
border-radius:2px;background:var(--accent)}

header.page{padding:0 0 16px;margin-bottom:8px;border-bottom:1px solid var(--line)}
h1{font-size:29px;line-height:1.32;margin:0 0 7px;letter-spacing:-.022em;font-weight:650}
h1 .dim{color:var(--dim);font-weight:500}
h2{font-size:17px;margin:40px 0 9px;display:flex;align-items:baseline;gap:9px;
letter-spacing:-.01em;scroll-margin-top:calc(var(--bar) + 18px)}
h2 .n{font:600 12.6px/1 var(--mono);color:var(--dim);width:14px}
h2 .meta{margin-left:auto;font:500 12.6px/1.4 var(--mono);color:var(--dim)}

.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;
margin:18px 0 6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card .k{color:var(--dim);font-size:12.6px;margin-bottom:7px}
.card .v{font:600 22px/1.2 var(--mono);letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.card .v.up{color:var(--up)} .card .v.down{color:var(--down)}
.card .x{color:var(--muted);font-size:12.4px;line-height:1.55;margin-top:6px;
font-family:var(--mono);display:flex;flex-direction:column;gap:1px}
.card .x>div{display:flex;justify-content:space-between;gap:10px}
.card .x b{color:var(--ink-2);font-weight:600}

.chart{background:var(--panel);border:1px solid var(--line);border-radius:11px;
padding:14px 12px 8px;margin:14px 0 6px;overflow:hidden}
.chart svg{width:100%;height:auto;display:block}
.chart svg text{pointer-events:none}

.tw{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;margin:14px 0}
.tw table{margin:0}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.4px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;
vertical-align:middle;font-variant-numeric:tabular-nums}
thead th{background:var(--card-2);color:var(--dim);font-size:12.4px;letter-spacing:.05em;
text-transform:uppercase;font-weight:600;white-space:nowrap}
tbody tr:hover{background:var(--paper-2)}
td.num{text-align:right;font-family:var(--mono)}
.tag{font:600 12px/1 var(--mono);padding:4px 7px;border-radius:4px;white-space:nowrap}

.note{color:var(--dim);font-size:12.8px;margin:9px 0 0;max-width:1000px}
.keyline{color:var(--dim);font-size:12.2px;margin:10px 0 0;line-height:1.6}
td.dim2{color:var(--muted)}
table.caliber td{font-size:13px;color:var(--ink-2);line-height:1.7;padding:9px 12px}
table.caliber td:first-child{width:22%;color:var(--muted);white-space:nowrap}
table.caliber code{font-family:var(--mono);font-size:12.2px;color:var(--brand);
background:var(--card-2);border:1px solid var(--line);border-radius:4px;padding:1px 5px}
#tip{position:fixed;left:0;top:0;z-index:99;pointer-events:none;opacity:0;
transition:opacity .1s;background:color-mix(in oklch, var(--card) 96%, transparent);border:1px solid var(--line-strong);border-radius:7px;
padding:6px 9px;color:var(--ink);font:12.6px/1.55 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
box-shadow:0 6px 14px color-mix(in oklch, var(--band) 55%, transparent);white-space:nowrap;max-width:340px}

footer{margin-top:52px;padding-top:16px;border-top:1px solid var(--line);
color:var(--dim);font-size:12.8px}
footer a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--line)}

@media (max-width:1349px){
.chart{overflow-x:auto;-webkit-overflow-scrolling:touch}
.chart svg{min-width:980px}
}
@media (max-width:900px){
.tw{
  background:
    linear-gradient(to right,var(--paper) 20%,transparent) left center,
    linear-gradient(to left,var(--paper) 20%,transparent) right center,
    radial-gradient(farthest-side at 0 50%,color-mix(in oklch, #000 40%, transparent),transparent) left center,
    radial-gradient(farthest-side at 100% 50%,color-mix(in oklch, #000 40%, transparent),transparent) right center;
  background-repeat:no-repeat;
  background-size:34px 100%,34px 100%,12px 100%,12px 100%;
  background-attachment:local,local,scroll,scroll;
}
.tw table{min-width:640px}
.tw table.caliber{min-width:0}
.tw table.caliber td:first-child{white-space:normal}
}
@media (max-width:1084px){
.shell{display:block;padding:18px 18px 80px}
main{max-width:none}
.side{position:sticky;top:var(--bar);z-index:55;max-height:none;overflow:visible;
margin:0 -18px 20px;padding:9px 18px;background:color-mix(in oklch, var(--paper) 95%, transparent);
backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.side-card{display:none}
.toc{flex-direction:row;overflow-x:auto;gap:6px;padding:1px 0 3px;scrollbar-width:none}
.toc::-webkit-scrollbar{display:none}
.toc a{padding:5px 11px;border:1px solid var(--line);border-radius:999px;
background:var(--card-2);font-size:12.6px;white-space:nowrap}
.toc a i{width:auto}
.toc a.on{border-color:var(--brand-f);background:var(--guide-bg);color:var(--brand)}
.toc a.on::before{display:none}
h2{scroll-margin-top:calc(var(--bar) + 66px)}
.bar-in{padding:0 16px}
}
@media (max-width:640px){
h1{font-size:23px}
.btn .lb{display:none}
.cards{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.card .v{font-size:20px}
}
@media print{
:root{--bg:var(--card);--panel:var(--card);--line:#d7dde5;--ink:#111827;--dim:#4b5563;
--up:#b91c1c;--down:#15803d;--accent:#1d4ed8}
.bar,.side,#tip,.keyline{display:none}
.shell{display:block;padding:0;max-width:none}
main{max-width:none}
body{background:var(--card);color:var(--ink);font-size:11pt}
h1{font-size:20pt;color:#111827}
h2{font-size:12.5pt;color:#111827;break-after:avoid}
.chart{break-inside:avoid;border-color:#d7dde5;background:var(--card)}
.card,.tw,table{background:var(--card)}
.card{border-color:#d7dde5}
.card .k,.card .x,td.dim2,thead th{color:#4b5563}
.card .x b,.lb,table.caliber td{color:#1f2937}
thead th{background:#f3f4f6}
td,th{border-color:#e5e7eb}
tr{break-inside:avoid}
footer{color:#4b5563;border-color:#e5e7eb}
footer a{color:#1d4ed8}
code,code.k,.caliber code{color:#1d4ed8;background:#f3f4f6;border-color:#e5e7eb}
}
"""


JS = r"""
<script>
// 侧栏目录：滚动高亮 + 顶部进度
(function(){
  var toc=document.getElementById('toc'); if(!toc) return;
  var links=[].slice.call(toc.querySelectorAll('a'));
  var secs=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});
  var bar=document.querySelector('.bar'), prog=document.getElementById('prog');
  var active=-1, raf=0;
  function offset(){return (bar?bar.offsetHeight:0)+(innerWidth<1085?70:30);}
  function update(){
    raf=0;
    var y=scrollY+offset(), idx=0;
    for(var i=0;i<secs.length;i++){
      if(secs[i] && secs[i].getBoundingClientRect().top+scrollY<=y) idx=i;
    }
    if(idx!==active){
      active=idx;
      links.forEach(function(a,i){a.classList.toggle('on',i===idx);});
      var cur=links[idx];
      if(cur && toc.scrollWidth>toc.clientWidth)
        toc.scrollLeft=cur.offsetLeft-Math.max(16,(toc.clientWidth-cur.offsetWidth)/2);
    }
    if(prog){
      var h=document.documentElement.scrollHeight-innerHeight;
      prog.style.transform='scaleX('+(h>0?Math.min(1,Math.max(0,scrollY/h)):0)+')';
    }
  }
  function onScroll(){if(!raf) raf=requestAnimationFrame(update);}
  addEventListener('scroll',onScroll,{passive:true});
  addEventListener('resize',onScroll);
  update();
})();
// 静态 data-tip（口径解释）——只处理不带 data-hv 的元素，图表悬停交给图自己
(function(){
  var tip=document.getElementById('tip');
  document.addEventListener('mousemove',function(e){
    var t=e.target.closest?e.target.closest('[data-tip]'):null;
    if(!t||t.getAttribute('data-hv')){ if(!document.querySelector('rect.hv:hover')) return; }
    if(!t) return;
    var txt=t.getAttribute('data-tip');
    if(tip.getAttribute('data-k')!==txt){tip.textContent=txt;tip.setAttribute('data-k',txt);}
    var w=tip.offsetWidth,h=tip.offsetHeight;
    var x=e.clientX+16,y=e.clientY+16;
    if(x+w>innerWidth-10) x=e.clientX-w-16;
    if(y+h>innerHeight-10) y=e.clientY-h-16;
    tip.style.left=x+'px';tip.style.top=y+'px';tip.style.opacity=1;
  },{passive:true});
})();
</script>
"""


def sec_head(i, name, sub="", sid=None):
    """章节头。i=None 时不带序号 —— 页面内部已经用 ①② 指两条价差，
    章节再编号会和它们撞车。"""
    num = f'<span class="n">{i:02d}</span>' if i is not None else ""
    anchor = f' id="{sid or ("t" + str(i))}"' if (sid or i is not None) else ""
    meta = f'<span class="meta">{esc(sub)}</span>' if sub else ""
    return f'<h2{anchor}>{num}{esc(name)}{meta}</h2>'



def cards_html(items):
    """items = [(标题, 主值, [('子项名', '子项值'), ...], 涨跌class)]"""
    out = ['<div class="cards">']
    for title, val, subs, k in items:
        x = "".join(f'<div><span>{esc(a)}</span><b>{esc(b)}</b></div>' for a, b in subs)
        out.append(f'<div class="card"><div class="k">{esc(title)}</div>'
                   f'<div class="v {k}">{val}</div><div class="x">{x}</div></div>')
    out.append("</div>")
    return "".join(out)


def fig_html(svg, n, note=""):
    nz = f'<p class="note">{note}</p>' if note else ""
    return f'<div class="chart">{svg}</div>{nz}'
