#!/usr/bin/env python3
"""Build and audit the site locally. Publishing requires an explicit subcommand.

    deploy_site.py build                 # build + audit into dist/. Never publishes.
    deploy_site.py publish -m "message"  # build + audit + commit + PUSH, public
    deploy_site.py publish --dry-run -m . # everything up to the commit, then stop
    deploy_site.py --self-test           # the regression suite. Publishes nothing.

Actions re-audits and deploys to Pages; a failing CI audit blocks the release, and
every deploy is a plain commit — rollback is `git revert` in the site repo.

Credentials: none in source — push uses the local git/osxkeychain auth.

THE 2026-10-25 INCIDENT, because this file is the only place it can't be forgotten.
`deploy_site.py --help` was run expecting usage text. There was no argument parsing:
`sys.argv[1]` became the commit message, the pipeline ran to completion, and a commit
whose message is literally `--help` was pushed to a public repository and redeployed a
live public site. Nothing was wrong with the *content* — that was luck, not design.

The old docstring called this script "fail-closed", and it was, about content: a failing
audit aborts the release. The incident was not a content failure. It was an *intent*
failure, and the CLI boundary had no coverage for intent at all. The gates below are that
coverage. Do not add a second way to reach `_publish`.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

# A single env var supplies the whole test sandbox, and when it is set REMOTE is *forced*
# to a path inside that sandbox. Two separate overrides (root and remote) would admit the
# combination where the source is a scratch tree and the destination is still the real
# public site -- a new footgun installed by the fix for the old one. With one variable
# that combination cannot be expressed.
TEST_ROOT = os.environ.get("OMEGA_DEPLOY_TEST_ROOT")
if TEST_ROOT:
    LAB = os.path.abspath(TEST_ROOT)
    REMOTE = os.path.join(LAB, "remote.git")
else:
    LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    REMOTE = "https://github.com/SillyZir/omegademo"
DIST = os.path.join(LAB, "dist")
DEPLOY = os.path.join(LAB, ".deploy", "omegademo")


def run(argv, cwd=None):
    print("$", " ".join(argv))
    p = subprocess.run(argv, cwd=cwd)
    if p.returncode != 0:
        sys.exit(f"deploy aborted: {' '.join(argv)} exited {p.returncode}")


def check_message(msg):
    """Reject the shapes an argv accident produces, rather than a sentence.

    argparse already refuses `-m --help` on its own (exit 2, "expected one argument"),
    because it reads a leading-dash token as an option and not as -m's value. But
    `-m=--help` and `-m " --help"` arrive here as ordinary string values, so the
    leading-dash rule is restated here rather than assumed from argparse.

    Deliberately not checked: a minimum length. It would catch `-m x`, but no length is
    the right one and a rule nobody can derive is a rule someone will delete. Empty and
    leading-dash are the two shapes that actually produced the incident.
    """
    m = msg.strip()
    if not m:
        sys.exit("deploy aborted: commit message is empty "
                 "(`make site-deploy` with MSG unset used to land here)")
    if m.startswith("-"):
        sys.exit(f"deploy aborted: commit message may not begin with '-': {msg!r} "
                 "-- this is the 2026-10-25 '--help' incident")
    return m


def build_and_audit():
    """Local only. No git, no network, no credentials. Shared by both subcommands."""
    run([sys.executable, os.path.join(LAB, "tools", "build_site.py")])
    run([sys.executable, os.path.join(LAB, "tools", "site_audit.py"), DIST])


def stage_deploy_tree():
    """Clone/pull/rsync/add. Reads the network; CANNOT publish.

    Returns True when the index holds changes worth committing. `git pull --rebase` stays
    on this side of the choke point on purpose: a dry run that skipped the pull and the
    rsync would not be exercising the steps that actually fail.
    """
    if not os.path.isdir(os.path.join(DEPLOY, ".git")):
        os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
        run(["git", "clone", "-q", REMOTE, DEPLOY])
    run(["git", "pull", "-q", "--rebase", "origin", "main"], cwd=DEPLOY)
    run(["rsync", "-a", "--delete", "--exclude", ".git", DIST + "/", DEPLOY])
    run(["git", "add", "-A"], cwd=DEPLOY)
    return subprocess.run(["git", "diff", "--cached", "--quiet"],
                          cwd=DEPLOY).returncode != 0


def _publish(msg):
    """THE ONLY FUNCTION IN THIS FILE THAT COMMITS OR PUSHES.

    Reached from exactly one call site, in cmd_publish, after check_message and after the
    --dry-run check. Do not add a second call site and do not move either verb out of
    here. A guard is a predicate that sits *next to* a dangerous call and drifts away from
    it on the next edit; a choke point makes "can anything else reach the push?" a
    question `grep` answers. --self-test asserts both of those properties mechanically.

    `git commit` lives in here with the push, not outside it, because a committed .deploy
    tree is one command from public and is the artifact that put `--help` in public
    history. The dry-run boundary and the nothing-irreversible-yet boundary are the same
    line, which is the only way a reader can keep them straight.
    """
    run(["git", "commit", "-q", "-m", msg], cwd=DEPLOY)
    run(["git", "push", "-q", "origin", "main"], cwd=DEPLOY)


def cmd_build(a):
    build_and_audit()
    print(f"built and audited: {DIST}\nnothing published -- "
          "`deploy_site.py publish -m \"message\"` publishes")
    return 0


def cmd_publish(a):
    msg = check_message(a.message)   # before any work: a bad message should cost nothing
    build_and_audit()
    if not stage_deploy_tree():
        print("nothing changed; no deploy needed")
        return 0
    if a.dry_run:
        print(f"$ git commit -q -m {msg!r}\n$ git push -q origin main\n"
              "DRY RUN -- not published.")
        return 0
    _publish(msg)
    print("pushed — CI re-audits and deploys: "
          f"{REMOTE}/actions (rollback: git revert in {DEPLOY})")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(
        prog="deploy_site.py",
        description="Build and audit the site. Publishing is never the default -- "
                    "it requires the `publish` subcommand and an explicit -m message.")
    ap.add_argument("--self-test", action="store_true",
                    help="run the publication-gating regression suite; publishes nothing")
    sub = ap.add_subparsers(dest="cmd", metavar="{build,publish}")

    b = sub.add_parser("build", help="build + audit into dist/. Local only, never publishes.")
    b.set_defaults(fn=cmd_build)

    p = sub.add_parser("publish", help="build + audit + commit + PUSH to the public site repo.")
    p.add_argument("-m", "--message", required=True, metavar="MSG",
                   help="commit message; required, and may not be empty or begin with '-'")
    p.add_argument("--dry-run", action="store_true",
                   help="run every step up to the commit, print what WOULD be published, "
                        "and exit 0 without publishing")
    p.set_defaults(fn=cmd_publish)
    return ap


def main():
    ap = build_parser()
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    # add_subparsers is optional by default, so a bare invocation parses cleanly with
    # cmd=None. Exit 2 rather than quietly doing a build: "run it with nothing and
    # something happens" is the exact shape of the incident, and a bare invocation
    # should teach the CLI rather than act on a guess about what was meant.
    if a.cmd is None:
        # ap.error, not sys.exit: it prints usage and exits **2**, the same code argparse
        # uses for every other misuse. sys.exit(str) exits 1, which would make "I was
        # invoked wrongly" indistinguishable from "a build step failed" to any caller
        # reading the code. The suite caught exactly that.
        ap.error("a subcommand is required ({build,publish}); "
                 "publishing is never the default")
    if TEST_ROOT:
        print(f"!! OMEGA_DEPLOY_TEST_ROOT is set: LAB={LAB}\n"
              f"!! remote is forced local: {REMOTE}", file=sys.stderr)
    return a.fn(a)


# ---------------------------------------------------------------------------
# Regression suite for the 2026-10-25 incident.
#
# House style is the sibling repo's: labelled lines, one per case, exit 0 or 1. No pytest
# -- a framework for a 60-line tool is the tooling expansion this project was told to
# stop, and a suite that needs an install is a suite that stops being run.
#
# Mechanism: a stub `git` placed first on PATH that logs its argv and exits 0, so the
# question "did this invocation reach a commit or a push?" is answered by reading a file
# rather than by trusting a mock of the very seam under test. The script is driven as a
# real subprocess, through real argparse, so the suite still catches a future edit that
# bypasses run() with a bare subprocess call.
#
# Nothing here can publish, by three independent mechanisms: OMEGA_DEPLOY_TEST_ROOT forces
# the remote to a local path, every git invocation is a stub, and the sandbox lives under
# /tmp. Any one of the three alone would be sufficient.
# ---------------------------------------------------------------------------

STUB_GIT = """#!/bin/sh
echo "$@" >> "$DEPLOY_TEST_LOG"
# `git diff --cached --quiet` exits 1 when the index holds changes. Returning 1 is what
# drives the script to the point an UNHARDENED copy would commit; a stub that reported
# "no changes" would make every case pass vacuously, including the broken one.
[ "$1" = "diff" ] && exit 1
exit 0
"""

STUB_BUILD = """#!/usr/bin/env python3
import os, sys
d = os.path.join(os.environ["OMEGA_DEPLOY_TEST_ROOT"], "dist")
os.makedirs(d, exist_ok=True)
open(os.path.join(d, "index.html"), "w").write("<html>fixture</html>")
"""

STUB_AUDIT = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"


def _sandbox(root):
    """Build the fixture tree. Returns the env for driving the script under test."""
    shutil.rmtree(root, ignore_errors=True)
    tools, deploy, bin_ = (os.path.join(root, "tools"),
                           os.path.join(root, ".deploy", "omegademo", ".git"),
                           os.path.join(root, "bin"))
    for d in (tools, deploy, bin_):
        os.makedirs(d, exist_ok=True)
    for name, body in (("build_site.py", STUB_BUILD), ("site_audit.py", STUB_AUDIT)):
        path = os.path.join(tools, name)
        with open(path, "w") as fh:
            fh.write(body)
        os.chmod(path, 0o755)
    git = os.path.join(bin_, "git")
    with open(git, "w") as fh:
        fh.write(STUB_GIT)
    os.chmod(git, 0o755)
    env = dict(os.environ)
    env["OMEGA_DEPLOY_TEST_ROOT"] = root
    env["DEPLOY_TEST_LOG"] = os.path.join(root, "git.log")
    env["PATH"] = bin_ + os.pathsep + env["PATH"]
    return env


def _drive(script, argv, env):
    """Run the script under test. Returns (returncode, git-verbs-it-reached)."""
    log = env["DEPLOY_TEST_LOG"]
    if os.path.exists(log):
        os.remove(log)
    p = subprocess.run([sys.executable, script] + argv, env=env,
                       capture_output=True, text=True)
    verbs = []
    if os.path.exists(log):
        with open(log) as fh:
            verbs = [ln.split()[0] for ln in fh.read().splitlines() if ln.split()]
    return p.returncode, verbs


# (label, argv, expected returncode or None for "nonzero", must-reach-publication)
CASES = [
    ("--help prints usage and runs nothing",      ["--help"],                    0, False),
    ("no arguments at all",                       [],                            2, False),
    ("an unrecognised flag",                      ["--bogus"],                   2, False),
    ("an unrecognised subcommand",                ["bogus"],                     2, False),
    ("publish with no message",                   ["publish"],                   2, False),
    ("publish -m --help, the incident string",    ["publish", "-m", "--help"],   2, False),
    ("publish -m=--help, argparse lets it past",  ["publish", "-m=--help"],   None, False),
    ("publish with an empty message",             ["publish", "-m", ""],      None, False),
    ("publish with a whitespace-only message",    ["publish", "-m", "   "],   None, False),
    ("build, the local default action",           ["build"],                     0, False),
    ("publish --dry-run with a real message",     ["publish", "--dry-run",
                                                   "-m", "Ship the nav fix"],    0, False),
    # The positive control. Without it, deleting the push outright turns every line above
    # green -- the suite would be measuring the absence of a capability it never confirmed
    # was present. This is the one case that must reach both verbs.
    ("publish with a real message REACHES both",  ["publish",
                                                   "-m", "Ship the nav fix"],    0, True),
]


def _structural_check(path):
    """Assert the choke point is still a choke point.

    The literals are assembled from fragments rather than written out, because a checker
    that spells the thing it counts is a checker that counts itself.
    """
    with open(path) as fh:
        lines = fh.read().splitlines()
    name = "_pub" + "lish"
    starts = [i for i, ln in enumerate(lines) if ln.startswith(f"def {name}(")]
    if len(starts) != 1:
        return [f"expected exactly one definition of {name}, found {len(starts)}"]
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines))
                if lines[i] and not lines[i][0].isspace()), len(lines))
    body, whole = lines[start:end], lines
    bad = []
    for verb in ("commit", "push"):
        lit = '"git", "' + verb + '"'
        everywhere = [i for i, ln in enumerate(whole) if lit in ln]
        inside = [i for i in everywhere if start <= i < end]
        if len(everywhere) != 1 or len(inside) != 1:
            bad.append(f"git {verb} appears on lines {[i + 1 for i in everywhere]}; "
                       f"expected exactly one, inside {name} "
                       f"(lines {start + 1}-{end})")
    # The lookbehind is load-bearing: cmd_publish's own def line ends in the choke point's
    # name followed by a paren, so a plain substring search reports the wrapper as a second
    # call site. The suite found that on its first run.
    #
    # And then it found this comment, which in an earlier draft quoted the pattern as a
    # string and so counted itself -- two lines below the sentence warning against exactly
    # that. It is described in prose here for the same reason the claim gate distinguishes
    # mention from use: a file has to be able to explain its own checks without tripping
    # them. Do not reintroduce the literal.
    call = re.compile(r"(?<![A-Za-z0-9_])" + name + r"\(")
    calls = [i for i, ln in enumerate(whole)
             if call.search(ln) and not ln.startswith(f"def {name}(")]
    if len(calls) != 1:
        bad.append(f"expected exactly one call site for {name}, "
                   f"found {len(calls)} on lines {[i + 1 for i in calls]}")
    del body
    return bad


def self_test(script=None, root="/tmp/deploy_regress/sandbox"):
    """Returns 0 if every gate holds. Publishes nothing, by three mechanisms."""
    script = script or os.path.abspath(__file__)
    print(f"deploy_site.py publication gating -- {script}")
    env = _sandbox(root)
    ok = True

    for label, argv, want_rc, want_publish in CASES:
        rc, verbs = _drive(script, argv, env)
        reached = [v for v in verbs if v in ("commit", "push")]
        rc_ok = (rc != 0) if want_rc is None else (rc == want_rc)
        if want_publish:
            if reached == ["commit", "push"] and rc_ok:
                print(f"  QUIET    {label}")
            else:
                print(f"  BROKEN   {label}  <-- rc={rc}, reached {reached or 'nothing'}; "
                      "the one legitimate path must still publish")
                ok = False
        elif reached:
            print(f"  ESCAPED  {label}  <-- rc={rc}, REACHED {reached}")
            ok = False
        elif not rc_ok:
            # It published nothing, which is the safety property, but it did so by the
            # wrong route. Reported rather than tolerated: an exit code is the only thing
            # a Makefile or a CI step can read.
            print(f"  RC       {label}  <-- published nothing, but rc={rc}, wanted "
                  f"{'nonzero' if want_rc is None else want_rc}")
            ok = False
        else:
            print(f"  CAUGHT   {label}")

    for problem in _structural_check(script):
        print(f"  DRIFTED  {problem}")
        ok = False
    if ok:
        print(f"  OK       choke point intact: both verbs inside _pub{'lish'} alone")

    print("GATING INTACT" if ok else "GATING FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
