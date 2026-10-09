"""Archive persistence and consolidation checks; no provider credentials needed."""
import tempfile
import unittest
import uuid
from pathlib import Path

from backend.archive import ConversationArchive


class ArchiveTests(unittest.TestCase):
    def test_roundtrip_and_idempotent_merge(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            source = ConversationArchive(Path(first) / "archive.sqlite3")
            conversation_id, run_id = source.begin_run(
                conversation_id=None, prompt="Plan the refactor", provider="chatgpt",
                model="requested-model", effort="high",
            )
            source.finish_run(
                conversation_id=conversation_id, run_id=run_id,
                response="A plan", status="completed", duration_ms=1234,
                metadata={"provider": "chatgpt", "model": "actual-model", "reasoning_effort": "medium"},
                tool_results=[{"tool_name": "read_file", "success": True}],
            )
            source.begin_run(conversation_id=conversation_id, prompt="Follow up", provider="lmstudio", model="local", effort=None)
            exported = source.export_json()
            destination = ConversationArchive(Path(second) / "archive.sqlite3")
            counts = destination.import_json(exported)
            self.assertEqual(counts, {"conversations": 1, "messages": 3, "runs": 2})
            self.assertEqual(destination.import_json(exported), {"conversations": 0, "messages": 0, "runs": 0})
            restored = destination.get_conversation(conversation_id)
            self.assertEqual(restored["runs"][0]["model"], "actual-model")
            self.assertEqual(restored["runs"][0]["effort"], "medium")
            self.assertEqual(restored["runs"][0]["tool_results"][0]["tool_name"], "read_file")
            self.assertEqual(len(destination.list_conversations(search="Follow up")), 1)
            self.assertIn("actual-model", destination.export_markdown(conversation_id))

    def test_failure_is_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = ConversationArchive(Path(directory) / "archive.sqlite3")
            conversation_id, run_id = archive.begin_run(conversation_id=None, prompt="Hello", provider="lmstudio", model="x", effort=None)
            archive.finish_run(conversation_id=conversation_id, run_id=run_id, response="", status="failed", duration_ms=42, error="Unavailable")
            saved = archive.get_conversation(conversation_id)
            self.assertEqual(saved["runs"][0]["status"], "failed")
            self.assertEqual(saved["messages"][1]["error"], "Unavailable")

    def test_invalid_import_rolls_back_without_partial_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = ConversationArchive(Path(directory) / "archive.sqlite3")
            payload = {
                "format": "dirigent-conversation-archive",
                "version": 1,
                "conversations": [
                    {"id": str(uuid.uuid4()), "title": "First", "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00", "runs": [], "messages": []},
                    {"id": "invalid", "title": "Second", "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00", "runs": [], "messages": []},
                ],
            }
            with self.assertRaises(ValueError):
                archive.import_json(payload)
            self.assertEqual(archive.list_conversations(), [])

    def test_later_import_completes_a_previously_running_run(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            source = ConversationArchive(Path(first) / "archive.sqlite3")
            conversation_id, run_id = source.begin_run(
                conversation_id=None, prompt="Long job", provider="chatgpt",
                model="requested", effort=None,
            )
            destination = ConversationArchive(Path(second) / "archive.sqlite3")
            destination.import_json(source.export_json())
            source.finish_run(
                conversation_id=conversation_id, run_id=run_id, response="Done",
                status="completed", duration_ms=5000,
                metadata={"model": "actual", "reasoning_effort": "high"},
            )
            destination.import_json(source.export_json())
            saved = destination.get_conversation(conversation_id)
            self.assertEqual(saved["runs"][0]["status"], "completed")
            self.assertEqual(saved["runs"][0]["model"], "actual")
            self.assertEqual(saved["runs"][0]["effort"], "high")
            self.assertEqual(len(saved["messages"]), 2)


if __name__ == "__main__":
    unittest.main()
