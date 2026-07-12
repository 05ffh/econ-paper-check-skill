#!/usr/bin/env python3
"""Refresh benchmarks/env/lock.txt with current pip freeze."""
from __future__ import annotations
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK = REPO_ROOT / "benchmarks" / "env" / "lock.txt"


def main() -> int:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print("pip freeze failed:", proc.stderr, file=sys.stderr)
        return 1
    py = sys.version.split()[0]
    ts = datetime.now(timezone.utc).isoformat()
    header = (
        f"# benchmarks/env/lock.txt (M4 v0.2)\n"
        f"# generated_at: {ts}\n"
        f"# python: {py}\n"
        f"# purpose: dependency_lock_hash for metrics.json reproducibility\n"
        f"# NOTE: this is an environment snapshot, NOT an install manifest.\n"
        f"\n"
    )
    body = proc.stdout
    LOCK.write_text(header + body, encoding="utf-8")

    h = hashlib.sha256((header + body).encode("utf-8")).hexdigest()
    print(f"wrote {LOCK.relative_to(REPO_ROOT)}  bytes={len(header)+len(body)}  sha256={h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
