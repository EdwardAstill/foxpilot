"""Standalone mission planning and state persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_MISSION_ROOT = Path.home() / ".local" / "share" / "foxpilot" / "missions"


@dataclass
class MissionStep:
    step_id: str
    kind: str
    description: str
    status: str = "pending"
    evidence: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionState:
    mission_id: str
    task: str
    status: str
    steps: list[MissionStep]
    created_at: str
    updated_at: str
    root: str = ""


def mission_root(root: str | Path | None = None) -> Path:
    return Path(root).expanduser() if root is not None else DEFAULT_MISSION_ROOT


def mission_path(mission_id: str, root: str | Path | None = None) -> Path:
    return mission_root(root) / f"{mission_id}.json"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _step(kind: str, description: str) -> MissionStep:
    return MissionStep(step_id=uuid.uuid4().hex[:12], kind=kind, description=description)


def plan_steps(task: str) -> list[MissionStep]:
    """Generate a deterministic placeholder plan for a plain-language task."""

    compact_task = " ".join(task.split()) or "requested browser task"
    return [
        _step("navigate", f"Open the starting page for: {compact_task}"),
        _step("inspect", "Inspect the page state and available actions"),
        _step("act", f"Perform the next safe browser action for: {compact_task}"),
        _step("evidence", "Capture evidence and summarize the result"),
    ]


def create_mission(task: str, *, root: str | Path | None = None) -> MissionState:
    now = _timestamp()
    state = MissionState(
        mission_id=uuid.uuid4().hex,
        task=task,
        status="planned",
        steps=plan_steps(task),
        created_at=now,
        updated_at=now,
        root=str(mission_root(root)),
    )
    save_mission(state, root=root)
    return state


def save_mission(state: MissionState, *, root: str | Path | None = None) -> Path:
    root_path = mission_root(root or state.root or None)
    root_path.mkdir(parents=True, exist_ok=True)
    state.root = str(root_path)
    state.updated_at = _timestamp()
    path = mission_path(state.mission_id, root_path)
    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n")
    return path


def load_mission(mission_id: str, *, root: str | Path | None = None) -> MissionState:
    data = json.loads(mission_path(mission_id, root).read_text())
    steps = [MissionStep(**step) for step in data.pop("steps")]
    return MissionState(steps=steps, **data)


def update_mission_status(
    mission_id: str, status: str, *, root: str | Path | None = None
) -> MissionState:
    state = load_mission(mission_id, root=root)
    state.status = status
    save_mission(state, root=root)
    return state


def update_step_status(
    mission_id: str,
    step_id: str,
    status: str,
    *,
    root: str | Path | None = None,
    result: dict[str, Any] | None = None,
    evidence: list[str] | None = None,
) -> MissionState:
    state = load_mission(mission_id, root=root)
    for step in state.steps:
        if step.step_id == step_id:
            step.status = status
            if result is not None:
                step.result = result
            if evidence is not None:
                step.evidence = evidence
            break
    else:
        raise ValueError(f"unknown mission step: {step_id}")
    save_mission(state, root=root)
    return state
