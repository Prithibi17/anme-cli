from __future__ import annotations

import sqlite3
from pathlib import Path


class Store:
    """Small local database for watchlist and playback history."""

    def __init__(self) -> None:
        state = Path.home() / ".local" / "state" / "anme-cli"
        state.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(state / "tui.db")
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS watchlist (
                anime_id TEXT PRIMARY KEY, title TEXT NOT NULL,
                progress TEXT NOT NULL DEFAULT '0'
            )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS history (
                anime_id TEXT PRIMARY KEY, title TEXT NOT NULL,
                episode TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'sub',
                watched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS playback_position (
                anime_id TEXT NOT NULL, episode TEXT NOT NULL,
                seconds REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (anime_id, episode)
            )"""
        )
        history_columns = {
            row[1] for row in self.db.execute("PRAGMA table_info(history)").fetchall()
        }
        if "mode" not in history_columns:
            self.db.execute(
                "ALTER TABLE history ADD COLUMN mode TEXT NOT NULL DEFAULT 'sub'"
            )
        self.db.commit()

    def add_watchlist(self, anime_id: str, title: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO watchlist(anime_id, title) VALUES (?, ?)",
            (anime_id, title),
        )
        self.db.commit()

    def remove_watchlist(self, anime_id: str) -> None:
        self.db.execute("DELETE FROM watchlist WHERE anime_id = ?", (anime_id,))
        self.db.commit()

    def update_progress(self, anime_id: str, episode: str) -> None:
        self.db.execute(
            "UPDATE watchlist SET progress = ? WHERE anime_id = ?",
            (episode, anime_id),
        )
        self.db.commit()

    def watchlist(self) -> list[tuple[str, str, str]]:
        return self.db.execute(
            "SELECT anime_id, title, progress FROM watchlist ORDER BY title"
        ).fetchall()

    def add_history(self, anime_id: str, title: str, episode: str, mode: str) -> None:
        self.db.execute(
            """INSERT INTO history(anime_id, title, episode, mode) VALUES (?, ?, ?, ?)
            ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title,
            episode=excluded.episode, mode=excluded.mode, watched_at=CURRENT_TIMESTAMP""",
            (anime_id, title, episode, mode),
        )
        self.db.commit()

    def history(self) -> list[tuple[str, str, str, str, str]]:
        return self.db.execute(
            "SELECT anime_id, title, episode, mode, watched_at FROM history ORDER BY watched_at DESC"
        ).fetchall()

    def remove_history(self, anime_id: str) -> None:
        self.db.execute("DELETE FROM history WHERE anime_id = ?", (anime_id,))
        self.db.commit()

    def clear_history(self) -> None:
        self.db.execute("DELETE FROM history")
        self.db.commit()

    def save_position(self, anime_id: str, episode: str, seconds: float) -> None:
        self.db.execute(
            """INSERT INTO playback_position(anime_id, episode, seconds) VALUES (?, ?, ?)
            ON CONFLICT(anime_id, episode) DO UPDATE SET seconds=excluded.seconds""",
            (anime_id, episode, max(0.0, seconds)),
        )
        self.db.commit()

    def position(self, anime_id: str, episode: str) -> float:
        row = self.db.execute(
            "SELECT seconds FROM playback_position WHERE anime_id = ? AND episode = ?",
            (anime_id, episode),
        ).fetchone()
        return float(row[0]) if row else 0.0
