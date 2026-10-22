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
    document.getElementById('demo').scrollIntoView(); }
  if (h === '#gates') { showView('good');
    const d = document.getElementById('gates');
    if (d) { d.open = true; d.querySelectorAll('[data-fill]').forEach(fill);
             d.scrollIntoView({block: 'center'}); } }
}
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-eager][data-fill]').forEach(fill);
  const showView = wireScenarios();
  handleHash(showView);
  window.addEventListener('hashchange', () => handleHash(showView));
  document.querySelectorAll('details.acc').forEach(d =>
    d.addEventListener('toggle', () => {
      if (d.open) d.querySelectorAll('[data-fill]').forEach(fill);
    }));
});
