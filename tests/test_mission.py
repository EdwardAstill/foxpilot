import json
import tempfile
import unittest
from pathlib import Path

from foxpilot.mission import (
    MissionState,
    create_mission,
    load_mission,
    save_mission,
    update_mission_status,
    update_step_status,
)


class MissionTests(unittest.TestCase):
    def test_create_mission_writes_json_with_basic_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = create_mission("Go to example.com and inspect the pricing", root=tmp)

            path = Path(tmp) / f"{state.mission_id}.json"
            saved = json.loads(path.read_text())

        self.assertEqual(state.task, "Go to example.com and inspect the pricing")
        self.assertEqual(state.status, "planned")
        self.assertGreaterEqual(len(state.steps), 4)
        self.assertEqual(state.steps[0].kind, "navigate")
        self.assertEqual(saved["mission_id"], state.mission_id)
        self.assertEqual(saved["steps"][0]["kind"], "navigate")

    def test_save_and_load_round_trip_dataclasses(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = create_mission("inspect checkout flow", root=tmp)
            state.steps[0].status = "complete"
            save_mission(state, root=tmp)

            loaded = load_mission(state.mission_id, root=tmp)

        self.assertIsInstance(loaded, MissionState)
        self.assertEqual(loaded.steps[0].status, "complete")
        self.assertEqual(loaded.task, "inspect checkout flow")

    def test_update_helpers_persist_status_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = create_mission("publish a draft", root=tmp)

            updated = update_mission_status(state.mission_id, "paused", root=tmp)
            updated = update_step_status(
                state.mission_id, state.steps[1].step_id, "blocked", root=tmp
            )
            loaded = load_mission(state.mission_id, root=tmp)

        self.assertEqual(updated.status, "paused")
        self.assertEqual(loaded.status, "paused")
        self.assertEqual(loaded.steps[1].status, "blocked")


if __name__ == "__main__":
    unittest.main()
