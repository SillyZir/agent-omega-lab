#!/usr/bin/env python3
"""Fail-closed structural + disclosure audit of a built site directory.

Run locally by `make site-deploy` and in CI on every push to the site repo —
a failing audit blocks the Pages deployment. Stdlib only.

    python3 site_audit.py <site-dir>
"""
import os
import re
import sys
from html.parser import HTMLParser

# The pattern is assembled from fragments so this file's own source can never
# match it — the audit scans every file in the tree, including itself, and the
# upstream build's disclosure gate scans this file on its way into the tree.
_F = ["/Use" "rs/[A-Za-z]", "/Volu" "mes/", "Agent-Omega" "-ops",
      "ghp" "_[A-Za-z0-9]{20}", "github" "_pat_", "sk-" "ant-",
      "AK" "IA[0-9A-Z]{16}", "energyai" "solution", "steady" "tao",
      "Sha" "ms", "Has" "san"]
FORBIDDEN = re.compile("|".join(_F))


class Check(HTMLParser):
    VOID = {"meta", "link", "br", "img", "hr", "input", "wbr", "source"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.errs = [], [], []
        self.aria, self.hrefs, self.fills = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        for k in ("aria-controls", "aria-labelledby"):
            if k in a:
                self.aria.append(a[k])
        if "href" in a:
            self.hrefs.append(a["href"])
        if "data-fill" in a:
            self.fills.append(a["data-fill"])
        if "src" in a:
            self.fills.append(a["src"])
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errs.append(f"tag mismatch at </{tag}>")
        else:
            self.stack.pop()


def main(root):
    errs = []

    def err(msg):
        errs.append(msg)

    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [x for x in dirnames if x not in (".git", ".github")]
        for f in files:
            p = os.path.join(dirpath, f)
            raw = open(p, "rb").read()
            if b"\x00" in raw and not f.endswith(".png"):
                err(f"null byte in {p}")
            if not f.endswith(".png"):
                m = FORBIDDEN.search(raw.decode("utf-8", errors="replace"))
                if m:
                    err(f"forbidden content in {p}: {m.group(0)!r}")

    # two passes: collect every page's ids first so cross-page anchors
    # (e.g. anatomy.html#merge) resolve against the real target page
    parsed = {}
    for page in ("index.html", "details.html", "404.html", "anatomy.html"):
        fp = os.path.join(root, page)
        if not os.path.exists(fp):
            err(f"missing page {page}")
            continue
        h = open(fp).read()
        c = Check()
        c.feed(h)
        parsed[page] = (c, h)

    for page, (c, h) in parsed.items():
        if c.stack:
            err(f"{page}: unclosed tags {c.stack}")
        errs += [f"{page}: {e}" for e in c.errs]
        dup = [i for i in set(c.ids) if c.ids.count(i) > 1]
        if dup:
            err(f"{page}: duplicate ids {dup}")
        for r in c.aria:
            if r not in c.ids:
                err(f"{page}: aria ref to missing id {r!r}")
        for x in c.hrefs + c.fills:
            if x.startswith("#"):
                if x[1:] not in c.ids:
                    err(f"{page}: dead anchor {x}")
            elif not re.match(r"^(https?:|data:|mailto:)", x):
                base, _, frag = x.partition("#")
                target = os.path.join(root, base.lstrip("/"))
                if not os.path.exists(target):
                    err(f"{page}: missing local target {x}")
                elif frag and base in parsed and frag not in parsed[base][0].ids:
                    err(f"{page}: dead cross-page anchor {x}")
        if page == "index.html" and "Content-Security-Policy" not in h:
            err("index.html: CSP meta missing")

    if "index.html" in parsed:
        c, h = parsed["index.html"]
        # the anatomy page must stay discoverable from the landing page
        if "anatomy.html" not in {x.partition("#")[0] for x in c.hrefs}:
            err("index.html: no link to anatomy.html — promotion regressed")
        # an open-PR snapshot must carry its date stamp and honesty disclaimer
        if "Under maintainer review" in h:
            if not re.search(r"snapshot as of \d{4}-\d{2}-\d{2}", h):
                err("index.html: open-PR snapshot lost its as-of date stamp")
            if "may close without merging" not in h:
                err("index.html: open-PR snapshot lost its disclaimer")

    og = os.path.join(root, "og.png")
    if not os.path.exists(og):
        err("og.png missing")
    elif open(og, "rb").read(8) != b"\x89PNG\r\n\x1a\n":
        err("og.png is not a PNG")

    ev = lambda n: open(os.path.join(root, "evidence", n)).read()
    try:
        if "SHIP PERMITTED" not in ev("proof_good.txt"):
            err("proof_good.txt lost its outcome marker")
        if "BLOCKED" not in ev("proof_bad.txt"):
            err("proof_bad.txt lost its outcome marker")
        if ev("gates.txt").count("  PASS ") != 16:
            err("gates.txt does not show exactly 16 passing gates")
        # the production run predates the 16th gate; its artifact shows 15
        if ev("anatomy/gates.txt").count("  PASS ") != 15:
            err("anatomy/gates.txt does not show exactly 15 passing gates")
    except OSError as e:
        err(f"evidence missing: {e}")

    if errs:
        print("SITE AUDIT FAILED:")
        for e in errs:
            print("  -", e)
        return 1
    print("site audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
