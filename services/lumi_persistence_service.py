"""Bounded, user-scoped persistence for Lumi conversations and memories."""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from datetime import datetime, timezone

from database.connection import DatabaseConnection, get_connection

MAX_MESSAGE_CHARS = 2_000
MAX_TITLE_CHARS = 160
MAX_CONTEXT_MESSAGES = 12
MAX_CONTEXT_CHARS = 12_000
MAX_MEMORY_CHARS = 600
MAX_MEMORIES = 50
MEMORY_CATEGORIES = {"preference", "goal", "personal_context"}


class LumiPersistenceError(ValueError):
    pass


def _clean(value: str, limit: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > limit:
        raise LumiPersistenceError("Conteúdo fora dos limites permitidos.")
    return normalized


def _title(content: str) -> str:
    compact = " ".join(content.split())
    return compact[:MAX_TITLE_CHARS].rstrip() or "Conversa com a Lumi"


def _fingerprint(content: str, category: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", content).casefold().split())
    return hashlib.sha256(f"{category}:{normalized}".encode("utf-8")).hexdigest()


def _conversation_row(row: tuple) -> dict:
    return {"id": str(row[0]), "title": row[1], "created_at": str(row[2]), "updated_at": str(row[3])}


def create_conversation(usuario_id: int, first_message: str | None = None) -> dict:
    title = _title(first_message) if first_message else "Nova conversa"
    public_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute("INSERT INTO lumi_conversations (public_id, usuario_id, titulo) VALUES (?, ?, ?)", (public_id, usuario_id, title))
        row = conn.execute("SELECT public_id, titulo, criada_em, atualizada_em FROM lumi_conversations WHERE public_id = ? AND usuario_id = ?", (public_id, usuario_id)).fetchone()
        conn.commit()
        return _conversation_row(row)
    finally:
        conn.close()


def _conversation_id(conn: DatabaseConnection, usuario_id: int, public_id: str) -> int:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", public_id):
        raise LumiPersistenceError("Conversa não encontrada.")
    row = conn.execute("SELECT id FROM lumi_conversations WHERE public_id = ? AND usuario_id = ?", (public_id, usuario_id)).fetchone()
    if row is None:
        raise LumiPersistenceError("Conversa não encontrada.")
    return int(row[0])


def get_conversation(usuario_id: int, public_id: str) -> dict:
    conn = get_connection()
    try:
        conversation_id = _conversation_id(conn, usuario_id, public_id)
        row = conn.execute("SELECT public_id, titulo, criada_em, atualizada_em FROM lumi_conversations WHERE id = ?", (conversation_id,)).fetchone()
        messages = conn.execute("SELECT role, content, status, criada_em FROM lumi_messages WHERE conversation_id = ? ORDER BY criada_em, id", (conversation_id,)).fetchall()
        result = _conversation_row(row)
        result["messages"] = [{"role": item[0], "content": item[1], "status": item[2], "created_at": str(item[3])} for item in messages]
        return result
    finally:
        conn.close()


def list_conversations(usuario_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT public_id, titulo, criada_em, atualizada_em FROM lumi_conversations WHERE usuario_id = ? ORDER BY atualizada_em DESC, id DESC LIMIT 100", (usuario_id,)).fetchall()
        return [_conversation_row(row) for row in rows]
    finally:
        conn.close()


def delete_conversation(usuario_id: int, public_id: str) -> bool:
    conn = get_connection()
    try:
        conversation_id = _conversation_id(conn, usuario_id, public_id)
        deleted = conn.execute("DELETE FROM lumi_conversations WHERE id = ? AND usuario_id = ?", (conversation_id, usuario_id)).rowcount == 1
        conn.commit()
        return deleted
    finally:
        conn.close()


def clear_history(usuario_id: int) -> int:
    conn = get_connection()
    try:
        result = conn.execute("DELETE FROM lumi_conversations WHERE usuario_id = ?", (usuario_id,))
        conn.commit()
        return result.rowcount
    finally:
        conn.close()


def load_context(conn: DatabaseConnection, usuario_id: int, public_id: str) -> tuple[int, list[dict[str, str]]]:
    conversation_id = _conversation_id(conn, usuario_id, public_id)
    rows = conn.execute("SELECT role, content FROM lumi_messages WHERE conversation_id = ? AND status = 'completed' ORDER BY criada_em DESC, id DESC LIMIT ?", (conversation_id, MAX_CONTEXT_MESSAGES)).fetchall()
    rows.reverse()
    selected: list[dict[str, str]] = []
    total = 0
    for role, content in rows:
        if total + len(content) > MAX_CONTEXT_CHARS:
            continue
        selected.append({"role": role, "content": content})
        total += len(content)
    return conversation_id, selected


def append_message(conn: DatabaseConnection, conversation_id: int, role: str, content: str, status: str = "completed") -> None:
    if role not in {"user", "assistant"} or status not in {"completed", "failed"}:
        raise LumiPersistenceError("Mensagem inválida.")
    value = _clean(content, MAX_MESSAGE_CHARS)
    conn.execute("INSERT INTO lumi_messages (conversation_id, role, content, status) VALUES (?, ?, ?, ?)", (conversation_id, role, value, status))
    conn.execute("UPDATE lumi_conversations SET atualizada_em = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))


def list_memories(usuario_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT public_id, categoria, conteudo, criada_em, atualizada_em FROM lumi_memories WHERE usuario_id = ? AND ativo = ? ORDER BY atualizada_em DESC, id DESC", (usuario_id, True)).fetchall()
        return [{"id": row[0], "category": row[1], "content": row[2], "created_at": str(row[3]), "updated_at": str(row[4])} for row in rows]
    finally:
        conn.close()


def create_memory(usuario_id: int, category: str, content: str) -> dict:
    if category not in MEMORY_CATEGORIES:
        raise LumiPersistenceError("Categoria de memória inválida.")
    value = _clean(content, MAX_MEMORY_CHARS)
    fingerprint = _fingerprint(value, category)
    conn = get_connection()
    try:
        # Serializa a decisão check/insert por usuário no PostgreSQL. Isso evita
        # que duas requisições idênticas concorrentes disputem a constraint.
        conn.lock_row("usuarios", "id", usuario_id)
        existing = conn.execute("SELECT public_id, categoria, conteudo, criada_em, atualizada_em FROM lumi_memories WHERE usuario_id = ? AND fingerprint = ?", (usuario_id, fingerprint)).fetchone()
        if existing is not None:
            return {"id": existing[0], "category": existing[1], "content": existing[2], "created_at": str(existing[3]), "updated_at": str(existing[4])}
        count = conn.execute("SELECT count(*) FROM lumi_memories WHERE usuario_id = ? AND ativo = ?", (usuario_id, True)).fetchone()[0]
        if int(count) >= MAX_MEMORIES:
            raise LumiPersistenceError("Limite de memórias atingido.")
        public_id = str(uuid.uuid4())
        conn.execute("INSERT INTO lumi_memories (public_id, usuario_id, categoria, conteudo, fingerprint) VALUES (?, ?, ?, ?, ?)", (public_id, usuario_id, category, value, fingerprint))
        row = conn.execute("SELECT public_id, categoria, conteudo, criada_em, atualizada_em FROM lumi_memories WHERE public_id = ?", (public_id,)).fetchone()
        conn.commit()
        return {"id": row[0], "category": row[1], "content": row[2], "created_at": str(row[3]), "updated_at": str(row[4])}
    finally:
        conn.close()


def delete_memory(usuario_id: int, public_id: str) -> bool:
    conn = get_connection()
    try:
        deleted = conn.execute("DELETE FROM lumi_memories WHERE public_id = ? AND usuario_id = ?", (public_id, usuario_id)).rowcount == 1
        conn.commit()
        return deleted
    finally:
        conn.close()


def clear_memories(usuario_id: int) -> int:
    conn = get_connection()
    try:
        result = conn.execute("DELETE FROM lumi_memories WHERE usuario_id = ?", (usuario_id,))
        conn.commit()
        return result.rowcount
    finally:
        conn.close()


def context_memories(conn: DatabaseConnection, usuario_id: int) -> list[str]:
    rows = conn.execute("SELECT categoria, conteudo FROM lumi_memories WHERE usuario_id = ? AND ativo = ? ORDER BY atualizada_em DESC, id DESC LIMIT ?", (usuario_id, True, 12)).fetchall()
    return [f"[{category}] {content}" for category, content in rows]
