"""Password-protected Parquet transport for the SQLite conversation archive.

The .dpa envelope contains only a format marker, random salt, random nonce, and
AES-GCM ciphertext. Its Parquet schema and conversation data are encrypted.
"""
from __future__ import annotations

import json
import os
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from backend.archive import ConversationArchive, SCHEMA_VERSION, now_utc

MAGIC = b"DIRIGENT-DPA-1\0"
SALT_BYTES = 16
NONCE_BYTES = 12
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024

MESSAGE = pa.struct([
    ("id", pa.string()), ("run_id", pa.string()), ("role", pa.string()),
    ("content", pa.string()), ("created_at", pa.string()),
    ("provider", pa.string()), ("model", pa.string()), ("effort", pa.string()),
    ("error", pa.string()), ("metadata_json", pa.string()),
])
RUN = pa.struct([
    ("id", pa.string()), ("provider", pa.string()), ("model", pa.string()),
    ("effort", pa.string()), ("started_at", pa.string()),
    ("completed_at", pa.string()), ("duration_ms", pa.int64()),
    ("status", pa.string()), ("error", pa.string()),
    ("metadata_json", pa.string()), ("tool_results_json", pa.string()),
    ("policy_decision_json", pa.string()),
])
SCHEMA = pa.schema([
    ("id", pa.string()), ("title", pa.string()),
    ("created_at", pa.string()), ("updated_at", pa.string()),
    ("messages", pa.list_(MESSAGE)), ("runs", pa.list_(RUN)),
])


def _password_key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 12:
        raise ValueError("Archive passphrase must contain at least 12 characters")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))


def _encode_rows(payload: dict[str, Any]) -> pa.Table:
    rows = []
    for conversation in payload["conversations"]:
        rows.append({
            "id": conversation["id"], "title": conversation["title"],
            "created_at": conversation["created_at"], "updated_at": conversation["updated_at"],
            "messages": [
                {**{key: message.get(key) for key in (
                    "id", "run_id", "role", "content", "created_at", "provider",
                    "model", "effort", "error")},
                 "metadata_json": json.dumps(message.get("metadata", {}), ensure_ascii=False)}
                for message in conversation["messages"]
            ],
            "runs": [
                {**{key: run.get(key) for key in (
                    "id", "provider", "model", "effort", "started_at", "completed_at",
                    "duration_ms", "status", "error")},
                 "metadata_json": json.dumps(run.get("metadata", {}), ensure_ascii=False),
                 "tool_results_json": json.dumps(run.get("tool_results", []), ensure_ascii=False),
                 "policy_decision_json": json.dumps(run.get("policy_decision"), ensure_ascii=False)}
                for run in conversation["runs"]
            ],
        })
    metadata = {b"dirigent-format": b"conversation-archive-parquet",
                b"dirigent-version": str(SCHEMA_VERSION).encode(),
                b"exported-at": now_utc().encode()}
    return pa.Table.from_pylist(rows, schema=SCHEMA.with_metadata(metadata))


def _decode_rows(table: pa.Table) -> dict[str, Any]:
    metadata = table.schema.metadata or {}
    if (metadata.get(b"dirigent-format") != b"conversation-archive-parquet"
            or metadata.get(b"dirigent-version") != str(SCHEMA_VERSION).encode()
            or not table.schema.remove_metadata().equals(SCHEMA)):
        raise ValueError("Unsupported Dirigent Parquet archive schema or version")
    conversations = []
    for row in table.to_pylist():
        messages = []
        for message in row["messages"] or []:
            message["metadata"] = json.loads(message.pop("metadata_json"))
            messages.append(message)
        runs = []
        for run in row["runs"] or []:
            for field in ("metadata", "tool_results", "policy_decision"):
                run[field] = json.loads(run.pop(f"{field}_json"))
            runs.append(run)
        conversations.append({
            "id": row["id"], "title": row["title"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "messages": messages, "runs": runs,
        })
    return {"format": "dirigent-conversation-archive", "version": SCHEMA_VERSION,
            "conversations": conversations}


def export_encrypted_parquet(archive: ConversationArchive, passphrase: str) -> bytes:
    """Export a complete archive as one encrypted, portable .dpa file."""
    if len(passphrase) < 12:
        raise ValueError("Archive passphrase must contain at least 12 characters")
    sink = pa.BufferOutputStream()
    pq.write_table(_encode_rows(archive.export_json()), sink, compression="zstd")
    parquet = sink.getvalue().to_pybytes()
    if len(parquet) + len(MAGIC) + SALT_BYTES + NONCE_BYTES + 16 > MAX_FILE_BYTES:
        raise ValueError("Archive exceeds the 128 MB encrypted export limit")
    salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(_password_key(passphrase, salt)).encrypt(nonce, parquet, MAGIC)
    return MAGIC + salt + nonce + ciphertext


def import_encrypted_parquet(archive: ConversationArchive, data: bytes, passphrase: str) -> dict[str, int]:
    """Authenticate, decode, and idempotently merge a .dpa file."""
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Archive exceeds the 128 MB import limit")
    header_size = len(MAGIC) + SALT_BYTES + NONCE_BYTES
    if len(data) < header_size + 16 or not data.startswith(MAGIC):
        raise ValueError("Unsupported or incomplete Dirigent encrypted archive")
    salt = data[len(MAGIC):len(MAGIC) + SALT_BYTES]
    nonce = data[len(MAGIC) + SALT_BYTES:header_size]
    try:
        parquet = AESGCM(_password_key(passphrase, salt)).decrypt(nonce, data[header_size:], MAGIC)
    except InvalidTag as exc:
        raise ValueError("Incorrect passphrase or damaged archive") from exc
    try:
        parquet_file = pq.ParquetFile(pa.BufferReader(parquet))
        if (parquet_file.metadata.num_rows > 100000
                or sum(parquet_file.metadata.row_group(index).total_byte_size
                       for index in range(parquet_file.metadata.num_row_groups)) > MAX_UNCOMPRESSED_BYTES):
            raise ValueError("Archive exceeds the supported decoded size")
        table = parquet_file.read()
        payload = _decode_rows(table)
    except (pa.ArrowException, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Dirigent Parquet archive") from exc
    return archive.import_json(payload)
