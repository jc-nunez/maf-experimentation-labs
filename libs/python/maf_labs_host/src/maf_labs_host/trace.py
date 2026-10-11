"""Append-only trajectory files (``trace.jsonl``) — the input for replay, evals and the web viewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TraceWriter:
    def __init__(self, run_dir: Path) -> None:
        self.dir = run_dir
        self.path = run_dir / "trace.jsonl"
        self._fh: Any = None

    def write(self, event: dict[str, Any]) -> None:
        if self._fh is None:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("a", encoding="utf-8")
        self._fh.write(json.dumps(event, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def read_trace(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
