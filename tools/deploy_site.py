#!/usr/bin/env python3
"""Fail-closed deploy: build -> audit -> sync -> push (Actions re-audits and
deploys to Pages; a failing CI audit blocks the release, and every deploy is a
plain commit — rollback is `git revert` in the site repo).

Credentials: none in source — push uses the local git/osxkeychain auth.
"""
import os
import subprocess
import sys

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(LAB, "dist")
DEPLOY = os.path.join(LAB, ".deploy", "omegademo")
REMOTE = "https://github.com/SillyZir/omegademo"


def run(argv, cwd=None):
    print("$", " ".join(argv))
    p = subprocess.run(argv, cwd=cwd)
    if p.returncode != 0:
        sys.exit(f"deploy aborted: {' '.join(argv)} exited {p.returncode}")


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "Site update"
    run([sys.executable, os.path.join(LAB, "tools", "build_site.py")])
    run([sys.executable, os.path.join(LAB, "tools", "site_audit.py"), DIST])
    if not os.path.isdir(os.path.join(DEPLOY, ".git")):
        os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
        run(["git", "clone", "-q", REMOTE, DEPLOY])
    run(["git", "pull", "-q", "--rebase", "origin", "main"], cwd=DEPLOY)
    run(["rsync", "-a", "--delete", "--exclude", ".git", DIST + "/", DEPLOY])
    run(["git", "add", "-A"], cwd=DEPLOY)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=DEPLOY)
    if diff.returncode == 0:
        print("nothing changed; no deploy needed")
        return
    run(["git", "commit", "-q", "-m", msg], cwd=DEPLOY)
    run(["git", "push", "-q", "origin", "main"], cwd=DEPLOY)
    print("pushed — CI re-audits and deploys: "
          f"{REMOTE}/actions (rollback: git revert in {DEPLOY})")


if __name__ == "__main__":
    main()
