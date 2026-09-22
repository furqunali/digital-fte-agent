from __future__ import annotations

import hashlib
from pathlib import Path

from .models import Task


def parse_task(path: Path) -> Task:
    text=path.read_text(encoding="utf-8-sig").strip()
    lines=text.splitlines()
    title=next((line[2:].strip() for line in lines if line.startswith("# ")), path.stem)
    return Task(path,hashlib.sha256(text.encode()).hexdigest()[:16],title,text)
