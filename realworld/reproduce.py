#!/usr/bin/env python3
"""Reproduce ONE real data point of Omega's localization benchmark.

The seeded target in ../target is synthetic by design. This script runs the
same localization session against a REAL historical bug: go-ethereum issue
#34692, exactly as it sat in the tree before the maintainers' fix. Ground
truth is the merged human fix (commit d4027f3d), so you can verify the result
against GitHub yourself:

    https://github.com/ethereum/go-ethereum/issues/34692
    https://github.com/ethereum/go-ethereum/commit/d4027f3d4654

What it does: a blob-minimized fetch of the fix commit (~110 MB; a few minutes
on a fast connection), checkout of its PARENT (the pre-fix state), then a live
`claude -p` localization session (Read/Grep/Glob, no shell, issue text only —
agent/agentic_session.py), and a top-1/top-3 comparison against the files the
human fix actually touched.

Requires: git, network, `claude` CLI auth. Bills your account for one session.
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
sys.path.insert(0, LAB)

from agent import agentic_session as ag  # noqa: E402

ISSUE = json.load(open(os.path.join(HERE, "issue.json")))
CHECKOUT = os.path.join(LAB, ".work", "realworld",
                        ISSUE["repo"].replace("/", "__"))


def sh(args, cwd=None, check=True):
    p = subprocess.run(args, cwd=cwd, encoding="utf-8")
    if check and p.returncode != 0:
        sys.exit(f"command failed: {' '.join(args)}")


def main():
    import shutil
    if not shutil.which("claude"):
        sys.exit("this reproduction runs a live localization session and "
                 "needs the `claude` CLI on PATH (install Claude Code and "
                 "authenticate).")
    url = f"https://github.com/{ISSUE['repo']}.git"
    sha = ISSUE["fix_sha"]
    if not os.path.isdir(os.path.join(CHECKOUT, ".git")):
        print(f"fetching {ISSUE['repo']} at the fix commit (blob-minimized)…")
        os.makedirs(CHECKOUT, exist_ok=True)
        sh(["git", "init", "-q"], cwd=CHECKOUT)
        sh(["git", "remote", "add", "origin", url], cwd=CHECKOUT)
        sh(["git", "fetch", "--filter=blob:none", "--depth", "2",
            "origin", sha], cwd=CHECKOUT)
    print("checking out the PARENT of the human fix (the pre-fix tree)…")
    sh(["git", "checkout", "-q", f"{sha}^"], cwd=CHECKOUT)

    print(f"\nLIVE localization session on {ISSUE['issue_key']}: "
          f"{ISSUE['title']!r}")
    t0 = time.time()
    files, err = ag.agentic_localize(CHECKOUT, ISSUE["issue_key"],
                                     ISSUE["title"], ISSUE["body"])
    dur = round(time.time() - t0, 1)

    truth = ISSUE["fix_files"]
    primary = [f for f in truth if not f.endswith("_test.go")] or truth
    top1 = bool(files) and files[0] in truth
    top3 = any(f in truth for f in files)
    print(f"\npredicted ({dur}s): {files}   error: {err or '(none)'}")
    print(f"human fix touched:  {truth}")
    print(f"top-1 match: {top1}   top-3 match: {top3}   "
          f"(primary source file: {primary[0]})")
    print("\nverify the ground truth yourself: "
          f"https://github.com/{ISSUE['repo']}/commit/{sha}")
    sys.exit(0 if top3 else 1)


if __name__ == "__main__":
    main()
