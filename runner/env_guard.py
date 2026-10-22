"""DEMO SHIM — this file is the ONE deliberate substitution in this lab.

The production system's ``runner/env_guard.py`` pins every heavy artifact
(clones, GOMODCACHE, cargo caches) to a dedicated external SSD and refuses to
run if it is not mounted — see the public showcase repo for the real module.
That storage topology is irrelevant on a reviewer's laptop, so this shim keeps
the two functions ``agent/test_exec.py`` imports, backed by the plain
environment instead. Every other module in ``agent/`` and ``cloud/`` is
byte-identical to the production code (verify against ``MANIFEST.json``).
"""

import os
import tempfile


def build_env(extra=None):
    """Plain inherited environment (production pins caches to an SSD here)."""
    env = {**os.environ}
    if extra:
        env.update(extra)
    return env


def cargo_target_dir(repo_id):
    """Per-repo cargo target dir outside the clone (unused by the Go demo)."""
    d = os.path.join(tempfile.gettempdir(), "omega-lab-cargo-target", repo_id)
    os.makedirs(d, exist_ok=True)
    return d
