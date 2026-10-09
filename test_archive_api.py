"""Check that generation is persisted at the API boundary."""
import asyncio
import importlib
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.archive import ConversationArchive
from backend.providers.chatgpt import ChatGPTProvider
from backend.providers.lmstudio import LMStudioProvider


class FakeEngine:
    def __init__(self, fail=False):
        self.fail = fail

    def execute(self, **_kwargs):
        if self.fail:
            raise RuntimeError("provider unavailable")
        return {
            "content": "Archived answer",
            "tool_results": [{"tool_name": "read_file", "success": True}],
            "policy_decision": None,
            "metadata": {"provider": "chatgpt", "model": "actual-model", "reasoning_effort": "high"},
        }


class ArchiveApiTests(unittest.TestCase):
    def test_provider_metadata_uses_actual_model_and_effort_when_available(self):
        class ChatResponse:
            def raise_for_status(self):
                pass

            def iter_lines(self, decode_unicode=False):
                return iter([
                    'data: {"type":"response.output_text.delta","delta":"Answer"}',
                    'data: {"type":"response.completed","response":{"model":"actual-chat-model","reasoning":{"effort":"medium"},"usage":{"input_tokens":5}}}',
                ])

        with patch("backend.providers.chatgpt.chatgpt_auth.active_access_token", return_value="test-token"), patch("backend.providers.chatgpt.requests.post", return_value=ChatResponse()):
            result = ChatGPTProvider().send("Hello", "requested-chat-model")
        self.assertEqual(result.metadata["model"], "actual-chat-model")
        self.assertEqual(result.metadata["reasoning_effort"], "medium")
        self.assertEqual(result.metadata["usage"]["input_tokens"], 5)

        class LocalResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"model": "actual-local-model", "choices": [{"message": {"content": "Answer"}}], "usage": {"total_tokens": 9}}

        with patch("backend.providers.lmstudio.requests.post", return_value=LocalResponse()):
            local = LMStudioProvider().send("Hello", "requested-local-model")
        self.assertEqual(local.metadata["model"], "actual-local-model")
        self.assertNotIn("reasoning_effort", local.metadata)

    def test_generation_and_failure_are_persisted(self):
        api = importlib.import_module("backend.app")
        with tempfile.TemporaryDirectory() as directory:
            archive = ConversationArchive(Path(directory) / "archive.sqlite3")
            conversation_id = uuid.uuid4()
            with patch.object(api, "archive", archive), patch.object(api, "_engine_for", return_value=FakeEngine()):
                result = asyncio.run(api.generate(api.GenerateRequest(
                    provider="chatgpt", model="requested-model", prompt="Hello",
                    conversation_id=conversation_id,
                )))
            self.assertEqual(result.response, "Archived answer")
            self.assertEqual(result.conversation_id, str(conversation_id))
            saved = archive.get_conversation(str(conversation_id))
            self.assertEqual(saved["runs"][0]["model"], "actual-model")
            self.assertEqual(saved["runs"][0]["effort"], "high")
            self.assertEqual(saved["runs"][0]["tool_results"][0]["tool_name"], "read_file")

            with patch.object(api, "archive", archive), patch.object(api, "_engine_for", return_value=FakeEngine(fail=True)):
                with self.assertRaises(api.HTTPException):
                    asyncio.run(api.generate(api.GenerateRequest(
                        provider="chatgpt", model="requested-model", prompt="Fail",
                        conversation_id=conversation_id,
                    )))
            saved = archive.get_conversation(str(conversation_id))
            self.assertEqual(saved["runs"][1]["status"], "failed")
            self.assertEqual(saved["messages"][-1]["error"], "provider unavailable")

            with patch.object(api, "archive", archive):
                action = asyncio.run(api.archive_local_action(api.ArchiveActionRequest(
                    conversation_id=conversation_id, prompt="Git status", response="Clean",
                    tool_results=[{"tool_name": "git_status", "success": True}],
                )))
            self.assertEqual(action["conversation_id"], str(conversation_id))
            self.assertEqual(archive.get_conversation(str(conversation_id))["runs"][-1]["provider"], "dirigent")


if __name__ == "__main__":
    unittest.main()
