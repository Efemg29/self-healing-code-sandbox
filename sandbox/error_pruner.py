"""Traceback sanitizer for token-efficient LLM reflection."""

from __future__ import annotations

import re

# Strip standard-library / site-packages frames that add noise without signal.
_STDLIB_PATH_RE = re.compile(
    r"^.*(/usr/lib/python[\d.]+/|/usr/local/lib/python[\d.]+/"
    r"|site-packages/|lib/python[\d.]+/).*$",
    re.MULTILINE,
)

# Keep assertion / exception blocks and local variable dumps.
_KEEP_MARKERS = (
    "AssertionError",
    "Error",
    "Exception",
    "FAILED",
    "E   ",
    "E       ",
    ">   ",
    "test_",
    "def test_",
    "locals",
    "Where:",
)


def prune_error_log(stderr: str, stdout: str = "", max_chars: int = 1000) -> str:
    """Sanitize sandbox logs for LLM consumption.

    Rules:
    1. Strip standard library / site-packages paths.
    2. Prefer failing test names, AssertionError/exception blocks, and locals.
    3. Cap length at ``max_chars``, truncating from the top (keep the bottom stack).
    """
    combined = "\n".join(part for part in (stdout, stderr) if part).strip()
    if not combined:
        return "No error output captured from sandbox."

    cleaned = _STDLIB_PATH_RE.sub("", combined)
    # Collapse excessive blank lines left behind by path stripping.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    lines = cleaned.splitlines()
    retained: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if retained and retained[-1] != "":
                retained.append("")
            continue
        if any(marker in line for marker in _KEEP_MARKERS):
            retained.append(line)
            continue
        # Keep traceback header / file frames under /app (our mounted code).
        if line.lstrip().startswith("File ") and "/app" in line:
            retained.append(line)
            continue
        if line.lstrip().startswith("Traceback"):
            retained.append(line)
            continue

    pruned = "\n".join(retained).strip() if retained else cleaned

    if len(pruned) > max_chars:
        pruned = pruned[-max_chars:]
        # Avoid starting mid-line after top-truncation.
        newline = pruned.find("\n")
        if 0 <= newline < 80:
            pruned = pruned[newline + 1 :]
        pruned = "...[truncated]...\n" + pruned

    return pruned
