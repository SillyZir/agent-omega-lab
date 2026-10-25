# Agent Omega — Demonstration Lab

A runnable companion to the [Agent Omega showcase](https://github.com/SillyZir/Agent-Omega).
The showcase documents an autonomous AI repair system with
[11 merged upstream pull requests](https://github.com/SillyZir/Agent-Omega#proven-outcomes--merged-upstream-contributions);
this lab lets you **execute its core engineering claims on your own machine**:

1. Bug localization and patch generation on a Go codebase.
2. A regression test that **fails on the buggy code and passes on the fix**.
3. Two independent patch reviews and the 16-gate release wall.
4. Failure injection — six ways a bad ship gets **blocked**.
5. A reproducible evaluation path against a **real historical go-ethereum bug**.

The modules doing the work are the production code: everything in `agent/` and
`cloud/` is **byte-identical** to the showcase repo — verify with
[`MANIFEST.json`](MANIFEST.json) (`shasum -a 256 <file>`). The one deliberate
substitution is [`runner/env_guard.py`](runner/env_guard.py), a clearly-labeled
shim replacing the production SSD storage guard.

## The five-minute interview demo

Prerequisites: `python3` (3.10+), `go` (1.21+), `git`. No API access needed —
the model stages replay a real captured run (clearly bannered RECORDED);
everything else executes live on your machine. The commands themselves finish
in well under a minute (first run pays a short `go` compile); five minutes
comfortably covers running all three and talking through the output.

```sh
make demo      # localize -> fix -> fail/pass differential -> judge x2 -> 16 gates
make inject    # six blocked-failure scenarios (the part worth watching)
make verify    # machine-checkable: asserts every deterministic outcome
```

Prefer a browser? `make web` serves a local console at **http://127.0.0.1:8377**
(stdlib only, bound to localhost): one button per stage, the verbatim runner
output color-coded — gate PASS/FAIL rows, SHIP PERMITTED/BLOCKED verdicts —
and every stage badged DETERMINISTIC / RECORDED / LIVE. The server executes
only the whitelisted `demo.py` stages; LIVE mode and the real-world run sit
behind an explicit confirmation because they bill the operator's account.

What `make demo` shows, in order:

| Stage | What runs | Mode |
|---|---|---|
| localize | `agent/agentic_session.py` session names the buggy file from the issue text alone | RECORDED (live: `--live`) |
| fix | the same constrained session's patch, applied to a fresh checkout | RECORDED (live: `--live`) |
| validate | the model-generated regression test runs on base (**must FAIL**) and on the patched tree (**must PASS**) via `agent/regression_harness.py` | **executes live** |
| judge ×2 | `agent/judge.py` verdicts; pass 2 reads *neutralized* issue text | RECORDED (live: `--live`) |
| gates | the real `agent/autoship_gates.evaluate()` — all 16 gates with reasons | **executes live** |

Expected tail of a successful `make demo`:

```
  PASS  breaker_armed            armed
  PASS  daily_cap                0/2 used (own in-flight intent excluded)
  ...
gate wall verdict: SHIP PERMITTED
demo complete: localized -> fixed -> differentially tested -> judged twice -> 16 gates -> ship permitted.
```

## Failure injection (`make inject`)

Six scenarios, each of which must end **BLOCKED** (the exit code asserts it):

1. A plausible-but-wrong patch (`patches/wrong.diff`) — the test suite catches
   it and the `tests_pass` gate refuses.
2. Prompt-injection planted in the issue text — `injection_lint` refuses.
3. A diff touching CI workflow config — `content_lint` refuses.
4. An oversized 40-file diff — `size_caps` refuses.
5. A tripped circuit breaker (`fixtures/state_tripped/`) — `breaker_armed` refuses.
6. A missing state file — the gate **errors and fails closed**: in this system,
   UNKNOWN is never PASS.

## The real-world data point (`make realworld`)

The demo target is a small seeded Go module (`target/`, bug documented in
[`target/ISSUE.md`](target/ISSUE.md)) — synthetic by design so the demo is
fast and deterministic. To see the same localization session against a **real
historical bug**, run:

```sh
make realworld   # network (~110 MB fetch) + `claude` CLI auth; one billed session
```

It fetches go-ethereum at the commit that fixed issue #34692, checks out the
pre-fix parent, runs a live localization session, and scores the prediction
against the files the maintainers' merged fix actually touched — ground truth
you can [verify on GitHub](https://github.com/ethereum/go-ethereum/commit/d4027f3d4654).

## What is live, what is recorded, what this lab is not

- **Always live on your machine:** patch application, every `go test` run, the
  fail-on-base/pass-on-patch differential, all 16 gates, all six injections.
- **Recorded by default:** the four model stages (localization, fix, judges,
  regression-test *generation*). `recordings/` holds the real captured
  sessions including the full transcript (`recordings/live_run.log`), and
  [`tools/record.py`](tools/record.py) is exactly how they were produced —
  run it to replace them with your own capture.
- **Live opt-in:** `make demo-live` (or any `demo.py` stage with `--live`)
  runs real `claude -p` sessions. Model output varies between runs; that
  nondeterminism is intrinsic and is why the gate wall exists.

**Known limitations, stated plainly:**

- The seeded bug is synthetic and easier than production work. The evidence
  that the same architecture handles real codebases is the showcase's
  [10 merged PRs](https://github.com/SillyZir/Agent-Omega#proven-outcomes--merged-upstream-contributions)
  in Caddy, rclone, go-ethereum, and k3s — and `make realworld` here.
- Six of the 16 gates read operational state (breaker, budgets, capacity,
  per-repo policy); in this lab they read `fixtures/` instead of the live
  production ledgers. The gate *code* is unmodified.
- The production system around these modules — scout, executor, write-ahead
  intents, crash reconciliation, daily monitoring — is documented in the
  showcase, not demonstrated here.
- Tested on macOS (arm64) with go 1.25 and python 3.14. The stated minimums
  (go 1.21, python 3.10) and Linux are expected to work but have not been
  verified.

## Layout

This lab is also the source of the public demonstration site at
[omegademo.com](https://omegademo.com): `tools/build_site.py` captures fresh
deterministic runs, bundles the recorded evidence with provenance stamps, runs
a disclosure gate, and emits `dist/` for the Pages repo — update by re-running
it and pushing, roll back with `git revert` there.

```
demo.py            every stage, one CLI        tools/record.py   how recordings were made
tools/web.py       local browser console       MANIFEST.json     byte-identity proof
site/ + tools/build_site.py  omegademo.com source + builder
agent/, cloud/     REAL production modules     fixtures/         gate state fixtures
runner/env_guard.py  the one labeled shim      patches/          correct.diff / wrong.diff
target/            seeded Go module + ISSUE.md realworld/        the go-ethereum reproduction
recordings/        captured live run + log
```
