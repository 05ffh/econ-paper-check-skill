"""
Reproducibility hashing helpers (M4 v0.2).
"""
from __future__ import annotations
import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_paths(paths: list[Path]) -> str:
    """Aggregate sha256 over sorted file list: sha256 of "sha256  path\n" lines."""
    lines = []
    for p in sorted(paths):
        rel = p.relative_to(REPO_ROOT).as_posix()
        h = _hash_file(p)
        lines.append(f"{h}  {rel}\n")
    aggregate = "".join(lines).encode("utf-8")
    return hashlib.sha256(aggregate).hexdigest()


def hash_dir(root: Path, patterns: list[str]) -> str:
    """
    Hash aggregate for all files under `root` matching any pattern.
    Patterns are glob-style, e.g. ["*.md", "*.yaml"].
    """
    from itertools import chain
    files: list[Path] = []
    for pat in patterns:
        files.extend(root.rglob(pat))
    # dedup
    files = sorted(set(files))
    return hash_paths(files)


def rules_hash() -> str:
    """rules/ + agent_instructions/ + references/ all md/yaml files."""
    files: list[Path] = []
    for sub in ["rules", "agent_instructions", "references"]:
        d = REPO_ROOT / sub
        if not d.exists():
            continue
        for pat in ["*.md", "*.yaml", "*.yml"]:
            files.extend(d.rglob(pat))
    files = sorted(set(files))
    return hash_paths(files)


def agent_instructions_hash() -> str:
    d = REPO_ROOT / "agent_instructions"
    if not d.exists():
        return "0" * 64
    files = sorted(set(d.rglob("*.md")))
    return hash_paths(files)


def kb_a_snapshot_hash() -> str:
    d = REPO_ROOT / "knowledge_base" / "norms"
    if not d.exists():
        return "0" * 64
    files = sorted(set(d.rglob("*.yaml")))
    return hash_paths(files)


def kb_b_snapshot_hash() -> str | None:
    """
    Content-addressed hash of KB-B metadata YAMLs.
    The active chroma DB itself is binary/varying and not hashed.
    """
    d = REPO_ROOT / "knowledge_base" / "examples" / "metadata"
    if not d.exists():
        return None
    files = sorted(set(d.rglob("*.yaml")))
    if not files:
        return None
    return hash_paths(files)


def vision_schema_hash() -> str:
    d = REPO_ROOT / "scripts" / "vision"
    if not d.exists():
        return "0" * 64
    files = sorted(set(d.rglob("*.py")))
    return hash_paths(files)


def prompt_template_hash() -> str:
    """
    Extract _SYSTEM_PROMPT_STRICT literal from ark_provider.py and hash it.
    Falls back to hashing the whole ark_provider.py if not extractable.
    """
    p = REPO_ROOT / "scripts" / "vision" / "providers" / "ark_provider.py"
    if not p.exists():
        return "0" * 64
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return _hash_file(path)


def dependency_lock_hash() -> str:
    p = REPO_ROOT / "benchmarks" / "env" / "lock.txt"
    if not p.exists():
        return "0" * 64
    return _hash_file(p)


def report_template_hash() -> str:
    """Hash render_report.py + render_report_html.py."""
    files: list[Path] = []
    for name in ["render_report.py", "render_report_html.py"]:
        p = REPO_ROOT / "scripts" / name
        if p.exists():
            files.append(p)
    if not files:
        return "0" * 64
    return hash_paths(files)
