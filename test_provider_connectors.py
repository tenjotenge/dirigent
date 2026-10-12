"""Offline checks for API credential and direct-model connector scaffolding."""
import asyncio
import importlib
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.archive import ConversationArchive
from backend.provider_credentials import ProviderCredentialStore
from backend.providers.claude import ClaudeProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class ConnectorTests(unittest.TestCase):
    def test_credential_source_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProviderCredentialStore()
            store._directory = Path(directory) / "providers"
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
                self.assertIsNone(store.get_secret("claude"))
                store.save("claude", "local-secret")
                self.assertEqual(store.get_secret("claude"), "local-secret")
                local_status = next(x for x in store.status() if x["id"] == "claude")
                self.assertEqual(local_status["source"], "local")
                self.assertTrue(local_status["local_stored"])
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "environment-secret"}):
                    self.assertEqual(store.get_secret("claude"), "environment-secret")
                    env_status = next(x for x in store.status() if x["id"] == "claude")
                    self.assertEqual(env_status["source"], "environment")
                    self.assertTrue(env_status["local_stored"])

    def test_claude_models_generation_and_archive_metadata(self):
        api = importlib.import_module("backend.app")
        claude_module = importlib.import_module("backend.providers.claude")
        with tempfile.TemporaryDirectory() as directory:
            store = ProviderCredentialStore()
            store._directory = Path(directory) / "providers"
            store.save("claude", "test-secret")
            archived = ConversationArchive(Path(directory) / "archive.sqlite3")
            model_response = FakeResponse({"data": [{"id": "claude-model-a"}]})
            message_response = FakeResponse({
                "model": "claude-actual-model",
                "content": [{"type": "text", "text": "Hello from Claude"}],
                "usage": {"input_tokens": 7, "output_tokens": 3},
                "stop_reason": "end_turn",
            })
            with patch.object(claude_module, "provider_credentials", store), \
                    patch.object(claude_module.requests, "get", return_value=model_response) as get, \
                    patch.object(claude_module.requests, "post", return_value=message_response) as post, \
                    patch.object(api, "archive", archived):
                self.assertEqual(ClaudeProvider().list_models(), ["claude-model-a"])
                result = asyncio.run(api.generate(api.GenerateRequest(
                    provider="claude", model="claude-model-a", prompt="Hello",
                    conversation_id=uuid.uuid4(), effort="high",
                )))
            self.assertEqual(get.call_args.kwargs["headers"]["x-api-key"], "test-secret")
            self.assertEqual(post.call_args.kwargs["json"]["output_config"], {"effort": "high"})
            self.assertNotIn("temperature", post.call_args.kwargs["json"])
            self.assertEqual(result.response, "Hello from Claude")
            saved = archived.get_conversation(result.conversation_id)
            self.assertEqual(saved["runs"][0]["provider"], "claude")
            self.assertEqual(saved["runs"][0]["model"], "claude-actual-model")
            self.assertEqual(saved["runs"][0]["effort"], "high")
            self.assertEqual(saved["runs"][0]["metadata"]["usage"]["output_tokens"], 3)

    def test_agent_services_do_not_enter_direct_generation_routes(self):
        api = importlib.import_module("backend.app")
        catalog = importlib.import_module("backend.providers.catalog")
        capabilities = {item["id"]: item for item in catalog.provider_capabilities()}
        self.assertTrue(capabilities["claude"]["generation_route"])
        for service in ("cursor", "devin", "openclaw"):
            self.assertFalse(capabilities[service]["generation_route"])
            self.assertNotIn(service, api.engines)


if __name__ == "__main__":
    unittest.main()
