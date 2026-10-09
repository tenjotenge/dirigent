"""Encrypted Parquet archive transfer tests; no live provider required."""
import asyncio
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, Request

from backend.archive import ConversationArchive
from backend.archive_parquet import MAGIC, export_encrypted_parquet, import_encrypted_parquet


class EncryptedParquetTests(unittest.TestCase):
    def test_api_exports_only_encrypted_payload(self):
        api = importlib.import_module("backend.app")
        with tempfile.TemporaryDirectory() as directory:
            local_archive = ConversationArchive(Path(directory) / "archive.sqlite3")
            with patch.object(api, "archive", local_archive):
                response = asyncio.run(api.export_archive_parquet(
                    api.ArchivePassphraseRequest(passphrase="a long unique passphrase")))
                self.assertTrue(response.body.startswith(MAGIC))
                self.assertEqual(response.headers["cache-control"], "no-store")

                async def receive():
                    return {"type": "http.request", "body": response.body, "more_body": False}

                request = Request({"type": "http", "method": "POST", "path": "/archive/import.dpa",
                                   "headers": [(b"content-length", str(len(response.body)).encode())]}, receive)
                self.assertEqual(asyncio.run(api.import_archive_parquet(
                    request, "a long unique passphrase"))["conversations"], 0)
                with self.assertRaises(HTTPException) as failure:
                    asyncio.run(api.export_archive_parquet(
                        api.ArchivePassphraseRequest(passphrase="too short")))
                self.assertEqual(failure.exception.status_code, 400)
        paths = {route.path for route in api.app.routes}
        self.assertNotIn("/archive/export.json", paths)
        self.assertNotIn("/archive/conversations/{conversation_id}/export.md", paths)

    def test_roundtrip_metadata_and_idempotent_consolidation(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            source = ConversationArchive(Path(first) / "archive.sqlite3")
            conversation_id, run_id = source.begin_run(
                conversation_id=None, prompt="Private prompt", provider="chatgpt",
                model="requested-model", effort=None,
            )
            source.finish_run(
                conversation_id=conversation_id, run_id=run_id,
                response="Private answer", status="completed", duration_ms=1200,
                metadata={"provider": "chatgpt", "model": "actual-model", "reasoning_effort": "high"},
                tool_results=[{"tool_name": "read_file", "success": True}],
                policy_decision={"allowed_calls": []},
            )
            data = export_encrypted_parquet(source, "a long unique passphrase")
            self.assertTrue(data.startswith(MAGIC))
            self.assertNotIn(b"Private prompt", data)
            self.assertNotIn(b"Private answer", data)
            self.assertNotIn(b"actual-model", data)
            self.assertNotIn(b"PAR1", data)

            destination = ConversationArchive(Path(second) / "archive.sqlite3")
            self.assertEqual(import_encrypted_parquet(destination, data, "a long unique passphrase"),
                             {"conversations": 1, "messages": 2, "runs": 1})
            self.assertEqual(import_encrypted_parquet(destination, data, "a long unique passphrase"),
                             {"conversations": 0, "messages": 0, "runs": 0})
            saved = destination.get_conversation(conversation_id)
            self.assertEqual(saved["messages"][1]["content"], "Private answer")
            self.assertEqual(saved["runs"][0]["model"], "actual-model")
            self.assertEqual(saved["runs"][0]["effort"], "high")
            self.assertEqual(saved["runs"][0]["tool_results"][0]["tool_name"], "read_file")
            self.assertEqual(saved["runs"][0]["policy_decision"], {"allowed_calls": []})

    def test_wrong_password_or_tampering_imports_nothing(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            source = ConversationArchive(Path(first) / "archive.sqlite3")
            source.begin_run(conversation_id=None, prompt="Secret", provider="lmstudio", model="local", effort=None)
            data = export_encrypted_parquet(source, "correct long passphrase")
            destination = ConversationArchive(Path(second) / "archive.sqlite3")
            with self.assertRaisesRegex(ValueError, "Incorrect passphrase"):
                import_encrypted_parquet(destination, data, "incorrect long passphrase")
            tampered = bytearray(data)
            tampered[-1] ^= 1
            with self.assertRaisesRegex(ValueError, "damaged archive"):
                import_encrypted_parquet(destination, bytes(tampered), "correct long passphrase")
            self.assertEqual(destination.list_conversations(), [])

    def test_empty_archive_and_short_passphrase(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            source = ConversationArchive(Path(first) / "archive.sqlite3")
            destination = ConversationArchive(Path(second) / "archive.sqlite3")
            with self.assertRaisesRegex(ValueError, "12 characters"):
                export_encrypted_parquet(source, "short")
            data = export_encrypted_parquet(source, "a long unique passphrase")
            self.assertEqual(import_encrypted_parquet(destination, data, "a long unique passphrase"),
                             {"conversations": 0, "messages": 0, "runs": 0})


if __name__ == "__main__":
    unittest.main()
