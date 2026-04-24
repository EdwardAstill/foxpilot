# `foxpilot mission`

Mission Mode is the planning and state foundation for longer browser tasks. The first implementation creates an auditable plan and stores mission state; browser execution is intentionally represented as status transitions until step execution and evidence checkpoints are added.

## Storage

Mission files are JSON documents stored in:

```text
~/.local/share/foxpilot/missions/
```

Tests and callers can pass an alternate root directory to the mission helpers.

## Commands

```bash
foxpilot mission run "download the latest invoice from OneDrive" --json
foxpilot mission status MISSION_ID
foxpilot mission cancel MISSION_ID
```

## State Model

Each mission records:

- Mission id.
- Original task.
- Mission status.
- Created and updated timestamps.
- Planned steps.

Each step records:

- Step id.
- Kind, such as `navigate`, `inspect`, `act`, or `evidence`.
- Human-readable description.
- Status.
- Evidence paths.
- Structured result data.

## Safety

Mission execution should pause before destructive or externally visible actions. Future step execution should combine mission steps with `foxpilot.safety.detect_dangerous_actions` and require confirmation before continuing.
