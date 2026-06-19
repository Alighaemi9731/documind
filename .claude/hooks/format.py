#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit): best-effort auto-format the touched file.

Always exits 0 — formatting is a convenience, never a gate. No-ops silently when
the relevant formatter isn't installed yet (e.g. before deps are set up).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUFF = os.path.join(REPO, "apps", "api", ".venv", "bin", "ruff")
PRETTIER = os.path.join(REPO, "apps", "web", "node_modules", ".bin", "prettier")

PY_EXT = {".py"}
JS_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".css", ".md", ".mdx", ".yml", ".yaml"}


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=60)
    except Exception:
        pass


def which(name: str) -> str | None:
    from shutil import which as _which
    return _which(name)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = (payload.get("tool_input") or {}).get("file_path", "")
    except Exception:
        return 0
    if not path or not os.path.isfile(path):
        return 0
    ext = os.path.splitext(path)[1].lower()

    if ext in PY_EXT:
        ruff = RUFF if os.path.exists(RUFF) else which("ruff")
        if ruff:
            run([ruff, "format", path])
            run([ruff, "check", "--fix", "--quiet", path])
        elif which("black"):
            run(["black", "-q", path])
    elif ext in JS_EXT:
        prettier = PRETTIER if os.path.exists(PRETTIER) else None
        if prettier:
            run([prettier, "--write", "--log-level", "warn", path])
    return 0


if __name__ == "__main__":
    sys.exit(main())
