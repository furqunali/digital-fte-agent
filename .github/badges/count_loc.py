#!/usr/bin/env python3
"""Count real lines of code in this repository and emit a shields.io endpoint badge.

Counts non-blank lines in authored source, markup, config and docs files.
Skips VCS/build/vendor directories and generated/lock/minified files.
Run from the repository root. Writes .github/badges/loc.json
"""
import json
import os
import sys

INCLUDE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".html", ".htm", ".css", ".scss", ".sass",
    ".java", ".go", ".rb", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".sh", ".bash", ".ps1", ".sql",
    ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".json", ".md", ".rst", ".txt",
}
EXCLUDE_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next",
    ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", "vendor", "coverage", ".github/badges",
}
EXCLUDE_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock",
    "pnpm-lock.yaml", "composer.lock",
}


def is_excluded_file(name: str) -> bool:
    if name in EXCLUDE_FILES:
        return True
    if name.endswith((".min.js", ".min.css", ".map")):
        return True
    return False


def count() -> int:
    total = 0
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        # skip nested .github/badges
        if os.path.normpath(root).endswith(os.path.join(".github", "badges")):
            continue
        for f in files:
            if is_excluded_file(f):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in INCLUDE_EXT:
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        if line.strip():
                            total += 1
            except (OSError, UnicodeError):
                continue
    return total


def humanize(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def main() -> int:
    n = count()
    os.makedirs(os.path.join(".github", "badges"), exist_ok=True)
    badge = {
        "schemaVersion": 1,
        "label": "lines of code",
        "message": humanize(n),
        "color": "blue",
    }
    out = os.path.join(".github", "badges", "loc.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(badge, fh)
    print(f"{n} lines of code -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
