#!/usr/bin/env python3
"""Browser console for the Agent Omega Demonstration Lab.

Zero dependencies (python stdlib only), binds 127.0.0.1 ONLY — nothing is
exposed off the machine. The server does not implement any pipeline logic:
every button spawns the same ``demo.py`` stages you can run in a terminal and
streams back their verbatim output, so what the browser shows IS the runner
output. Launch:

    make web            # then open http://127.0.0.1:8377
    python3 tools/web.py [--port 8377]

Stage whitelist only — the server never executes arbitrary input.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(LAB, "demo.py")

# stage -> (argv tail, allows --live, needs network note)
STAGES = {
    "setup":    (["setup"], False),
    "localize": (["localize"], True),
    "fix":      (["fix"], True),
    "validate": (["validate"], False),
    "judge":    (["judge"], True),
    "gates":    (["gates"], False),
    "inject":   (["inject"], False),
    "all":      (["all"], True),
    "verify":   (["verify"], False),
}
REALWORLD = os.path.join(LAB, "realworld", "reproduce.py")

_run_lock = threading.Lock()


def run_stage(stage, live):
    if stage == "realworld":
        argv = [sys.executable, REALWORLD]
    else:
        tail, allows_live = STAGES[stage]
        argv = [sys.executable, DEMO] + tail
        if live and allows_live:
            argv.append("--live")
    p = subprocess.run(argv, cwd=LAB, capture_output=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    return {"stage": stage, "live": bool(live), "exit": p.returncode,
            "output": (p.stdout or "") + (("\n[stderr]\n" + p.stderr)
                                          if p.stderr.strip() else "")}


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Agent Omega — Demonstration Lab</title>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --fg:#e6edf3;
          --dim:#8b949e; --det:#58a6ff; --rec:#d29922; --live:#f85149;
          --ok:#3fb950; --bad:#f85149; }
  * { box-sizing: border-box; }
  body { background:var(--bg); color:var(--fg); margin:0;
         font:14px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace; }
  header { padding:18px 24px 10px; border-bottom:1px solid var(--line); }
  h1 { margin:0 0 4px; font-size:18px; }
  .sub { color:var(--dim); font-size:12.5px; }
  .legend { display:flex; gap:14px; padding:10px 24px; font-size:12px;
            border-bottom:1px solid var(--line); flex-wrap:wrap; }
  .chip { padding:1px 8px; border-radius:10px; border:1px solid; }
  .chip.det  { color:var(--det);  border-color:var(--det); }
  .chip.rec  { color:var(--rec);  border-color:var(--rec); }
  .chip.live { color:var(--live); border-color:var(--live); }
  main { display:grid; grid-template-columns:270px 1fr; gap:0; }
  nav { padding:16px 18px; border-right:1px solid var(--line); }
  .grp { color:var(--dim); font-size:11px; text-transform:uppercase;
         letter-spacing:.08em; margin:14px 0 6px; }
  button { display:block; width:100%; text-align:left; margin:4px 0;
           background:var(--panel); color:var(--fg); cursor:pointer;
           border:1px solid var(--line); border-radius:6px; padding:8px 10px;
           font:inherit; }
  button:hover { border-color:var(--dim); }
  button:disabled { opacity:.45; cursor:wait; }
  button .m { float:right; font-size:11px; }
  .m.det{color:var(--det)} .m.rec{color:var(--rec)} .m.live{color:var(--live)}
  .toggle { margin-top:16px; padding:10px; border:1px dashed var(--live);
            border-radius:6px; font-size:12px; color:var(--dim); }
  .toggle input { accent-color:var(--live); }
  #status { padding:8px 18px; font-size:12.5px; color:var(--dim);
            border-bottom:1px solid var(--line); min-height:34px; }
  #status .ok  { color:var(--ok); }  #status .bad { color:var(--bad); }
  #out { padding:14px 18px 40px; white-space:pre-wrap; overflow-x:auto;
         min-height:60vh; }
  #out .banner { display:block; margin-top:10px; font-weight:700; }
  #out .b-det{color:var(--det)} #out .b-rec{color:var(--rec)}
  #out .b-live{color:var(--live)}
  #out .pass { color:var(--ok); }  #out .fail { color:var(--bad); }
  #out .ship { color:var(--ok); font-weight:700; }
  #out .blocked { color:var(--rec); font-weight:700; }
  #out .notblocked { color:var(--bad); font-weight:700;
                     background:#f8514922; }
  a { color:var(--det); }
</style></head><body>
<header>
  <h1>Agent Omega — Demonstration Lab</h1>
  <div class="sub">Every button runs the same <code>demo.py</code> stages as
  the CLI and shows their verbatim output. Server is bound to 127.0.0.1 —
  local only. <a href="https://github.com/SillyZir/Agent-Omega">System
  showcase &amp; merged-PR record</a></div>
</header>
<div class="legend">
  <span class="chip det">DETERMINISTIC — executes for real on this machine</span>
  <span class="chip rec">RECORDED — replays a real captured claude session</span>
  <span class="chip live">LIVE — real claude session, billed, nondeterministic</span>
</div>
<main>
<nav>
  <div class="grp">The demo</div>
  <button data-s="all">Full pipeline demo <span class="m rec">REC+DET</span></button>
  <button data-s="inject">Failure injection ×6 <span class="m det">DET</span></button>
  <button data-s="verify">Verify (assert everything) <span class="m det">DET</span></button>
  <div class="grp">Individual stages</div>
  <button data-s="localize">1 · Localize the bug <span class="m rec">REC</span></button>
  <button data-s="fix">2 · Generate the fix <span class="m rec">REC</span></button>
  <button data-s="validate">3 · Fail/pass differential <span class="m det">DET</span></button>
  <button data-s="judge">4 · Judge ×2 <span class="m rec">REC</span></button>
  <button data-s="gates">5 · 16-gate wall <span class="m det">DET</span></button>
  <div class="grp">Beyond the seeded target</div>
  <button data-s="realworld">Real go-ethereum bug #34692
    <span class="m live">LIVE+NET</span></button>
  <div class="toggle">
    <label><input type="checkbox" id="live"> LIVE mode for stages 1/2/4 and
    the full demo — runs real <code>claude -p</code> sessions on YOUR
    account (minutes, billed, output varies run to run)</label>
  </div>
</nav>
<section>
  <div id="status">idle — pick a stage. First run does a short go compile.</div>
  <div id="out">Welcome. Try <b>Full pipeline demo</b>, then
<b>Failure injection</b> — the six ways a bad ship gets blocked are the part
worth watching.

Launch note: recorded stages replay <i>recordings/</i> (a real captured run;
see recordings/live_run.log for the transcript and tools/record.py for how it
was made). Validation, the gate wall, and every injection execute live here.</div>
</section>
</main>
<script>
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
  // placeholder two-step instead of a lookbehind (older Safari throws on
  // those); the \u0000 delimiters cannot occur in demo output
  h = h.replace(/NOT BLOCKED/g, '\u0000NB\u0000');
  h = h.replace(/BLOCKED/g, '<span class="blocked">BLOCKED</span>');
  h = h.replace(/\u0000NB\u0000/g,
                '<span class="notblocked">NOT BLOCKED</span>');
  return h;
}
const out = document.getElementById('out'),
      status = document.getElementById('status'),
      buttons = [...document.querySelectorAll('button')];
async function run(stage) {
  const live = document.getElementById('live').checked;
  if (stage === 'realworld' &&
      !confirm('Real go-ethereum reproduction: ~110 MB fetch + one live ' +
               'claude session billed to your account. Continue?')) return;
  if (live && !confirm('LIVE mode runs real claude sessions billed to your ' +
                       'account and can take minutes. Continue?')) return;
  buttons.forEach(b => b.disabled = true);
  const t0 = Date.now();
  status.innerHTML = `running <b>${stage}</b>${live ? ' (LIVE)' : ''}…`;
  out.innerHTML = '';
  try {
    const r = await fetch('/run', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({stage, live})});
    const j = await r.json();
    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    status.innerHTML = r.status === 409 ? 'busy — another stage is running'
      : `<b>${stage}</b> finished in ${secs}s — exit ${j.exit} ` +
        (j.exit === 0 ? '<span class="ok">OK</span>'
                      : '<span class="bad">NONZERO</span>');
    out.innerHTML = paint(j.output || '(no output)');
  } catch (e) {
    status.innerHTML = `<span class="bad">request failed: ${esc(String(e))}</span>`;
  }
  buttons.forEach(b => b.disabled = false);
}
buttons.forEach(b => b.addEventListener('click', () => run(b.dataset.s)));
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/health":
            return self._send(200, json.dumps({"ok": True}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/run":
            return self._send(404, json.dumps({"error": "not found"}))
        # Require a JSON content type: a cross-origin fetch with this header
        # triggers a CORS preflight (which we never answer), and form/text
        # posts that skip preflight are rejected here — so a malicious web
        # page cannot drive this server from your browser.
        ctype = self.headers.get("Content-Type", "")
        if not ctype.startswith("application/json"):
            return self._send(400, json.dumps({"error": "json only"}))
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            stage = req.get("stage", "")
            live = bool(req.get("live"))
        except Exception:
            return self._send(400, json.dumps({"error": "bad request"}))
        if stage not in STAGES and stage != "realworld":
            return self._send(400, json.dumps({"error": "unknown stage"}))
        if not _run_lock.acquire(blocking=False):
            return self._send(409, json.dumps({"error": "busy"}))
        try:
            result = run_stage(stage, live)
        except Exception as e:
            result = {"stage": stage, "exit": -1, "output": f"server error: {e}"}
        finally:
            _run_lock.release()
        return self._send(200, json.dumps(result))

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass


def main():
    port = 8377
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        sys.exit(f"cannot bind 127.0.0.1:{port} ({e.strerror}) — is another "
                 f"console running? Try: python3 tools/web.py --port {port + 1}")
    print(f"Agent Omega Demonstration Lab console: http://127.0.0.1:{port}"
          f"  (local only; Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
