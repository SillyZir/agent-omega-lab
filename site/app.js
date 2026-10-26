/* Console renderer + accessible tabs + lazy accordion loading.
   Same-origin fetches only; no external requests. */
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function paint(text) {
  let h = esc(text);
  h = h.replace(/^━━━ (.*)\[(DETERMINISTIC|RECORDED|LIVE)([^\]]*)\]$/gm,
    (m, head, mode, rest) => {
      const cls = {DETERMINISTIC:'b-det', RECORDED:'b-rec', LIVE:'b-live'}[mode];
      return `<span class="banner ${cls}">━━━ ${head}[${mode}${rest}]</span>`; });
  h = h.replace(/^(  PASS .*)$/gm, '<span class="pass">$1</span>');
  h = h.replace(/^(  FAIL .*)$/gm, '<span class="fail">$1</span>');
  h = h.replace(/SHIP PERMITTED/g, '<span class="ship">SHIP PERMITTED</span>');
  h = h.replace(/NOT BLOCKED|BLOCKED/g, m => m === 'BLOCKED'
    ? '<span class="blocked">BLOCKED</span>'
    : '<span class="notblocked">NOT BLOCKED</span>');
  return h;
}
async function grab(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + ' -> ' + r.status);
  return r.text();
}
async function fill(el) {
  if (!el || el.dataset.loaded) return;
  el.dataset.loaded = '1';
  try { el.innerHTML = paint(await grab(el.dataset.fill)); }
  catch (e) { el.textContent = 'could not load ' + el.dataset.fill; }
}
function wireScenarios() {
  const tabs = [...document.querySelectorAll('#demo-tabs .tab')];
  const views = [...document.querySelectorAll('[data-view]')];
  function show(tab, focus) {
    tabs.forEach(t => {
      const on = t === tab;
      t.setAttribute('aria-selected', String(on));
      t.tabIndex = on ? 0 : -1;
    });
    views.forEach(v => {
      const on = v.dataset.view === tab.dataset.view;
      v.style.display = on ? '' : 'none';
      v.classList.toggle('showing', on);
      if (on) v.querySelectorAll('[data-fill]').forEach(fill);
    });
    if (focus) tab.focus();
  }
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => show(t));
    t.addEventListener('keydown', e => {
      const n = tabs.length;
      let j = null;
      if (e.key === 'ArrowRight') j = (i + 1) % n;
      else if (e.key === 'ArrowLeft') j = (i - 1 + n) % n;
      else if (e.key === 'Home') j = 0;
      else if (e.key === 'End') j = n - 1;
      if (j !== null) { e.preventDefault(); show(tabs[j], true); }
    });
  });
  if (tabs.length) show(tabs[0]);
  return name => { const t = tabs.find(x => x.dataset.view === name);
                   if (t) show(t); };
}
function handleHash(showView) {
  const h = location.hash;
  if (h === '#inject' || h === '#view-inject') { showView('inject');
    const demo = document.getElementById('demo');
    if (demo) demo.scrollIntoView(); }
  if (h === '#gates') { showView('good');
    const d = document.getElementById('gates');
    if (d) { d.open = true; d.querySelectorAll('[data-fill]').forEach(fill);
             d.scrollIntoView({block: 'center'}); } }
}
/* Hero trace sequencer. The markup's base state is the completed run (what
   no-JS and reduced-motion users see); this replays it: each stage goes
   pending -> active -> done, holds the finished trace, then loops. Paused
   when the tab is hidden or the trace is scrolled off-screen. */
function wireTrace() {
  const trace = document.querySelector('.trace');
  if (!trace || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const stages = [...trace.querySelectorAll('.tstage')];
  if (!stages.length) return;
  let timer = null, step = 0, onscreen = true;
  function render() {
    stages.forEach((s, i) => {
      s.classList.toggle('done', i < step);
      s.classList.toggle('active', i === step);
      s.classList.toggle('pending', i > step);
    });
  }
  function tick() {
    render();
    const hold = step === stages.length ? 3200 : 1000;
    step = (step + 1) % (stages.length + 1);
    timer = setTimeout(tick, hold);
  }
  function start() {
    if (timer !== null || document.hidden || !onscreen) return;
    trace.classList.add('anim');
    step = 0;
    timer = setTimeout(tick, 700);
  }
  function stop() { clearTimeout(timer); timer = null; }
  document.addEventListener('visibilitychange',
    () => document.hidden ? stop() : start());
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(es => {
      onscreen = es[es.length - 1].isIntersecting;
      onscreen ? start() : stop();
    }, {threshold: .25}).observe(trace);
  }
  start();
}
document.addEventListener('DOMContentLoaded', () => {
  const eager = [...document.querySelectorAll('[data-eager][data-fill]')];
  // eager consoles change height as they load, shifting a fragment target
  // the browser already scrolled to — re-anchor once they're all in
  Promise.all(eager.map(fill)).then(() => {
    const id = decodeURIComponent(location.hash.slice(1));
    if (!id || ['gates', 'inject', 'view-inject'].includes(id)) return;
    const el = document.getElementById(id);
    if (el && eager.length) el.scrollIntoView();
  });
  const showView = wireScenarios();
  handleHash(showView);
  window.addEventListener('hashchange', () => handleHash(showView));
  document.querySelectorAll('details.acc').forEach(d =>
    d.addEventListener('toggle', () => {
      if (d.open) d.querySelectorAll('[data-fill]').forEach(fill);
    }));
  wireTrace();
});
