#!/usr/bin/env python3
"""Build the omegademo.com static site into dist/.

Reproducible deploy pipeline:
  1. runs the deterministic lab stages fresh (demo all / inject / verify) and
     stamps each capture with its provenance;
  2. copies the recorded evidence (recordings/, patches, issue, realworld);
  3. sanitizes machine paths, then FAILS the build if any sensitive pattern
     survives in the output tree;
  4. writes dist/ ready to push to the Pages repository.

Update the live site: `make site-deploy MSG="..."` (tools/deploy_site.py
publish — rebuilds, re-audits, then pushes; never sync dist/ by hand, that
bypasses the publish gates). Roll back: git revert in the Pages repo clone.
Nothing here contacts a model.
"""

import datetime
import json
import platform
import os
import re
import shutil
import subprocess
import sys

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(LAB, "dist")
EV = os.path.join(DIST, "evidence")
DOMAIN = "omegademo.com"


def sanitize(text):
    text = text.replace(LAB, "<LAB>")
    text = re.sub(r"/Users/[A-Za-z0-9_.-]+", "<HOME>", text)
    text = re.sub(r"/private/tmp/\S*", "<TMP>", text)
    text = re.sub(r"/tmp/omega-lab-cleantest\S*", "<LAB>", text)
    return text


def capture(stage):
    p = subprocess.run([sys.executable, os.path.join(LAB, "demo.py"), stage],
                       cwd=LAB, capture_output=True, encoding="utf-8",
                       timeout=900)
    if p.returncode != 0:
        sys.exit(f"build aborted: demo.py {stage} exited {p.returncode}")
    gover = subprocess.run(["go", "version"], capture_output=True,
                           encoding="utf-8").stdout.strip().split()
    gover = next((w.lstrip("go") for w in gover if w.startswith("go1")), "unknown")
    stamp = (f"# Deterministic execution of `python3 demo.py {stage}` captured "
             f"{datetime.date.today().isoformat()} on the maintainer's machine "
             f"({platform.system().lower()} {platform.machine()}, go {gover}, "
             f"python {platform.python_version()}).\n"
             f"# Reproduce locally: github.com/SillyZir/agent-omega-lab\n\n")
    return stamp + sanitize(p.stdout)


