#!/usr/bin/env python3
"""Regenerate recordings/ by running the real model sessions once.

This is exactly how the shipped recordings were produced — run it yourself to
replace them with your own captured run (requires the `claude` CLI, `go`,
`gofmt`, `go vet`; bills the invoking account). Output is deliberately verbose;
redirect to recordings/live_run.log to refresh the shipped transcript.
"""

import json
import os
import shutil
import sys
import time

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LAB)

import demo  # noqa: E402  (reuses setup / issue_text / reset_tree / WORK)
from agent import agentic_session as ag          # noqa: E402
from agent import judge as judge_mod             # noqa: E402
from agent import autoship_gates as gates_mod    # noqa: E402
from agent import regression_harness as rh       # noqa: E402
from agent import test_generation as tg          # noqa: E402
from agent import test_exec as te                # noqa: E402

REC = os.path.join(LAB, "recordings")
WORK = demo.WORK


def say(msg):
    print(f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {msg}", flush=True)


def main():
    if not shutil.which("claude"):
        sys.exit("recording runs real model sessions and needs the `claude` "
                 "CLI on PATH.")
    os.makedirs(os.path.join(REC, "testgen"), exist_ok=True)
    captured = time.strftime("%Y-%m-%d")
    title, body = demo.issue_text()
    base_sha = demo.setup()

    say("STEP 1/4 — live localization session")
    t0 = time.time()
    files, err = ag.agentic_localize(WORK, demo.ISSUE_KEY, title, body)
    dur = round(time.time() - t0, 1)
    say(f"localized -> {files} (err={err!r}) in {dur}s")
    json.dump({"files": files, "error": err, "duration_s": dur,
               "captured": captured},
              open(os.path.join(REC, "localize.json"), "w"), indent=1)

    say("STEP 2/4 — live fix session (tree left patched)")
    t0 = time.time()
    fix_diff, declared, err = ag.agentic_fix(WORK, demo.ISSUE_KEY, title, body,
                                             reset=False)
    dur = round(time.time() - t0, 1)
    say(f"fix declared={declared} err={err!r} in {dur}s "
        f"({len(fix_diff)} byte diff)")
    if not fix_diff or not declared.get("done"):
        sys.exit("recording aborted: the live fix session did not produce a fix")
    open(os.path.join(REC, "fix.diff"), "w").write(fix_diff)
    json.dump({**declared, "duration_s": dur, "captured": captured},
              open(os.path.join(REC, "fix_declared.json"), "w"), indent=1)

    say("sanity: full test suite on the patched tree")
    passed, status, out = rh.run_package_tests(
        WORK, rh._changed_files(fix_diff), "go")
    say(f"tests on patched tree: passed={passed} status={status!r}")
    if passed is not True:
        sys.exit("recording aborted: live fix does not pass the package tests")

    say("STEP 3/4 — live regression-test generation (fix-blind differential)")
    issue = {"issue_key": demo.ISSUE_KEY, "repo": "agent-omega-lab/linkcache",
             "number": 1, "title": title, "body": body}
    t0 = time.time()
    outcome = tg.generate_regression_test(
        WORK, issue, base_sha, fix_diff, rh._changed_files(fix_diff), "go",
        te._BUILD_ENV)
    dur = round(time.time() - t0, 1)
    say(f"testgen outcome={outcome.get('outcome')!r} in {dur}s")
    if outcome.get("outcome") != "generated":
        sys.exit(f"recording aborted: testgen outcome {outcome.get('outcome')!r}")
    outcome["duration_s"] = dur
    outcome["captured"] = captured
    json.dump(outcome, open(os.path.join(REC, "testgen_outcome.json"), "w"),
              indent=1)
    test_rel = outcome["test_file"]
    shutil.copy(os.path.join(WORK, test_rel),
                os.path.join(REC, "testgen", os.path.basename(test_rel)))
    say(f"regression test saved: recordings/testgen/{os.path.basename(test_rel)}")

    say("STEP 4/4 — judge passes: recorded fix (x2) and wrong patch (x2)")
    neutral = gates_mod.neutralize_issue_text(body)
    v1 = judge_mod.review_patch(title, body, fix_diff,
                                "affected package tests pass")
    v2 = judge_mod.review_patch(title, neutral, fix_diff,
                                "affected package tests pass")
    say(f"fix: pass1={v1} pass2={v2}")
    json.dump({"pass1": v1, "pass2": v2, "captured": captured},
              open(os.path.join(REC, "judge_recorded.json"), "w"), indent=1)

    wrong = open(os.path.join(LAB, "patches", "wrong.diff")).read()
    w1 = judge_mod.review_patch(title, body, wrong,
                                "affected package tests FAIL (capacity bound)")
    w2 = judge_mod.review_patch(title, neutral, wrong,
                                "affected package tests FAIL (capacity bound)")
    say(f"wrong: pass1={w1} pass2={w2}")
    json.dump({"pass1": w1, "pass2": w2, "captured": captured},
              open(os.path.join(REC, "judge_wrong.json"), "w"), indent=1)

    demo.reset_tree()
    say("RECORDING COMPLETE — all artifacts written to recordings/")


if __name__ == "__main__":
    main()
