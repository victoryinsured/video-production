"""Run tracking (see VIDEO_ENGINE.md §8/§12).

The legacy engine kept an in-memory/console-only log of what it did on a run and never persisted
step state to disk — the web app's `JobStep` table is the real source of truth for step state.
This module's `RunTracker` is a lightweight, additive JSON-log writer used only so a CLI
invocation leaves a human-readable trail in the lesson's output directory for debugging and
manual support, independent of the database.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class RunTracker:
    output_dir: Path
    events: List[Dict[str, Any]] = field(default_factory=list)

    def log(self, step: str, status: str, **details: Any) -> None:
        self.events.append({
            "ts": time.time(),
            "step": step,
            "status": status,
            **details,
        })

    def write(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / "run_log.json"
        path.write_text(json.dumps(self.events, indent=2), encoding="utf-8")
        return path