def main():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(EV)

    # 1 · fresh deterministic captures
    for stage in ("all", "inject", "verify"):
        name = "demo_all.txt" if stage == "all" else f"{stage}.txt"
        open(os.path.join(EV, name), "w").write(capture(stage))
        print(f"captured {name}")

    # 1b · curated proof slices (build fails loudly if markers move)
    def slice_between(text, start, end=None, what=""):
        i = text.find(start)
        if i < 0:
            sys.exit(f"build aborted: marker missing for {what}: {start!r}")
        if end is None:
            return text[i:]
        j = text.find(end, i)
        if j < 0:
            sys.exit(f"build aborted: end marker missing for {what}: {end!r}")
        return text[i:j]

    demo_all = open(os.path.join(EV, "demo_all.txt")).read()
    inject = open(os.path.join(EV, "inject.txt")).read()
    judges = json.load(open(os.path.join(LAB, "recordings",
                                         "judge_recorded.json")))
    judge_wrong = json.load(open(os.path.join(LAB, "recordings",
                                              "judge_wrong.json")))

    core = slice_between(demo_all, "━━━ regression-test differential",
                         what="core proof")
    proof_hdr = ("# Curated view of the run above: the differential, both judge\n"
                 "# verdicts, and the gate wall. Full unabridged log: the "
                 "'Full log' tab.\n\n")
    open(os.path.join(EV, "proof.txt"), "w").write(proof_hdr + core)

    captured = judges.get("captured", "unknown")
    good_hdr = (f"# The model's own fix (captured {captured}): differential, "
                "judges, gate wall.\n\n")
    open(os.path.join(EV, "proof_good.txt"), "w").write(good_hdr + core)

    bad = slice_between(inject, "━━━ 1) plausible-but-WRONG patch",
                        "━━━ 2)", what="wrong-patch scenario")
    bad += ("\nRecorded judge verdict on this patch:\n"
            f"  {judge_wrong['pass1']['verdict']} — "
            f"{judge_wrong['pass1']['reason']}\n")
    bad_hdr = ("# patches/wrong.diff — a plausible 'off-by-one fix' that never "
               "touches the root cause.\n\n")
    open(os.path.join(EV, "proof_bad.txt"), "w").write(bad_hdr + bad)

    gates = slice_between(core, "━━━ the ship-gate wall", what="gate wall")
    open(os.path.join(EV, "gates.txt"), "w").write(gates)

    # fail/pass panels for the demo card, from the recorded testgen differential
    tg = json.load(open(os.path.join(LAB, "recordings", "testgen_outcome.json")))
    # keep the two lines that carry the point; full output stays verbatim in
    # the unabridged pipeline log — truncation is marked, never silent
    fail_lines = [l for l in tg["base_output"].strip().splitlines()
                  if l.strip().startswith("--- FAIL") or "evict_lru_test" in l]
    open(os.path.join(EV, "panel_fail.txt"), "w").write(
        "$ go test ./...   # buggy tree + generated regression test\n\n"
        + "\n".join(fail_lines)
        + "\nFAIL\n[… full output in the unabridged pipeline log …]\n")
    open(os.path.join(EV, "panel_pass.txt"), "w").write(
        "$ go test ./...   # patched tree, same test\n\n"
        + tg["patched_output"].strip() + "\n")
    for f, marker in (("proof.txt", "SHIP PERMITTED"),
                      ("proof_good.txt", "SHIP PERMITTED"),
                      ("proof_bad.txt", "BLOCKED")):
        if marker not in open(os.path.join(EV, f)).read():
            sys.exit(f"build aborted: {f} lacks its outcome marker {marker!r}")

    # Card-facing presentation pass (documented, not silent): the demo card's
    # tabs show these four files next to a caption that already states the
    # provenance, so (a) drop the build-stamp comment lines from inject.txt
    # and (b) reword the lab banner tag "executing for real on this machine"
    # -> "executed on the maintainer's machine", which is the same claim
    # phrased for a reader who is NOT on that machine. The unabridged logs
    # (demo_all.txt, verify.txt, live_run.log) remain byte-verbatim.
    inj_p = os.path.join(EV, "inject.txt")
    lines = open(inj_p).read().splitlines(True)
    while lines and (lines[0].startswith("#") or lines[0].strip() == ""):
        lines.pop(0)
    open(inj_p, "w").write("".join(lines))
    for name in ("proof.txt", "proof_good.txt", "proof_bad.txt", "inject.txt"):
        p = os.path.join(EV, name)
        t = open(p).read().replace(
            "DETERMINISTIC — executing for real on this machine",
            "DETERMINISTIC — executed on the maintainer's machine")
        open(p, "w").write(t)
    print("card-facing presentation pass applied")

    print("curated proof slices written")

    # 2 · recorded + static evidence (verbatim copies)
    rec = os.path.join(LAB, "recordings")
    copies = {
        os.path.join(rec, "live_run.log"): "live_run.log",
        os.path.join(rec, "fix.diff"): "fix.diff",
        os.path.join(rec, "fix_declared.json"): "fix_declared.json",
        os.path.join(rec, "localize.json"): "localize.json",
        os.path.join(rec, "judge_recorded.json"): "judge_recorded.json",
        os.path.join(rec, "judge_wrong.json"): "judge_wrong.json",
        os.path.join(rec, "testgen_outcome.json"): "testgen_outcome.json",
        os.path.join(rec, "testgen", "evict_lru_test.go"): "evict_lru_test.go",
        os.path.join(LAB, "patches", "correct.diff"): "correct.diff",
        os.path.join(LAB, "patches", "wrong.diff"): "wrong.diff",
        os.path.join(LAB, "target", "ISSUE.md"): "ISSUE.md",
        os.path.join(LAB, "realworld", "issue.json"): "realworld_issue.json",
        os.path.join(LAB, "site", "realworld_run.txt"): "realworld_run.txt",
    }
    for src, dst in copies.items():
        shutil.copy(src, os.path.join(EV, dst))
    print(f"copied {len(copies)} evidence files")

    # 3 · pages + shared assets + Pages plumbing
    # consistency gate: the page's stated capture date must match the recordings
    idx_src = open(os.path.join(LAB, "site", "index.html")).read()
    if captured not in idx_src:
        sys.exit(f"build aborted: index.html does not mention the recording "
                 f"capture date {captured!r} — page claim has drifted")

    # trace gate: each hero-trace snippet claim must appear (case-insensitive)
    # both on the page and verbatim in the artifact it summarizes, so the
    # animation can never drift from the evidence
    trace_pins = {
        "0.87": "scout_row.txt",
        "repro evidence": "scout_row.txt",
        "internal/capability/catalog.go": "declared.txt",
        "suppressed the entire live": "judges.txt",
        "never the whole live directory": "fix.diff",
        "unpatched tree": "testgen.txt",
        "9707": "ship.txt",
        "merged by the maintainer": "merge.txt",
    }
    squash = lambda s: re.sub(r"\s+", " ", s.lower())
    # pins are checked against the trace element only — a pin surviving
    # elsewhere on the page (e.g. "9707" in the PR table) must not mask
    # drift in the trace itself
    t0 = idx_src.find('class="trace')
    t1 = idx_src.find("</ol>", t0)
    if t0 == -1 or t1 == -1:
        sys.exit("build aborted: hero trace element not found in index.html")
    trace_lc = squash(idx_src[t0:t1])
    for pin, art in trace_pins.items():
        try:
            artifact = squash(
                open(os.path.join(LAB, "site", "anatomy", art)).read())
        except OSError as e:
            sys.exit(f"build aborted: trace-pin artifact anatomy/{art} "
                     f"unreadable: {e}")
        if squash(pin) not in trace_lc:
            sys.exit(f"build aborted: trace pin {pin!r} missing from the "
                     f"hero trace in index.html")
        if squash(pin) not in artifact:
            sys.exit(f"build aborted: trace pin {pin!r} not found in "
                     f"anatomy/{art} — page claim has drifted from the artifact")

    # the open-PR snapshot is a dated static claim; nag (don't block) when old
    m = re.search(r"snapshot as of (\d{4}-\d{2}-\d{2})", idx_src)
    if m:
        age = (datetime.date.today()
               - datetime.date.fromisoformat(m.group(1))).days
        if age > 14:
            print(f"WARNING: open-PR snapshot is {age} days old — refresh it "
                  f"(tools/refresh_open_prs.py) before deploying")
    shutil.copytree(os.path.join(LAB, "site", "anatomy"),
                    os.path.join(EV, "anatomy"))
    for f in ("index.html", "details.html", "style.css", "app.js", "404.html",
              "anatomy.html"):
        shutil.copy(os.path.join(LAB, "site", f), os.path.join(DIST, f))
    shutil.copy(os.path.join(LAB, "site", "og.png"),
                os.path.join(DIST, "og.png"))
    shutil.copy(os.path.join(LAB, "tools", "site_audit.py"),
                os.path.join(DIST, "site_audit.py"))
    os.makedirs(os.path.join(DIST, ".github", "workflows"), exist_ok=True)
    shutil.copy(os.path.join(LAB, "site", "deploy.yml"),
                os.path.join(DIST, ".github", "workflows", "deploy.yml"))
    open(os.path.join(DIST, "CNAME"), "w").write(DOMAIN + "\n")
    open(os.path.join(DIST, ".nojekyll"), "w").write("")
    open(os.path.join(DIST, "robots.txt"), "w").write(
        "User-agent: *\nAllow: /\n")

    # 4 · disclosure gate — the build FAILS if anything sensitive survives
    bad = re.compile(
        r"/Users/[A-Za-z]|/Volumes/|Agent-Omega-ops|ghp_[A-Za-z0-9]{20}|"
        r"github_pat_|sk-ant-|AKIA[0-9A-Z]{16}|energyaisolution|steadytao")
    hits = []
    for root, _, files in os.walk(DIST):
        for f in files:
            p = os.path.join(root, f)
            m = bad.search(open(p, encoding="utf-8", errors="replace").read())
            if m:
                hits.append(f"{p}: {m.group(0)!r}")
    if hits:
        sys.exit("DISCLOSURE GATE FAILED:\n" + "\n".join(hits))
    n = sum(len(fs) for _, _, fs in os.walk(DIST))
    print(f"disclosure gate passed; dist/ ready ({n} files)")


if __name__ == "__main__":
    main()
