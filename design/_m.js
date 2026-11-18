
(() => {
  const out = [];
  document.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.right > window.innerWidth + 1) {
      out.push([el.tagName + '.' + (el.className||'').toString().slice(0,40), Math.round(r.width), Math.round(r.right)]);
    }
  });
  return JSON.stringify({vw: window.innerWidth, doc: document.documentElement.scrollWidth, bad: out.slice(0,15)});
})()
