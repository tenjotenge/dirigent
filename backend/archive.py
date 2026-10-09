"""Local SQLite conversation archive with portable, idempotent exports."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.paths import get_app_data_dir

SCHEMA_VERSION = 1


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConversationArchive:
    def __init__(self, path: Path | None = None):
        self.path = path or get_app_data_dir() / "archive.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        if os.name != "nt":
            os.chmod(self.path, 0o600)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    run_id TEXT,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    effort TEXT,
                    error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id, created_at);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    effort TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_ms INTEGER,
                    status TEXT NOT NULL,
                    error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    tool_results_json TEXT NOT NULL DEFAULT '[]',
                    policy_decision_json TEXT NOT NULL DEFAULT 'null'
                );
                CREATE INDEX IF NOT EXISTS runs_conversation ON runs(conversation_id, started_at);
            """)

    def begin_run(self, *, conversation_id: str | None, prompt: str, provider: str,
                  model: str, effort: str | None) -> tuple[str, str]:
        conversation_id = conversation_id or str(uuid.uuid4())
        self._check_uuid(conversation_id)
        run_id = str(uuid.uuid4())
        timestamp = now_utc()
        title = " ".join(prompt.split())[:100] or "Untitled conversation"
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO conversations VALUES (?, ?, ?, ?)",
                (conversation_id, title, timestamp, timestamp),
            )
            connection.execute("UPDATE conversations SET updated_at=? WHERE id=?", (timestamp, conversation_id))
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 'running', NULL, '{}', '[]', 'null')",
                (run_id, conversation_id, provider, model, effort, timestamp),
            )
            connection.execute(
                "INSERT INTO messages VALUES (?, ?, ?, 'user', ?, ?, ?, ?, ?, NULL, '{}')",
                (str(uuid.uuid4()), conversation_id, run_id, prompt, timestamp, provider, model, effort),
            )
        return conversation_id, run_id

    def record_local_action(self, *, conversation_id: str | None, prompt: str,
                            response: str, tool_results: Any = None,
                            error: str | None = None, duration_ms: int = 0) -> str:
        conversation_id, run_id = self.begin_run(
            conversation_id=conversation_id, prompt=prompt,
            provider="dirigent", model="local-tool", effort=None,
        )
        self.finish_run(
            conversation_id=conversation_id, run_id=run_id, response=response,
            status="failed" if error else "completed", duration_ms=duration_ms,
            error=error, tool_results=tool_results,
        )
        return conversation_id

    def finish_run(self, *, conversation_id: str, run_id: str, response: str,
                   status: str, duration_ms: int, error: str | None = None,
                   metadata: dict[str, Any] | None = None,
                   tool_results: Any = None, policy_decision: Any = None) -> None:
        timestamp = now_utc()
        metadata = metadata or {}
        with self._connect() as connection:
            run = connection.execute("SELECT provider, model, effort FROM runs WHERE id=? AND conversation_id=?", (run_id, conversation_id)).fetchone()
            if run is None:
                raise ValueError("Unknown archive run")
            actual_effort = metadata.get("reasoning_effort") or run["effort"]
            actual_model = metadata.get("model") or run["model"]
            actual_provider = metadata.get("provider") or run["provider"]
            connection.execute(
                "UPDATE runs SET provider=?, model=?, effort=?, completed_at=?, duration_ms=?, status=?, error=?, metadata_json=?, tool_results_json=?, policy_decision_json=? WHERE id=?",
                (actual_provider, actual_model, actual_effort, timestamp, duration_ms, status, error, _json(metadata), _json(tool_results or []), _json(policy_decision), run_id),
            )
            connection.execute(
                "INSERT INTO messages VALUES (?, ?, ?, 'assistant', ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), conversation_id, run_id, response, timestamp, actual_provider, actual_model, actual_effort, error, _json(metadata)),
            )
            connection.execute("UPDATE conversations SET updated_at=? WHERE id=?", (timestamp, conversation_id))

    def list_conversations(self, search: str = "", limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        where = "WHERE c.title LIKE ? OR EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=c.id AND m.content LIKE ?)" if search else ""
        params: tuple[Any, ...] = (f"%{search}%", f"%{search}%") if search else ()
        with self._connect() as connection:
            rows = connection.execute(f"""
                SELECT c.*, COUNT(DISTINCT r.id) AS run_count,
                    (SELECT provider FROM runs WHERE conversation_id=c.id ORDER BY started_at DESC LIMIT 1) AS last_provider,
                    (SELECT model FROM runs WHERE conversation_id=c.id ORDER BY started_at DESC LIMIT 1) AS last_model,
                    (SELECT effort FROM runs WHERE conversation_id=c.id ORDER BY started_at DESC LIMIT 1) AS last_effort
                FROM conversations c LEFT JOIN runs r ON r.conversation_id=c.id
                {where} GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ? OFFSET ?
            """, (*params, min(max(limit, 1), 200), max(offset, 0))).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._get_conversation(connection, conversation_id)

    def _get_conversation(self, connection: sqlite3.Connection, conversation_id: str) -> dict[str, Any] | None:
        conversation = connection.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if conversation is None:
            return None
        messages = connection.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at, rowid", (conversation_id,)).fetchall()
        runs = connection.execute("SELECT * FROM runs WHERE conversation_id=? ORDER BY started_at, rowid", (conversation_id,)).fetchall()
        result = dict(conversation)
        result["messages"] = [self._decode_row(row) for row in messages]
        result["runs"] = [self._decode_row(row) for row in runs]
        return result

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in ("metadata_json", "tool_results_json", "policy_decision_json"):
            if key in result:
                result[key.removesuffix("_json")] = json.loads(result.pop(key))
        return result

    def export_json(self) -> dict[str, Any]:
        with self._connect() as connection:
            # Hold a read snapshot so another agent cannot change half of an
            # export while it is being assembled.
            connection.execute("BEGIN")
            ids = [row[0] for row in connection.execute("SELECT id FROM conversations ORDER BY created_at")]
            conversations = [self._get_conversation(connection, item) for item in ids]
        return {"format": "dirigent-conversation-archive", "version": SCHEMA_VERSION,
                "exported_at": now_utc(), "conversations": conversations}

    def import_json(self, payload: dict[str, Any]) -> dict[str, int]:
        if payload.get("format") != "dirigent-conversation-archive" or payload.get("version") != SCHEMA_VERSION:
            raise ValueError("Unsupported Dirigent archive format or version")
        conversations = payload.get("conversations")
        if not isinstance(conversations, list) or len(conversations) > 100000:
            raise ValueError("Invalid archive conversations list")
        counts = {"conversations": 0, "messages": 0, "runs": 0}
        with self._connect() as connection:
            for item in conversations:
                if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("id", "title", "created_at", "updated_at")):
                    raise ValueError("Invalid conversation in archive")
                self._check_uuid(item["id"])
                cursor = connection.execute("INSERT OR IGNORE INTO conversations VALUES (?, ?, ?, ?)",
                    (item["id"], item["title"], item["created_at"], item["updated_at"]))
                counts["conversations"] += cursor.rowcount
                connection.execute(
                    "UPDATE conversations SET updated_at=MAX(updated_at, ?) WHERE id=?",
                    (item["updated_at"], item["id"]),
                )
                if not isinstance(item.get("runs", []), list) or not isinstance(item.get("messages", []), list):
                    raise ValueError("Invalid conversation entries in archive")
                for run in item.get("runs", []):
                    if not isinstance(run, dict) or not all(isinstance(run.get(key), str) for key in ("id", "provider", "model", "started_at", "status")):
                        raise ValueError("Invalid run in archive")
                    self._check_uuid(run["id"])
                    cursor = connection.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (run["id"], item["id"], run["provider"], run["model"], run.get("effort"), run["started_at"], run.get("completed_at"), run.get("duration_ms"), run["status"], run.get("error"), _json(run.get("metadata", {})), _json(run.get("tool_results", [])), _json(run.get("policy_decision"))))
                    counts["runs"] += cursor.rowcount
                    # A previous export may have captured this run while it was still
                    # in progress. A later import must be able to complete it.
                    if cursor.rowcount == 0 and run["status"] != "running":
                        connection.execute("""
                            UPDATE runs SET provider=?, model=?, effort=?, completed_at=?,
                                duration_ms=?, status=?, error=?, metadata_json=?,
                                tool_results_json=?, policy_decision_json=?
                            WHERE id=? AND conversation_id=? AND status='running'
                        """, (run["provider"], run["model"], run.get("effort"),
                              run.get("completed_at"), run.get("duration_ms"),
                              run["status"], run.get("error"),
                              _json(run.get("metadata", {})), _json(run.get("tool_results", [])),
                              _json(run.get("policy_decision")), run["id"], item["id"]))
                for message in item.get("messages", []):
                    if not isinstance(message, dict) or not all(isinstance(message.get(key), str) for key in ("id", "role", "content", "created_at")) or message["role"] not in ("user", "assistant"):
                        raise ValueError("Invalid message in archive")
                    self._check_uuid(message["id"])
                    cursor = connection.execute("INSERT OR IGNORE INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (message["id"], item["id"], message.get("run_id"), message["role"], message["content"], message["created_at"], message.get("provider"), message.get("model"), message.get("effort"), message.get("error"), _json(message.get("metadata", {}))))
                    counts["messages"] += cursor.rowcount
        return counts

    @staticmethod
    def _check_uuid(value: str) -> None:
        try:
            uuid.UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Archive IDs must be UUIDs") from exc

    def export_markdown(self, conversation_id: str) -> str | None:
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            return None
        lines = [f"# {conversation['title']}", "", f"Conversation ID: `{conversation_id}`", ""]
        for message in conversation["messages"]:
            lines.extend([f"## {message['role'].title()} — {message['created_at']}", ""])
            if message["provider"]:
                lines.append(f"Provider: `{message['provider']}` · Model: `{message['model'] or 'unknown'}` · Effort: `{message['effort'] or 'unknown'}`")
                lines.append("")
            lines.extend([message["content"] or "(empty response)", ""])
            if message["error"]:
                lines.extend([f"Error: {message['error']}", ""])
        lines.extend(["## Run details", ""])
        for run in conversation["runs"]:
            lines.extend([
                f"### {run['started_at']} — {run['provider']} / {run['model']}", "",
                f"Status: {run['status']} · Effort: {run['effort'] or 'unknown'} · Duration: {run['duration_ms'] if run['duration_ms'] is not None else 'unknown'} ms", "",
                "````json",
                json.dumps({"metadata": run["metadata"], "tool_results": run["tool_results"], "policy_decision": run["policy_decision"]}, ensure_ascii=False, indent=2),
                "````", "",
            ])
        return "\n".join(lines)


archive = ConversationArchive()
