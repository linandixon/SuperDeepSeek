import json
import sqlite3
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "evidence.sqlite3"


class EvidenceStore:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                create table if not exists evidence (
                  id text primary key,
                  session_key text not null,
                  created_at integer not null,
                  packet_json text not null
                )
                """
            )

    def put_many(self, packets: List[dict]) -> None:
        with self._connect() as db:
            for packet in packets:
                db.execute(
                    "insert or replace into evidence values (?, ?, ?, ?)",
                    (
                        packet["id"],
                        packet.get("session_key", "default"),
                        int(packet.get("created_at", 0)),
                        json.dumps(packet, ensure_ascii=False),
                    ),
                )

    def recent(self, session_key: str, limit: int = 5) -> List[dict]:
        with self._connect() as db:
            rows = db.execute(
                "select packet_json from evidence where session_key = ? order by created_at desc limit ?",
                (session_key, limit),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
