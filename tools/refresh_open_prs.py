#!/usr/bin/env python3
"""Verify and restamp the open-PR snapshot in site/index.html.

The snapshot between the `open-prs:start` / `open-prs:end` markers is a dated
static claim. This tool re-checks every PR listed there against GitHub (via
the `gh` CLI) and:

  - if every PR is still open: rewrites the as-of date to today (marker
    comment and heading) and reports success;
  - if any PR changed state (merged/closed): exits nonzero and lists the rows
    that must be edited by hand — merged rows belong in the merged table, not
    silently dropped.

Descriptions stay hand-curated; this tool never generates HTML rows.
"""

import datetime
import json
import os
import re
import subprocess
import sys

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(LAB, "site", "index.html")


def main():
    src = open(IDX).read()
    m = re.search(r"<!-- open-prs:start.*?<!-- open-prs:end -->", src, re.S)
    if not m:
        sys.exit("no open-prs block found in site/index.html")
    block = m.group(0)

    prs = list(dict.fromkeys(
        re.findall(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)", block)))
    if not prs:
        sys.exit("open-prs block contains no PR links")

    stale = []
    for repo, num in prs:
        try:
            out = subprocess.run(
                ["gh", "api", f"repos/{repo}/pulls/{num}"],
                capture_output=True, text=True)
        except FileNotFoundError:
            sys.exit("gh CLI not found on PATH")
        if out.returncode != 0:
            sys.exit(f"gh api failed for {repo}#{num}: {out.stderr.strip()}")
        try:
            pr = json.loads(out.stdout)
        except ValueError:
            sys.exit(f"gh api returned non-JSON for {repo}#{num}")
        state = "merged" if pr.get("merged_at") else pr["state"]
        print(f"{repo}#{num}: {state}")
        if state != "open":
            stale.append(f"{repo}#{num} is now {state}")

    if stale:
        print("\nSNAPSHOT STALE — edit site/index.html by hand:")
        for s in stale:
            print("  -", s)
        print("(a merged row moves to the merged table; a closed row is "
              "removed; then re-run this tool)")
        return 1

    today = datetime.date.today().isoformat()
    new, n_head = re.subn(r"(snapshot as of )\d{4}-\d{2}-\d{2}",
                          r"\g<1>" + today, src)
    new, n_mark = re.subn(r"(open-prs:start · snapshot )\d{4}-\d{2}-\d{2}",
                          r"\g<1>" + today, new)
    if n_head != 1 or n_mark != 1:
        sys.exit(f"restamp anchors drifted (heading matches={n_head}, "
                 f"marker matches={n_mark}; each must be exactly 1) — "
                 f"fix site/index.html by hand")
    n = len(prs)
    words = {9: "Nine", 8: "Eight", 7: "Seven", 6: "Six", 5: "Five",
             4: "Four", 3: "Three", 2: "Two", 1: "One"}
    if n not in words:
        sys.exit(f"{n} open PRs exceeds the count-word table — "
                 f"edit the heading by hand")
    phrase = words[n] + " open pull request" + ("s" if n > 1 else "")
    new, n_cnt = re.subn(r"(?:Nine|Eight|Seven|Six|Five|Four|Three|Two|One)"
                         r" open pull requests?", phrase, new)
    if n_cnt != 1:
        sys.exit(f"count-word anchor drifted ({n_cnt} matches; must be "
                 f"exactly 1) — fix site/index.html by hand")
    if new != src:
        open(IDX, "w").write(new)
        print(f"restamped snapshot to {today} ({n} PRs, all open)")
    else:
        print(f"snapshot already current ({today}, {n} PRs, all open)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
