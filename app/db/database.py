import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

class Database:
    """
    Gerenciador de persistência SQLite para Chat Sessions e Resumos.
    """
    DB_DIR = Path.home() / ".titier" / "db"
    DB_PATH = DB_DIR / "chats.db"

    def __init__(self):
        self.DB_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(str(self.DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            # Tabela de Resumos de PDF
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pdf_summaries (
                    file_hash TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tabela de Sessões de Chat
            # include_other_chats: permite buscar contexto em outras conversas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    color TEXT,
                    pdf_hash TEXT,
                    search_mode TEXT DEFAULT 'local',
                    include_other_chats INTEGER DEFAULT 0,
                    titling_attempted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tabela de Mensagens
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT, -- JSON string
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    # --- Resumos ---
    def save_summary(self, file_hash: str, content: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pdf_summaries (file_hash, content) VALUES (?, ?)",
                (file_hash, content)
            )
            conn.commit()

    def get_summary(self, file_hash: str) -> Optional[str]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT content FROM pdf_summaries WHERE file_hash = ?", (file_hash,)).fetchone()
            return row['content'] if row else None

    # --- Sessões ---
    def save_session(self, session_id: str, title: str, color: Optional[str] = None, 
                     pdf_hash: Optional[str] = None, search_mode: str = 'local', 
                     include_other_chats: bool = False):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO chat_sessions 
                (id, title, color, pdf_hash, search_mode, include_other_chats, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, title, color, pdf_hash, search_mode, 1 if include_other_chats else 0, datetime.now().isoformat()))
            conn.commit()

    def update_session_title(self, session_id: str, title: str, titling_attempted: bool = True):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE chat_sessions SET title = ?, titling_attempted = ?, updated_at = ? WHERE id = ?",
                (title, 1 if titling_attempted else 0, datetime.now().isoformat(), session_id)
            )
            conn.commit()

    def update_session_settings(self, session_id: str, search_mode: Optional[str] = None, 
                                include_other_chats: Optional[bool] = None):
        with self._get_connection() as conn:
            if search_mode is not None:
                conn.execute(
                    "UPDATE chat_sessions SET search_mode = ?, updated_at = ? WHERE id = ?",
                    (search_mode, datetime.now().isoformat(), session_id)
                )
            if include_other_chats is not None:
                conn.execute(
                    "UPDATE chat_sessions SET include_other_chats = ?, updated_at = ? WHERE id = ?",
                    (1 if include_other_chats else 0, datetime.now().isoformat(), session_id)
                )
            conn.commit()

    def get_sessions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC").fetchall()
            return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def delete_session(self, session_id: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            conn.commit()

    def delete_all_sessions(self):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages")
            conn.execute("DELETE FROM chat_sessions")
            conn.commit()

    # --- Mensagens ---
    def add_message(self, session_id: str, role: str, content: str, sources: Optional[List[Dict]] = None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)",
                (session_id, role, content, json.dumps(sources) if sources else None)
            )
            # Atualizar updated_at da sessão
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), session_id)
            )
            conn.commit()

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            ).fetchall()
            messages = []
            for row in rows:
                msg = dict(row)
                if msg['sources']:
                    msg['sources'] = json.loads(msg['sources'])
                messages.append(msg)
            return messages

# Instância global
_db: Optional[Database] = None

def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
