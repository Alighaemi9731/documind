#!/usr/bin/env python3
"""PreToolUse(Bash) gate: block `git commit` when staged changes contain secrets.

Fails OPEN on any internal error (never blocks unrelated Bash commands); fails
CLOSED (exit 2) only when a `git commit` is about to include a likely secret or a
real `.env` file. Mirrors the CI `gitleaks` job for fast local feedback.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# (label, compiled pattern) — matched against ADDED lines in the staged diff.
PATTERNS = [
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Groq key", re.compile(r"gsk_[A-Za-z0-9]{20,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
]

# A secret-looking name assigned to a QUOTED STRING LITERAL. Anchoring on the
# quote avoids matching ordinary code (e.g. ``token = create_access_token(...)``
# or ``password=payload.password``) — only inline string secrets are flagged.
ASSIGN = re.compile(
    r"(?i)\b(JWT_SECRET|MASTER_KEY_FERNET|POSTGRES_PASSWORD|[A-Z0-9_]*SECRET|"
    r"[A-Z0-9_]*API_KEY|[A-Z0-9_]*TOKEN|[A-Z0-9_]*PASSWORD)\b\s*[=:]\s*"
    r"['\"]([^'\"]{8,})['\"]"
)
PLACEHOLDER = re.compile(
    r"(?i)^(change_me|changeme|your[-_]|<.*>|\$\{?.*\}?|xxx+|placeholder|ci-only|"
    r"example|todo|\.\.\.|null|none|true|false)"
)
# Non-secret literals that legitimately appear assigned (CI throwaways, app identifiers).
SAFE_LITERALS = {"documind", "postgres", "localhost", "example", "ci-only"}
# Characters that mark a value as a template/path/sed-expr/interpolation, not a raw secret.
# The strict provider-key PATTERNS above still catch real keys regardless.
TEMPLATE_CHARS = set("/$*{}")


def _is_secretish(value: str) -> bool:
    if PLACEHOLDER.match(value):
        return False
    if value.lower() in SAFE_LITERALS:
        return False
    if any(c in value for c in TEMPLATE_CHARS):
        return False
    return True


def is_git_commit(command: str) -> bool:
    if re.search(r"\bgit\b.*\bcommit\b", command) is None:
        return False
    # `git commit --dry-run` / `-n` style dry runs don't create a commit.
    return "--dry-run" not in command


def staged_env_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return []
    bad = []
    for name in out.splitlines():
        base = os.path.basename(name.strip())
        if base == ".env" or (base.startswith(".env.") and base != ".env.example"):
            bad.append(name.strip())
    return bad


def _is_test_path(path: str) -> bool:
    """Test files legitimately contain fake credentials; the strict provider-key
    PATTERNS still apply to them, but the generic ASSIGN heuristic does not."""
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    return (
        "/tests/" in p
        or "/test/" in p
        or "/e2e/" in p
        or base == "conftest.py"
        or base.startswith("test_")
        or base.endswith((".spec.ts", ".spec.tsx", ".test.ts", ".test.tsx", ".spec.js", ".test.js"))
    )


def scan_staged_diff() -> list[str]:
    try:
        diff = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--no-color"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return []
    findings: list[str] = []
    current_file = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        for label, pat in PATTERNS:
            if pat.search(added):
                findings.append(f"{current_file}: {label}: {added.strip()[:120]}")
        if not _is_test_path(current_file):
            m = ASSIGN.search(added)
            if m and _is_secretish(m.group(2)):
                findings.append(
                    f"{current_file}: secret-like assignment to {m.group(1)}: "
                    f"{added.strip()[:120]}"
                )
    return findings


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = (payload.get("tool_input") or {}).get("command", "")
    except Exception:
        return 0  # fail open — never block on parse error
    if not isinstance(command, str) or not is_git_commit(command):
        return 0

    problems = []
    env_files = staged_env_files()
    if env_files:
        problems.append("staged real env file(s): " + ", ".join(env_files))
    problems.extend(scan_staged_diff())

    if problems:
        sys.stderr.write(
            "BLOCKED: potential secrets in the staged commit.\n  - "
            + "\n  - ".join(problems[:20])
            + "\nUnstage/remove them (secrets belong in .env, generated by the installer) "
            "and retry. If this is a false positive, scrub the value before committing.\n"
        )
        return 2  # block the tool call
    return 0


if __name__ == "__main__":
    sys.exit(main())
