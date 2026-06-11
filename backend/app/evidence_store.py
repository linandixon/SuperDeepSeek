import json
import sqlite3
from pathlib import Path
from typing import Dict, List


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
            try:
                db.execute("alter table evidence add column source_hash text default ''")
            except sqlite3.OperationalError:
                pass
            db.execute("create index if not exists idx_evidence_session_hash on evidence(session_key, source_hash)")

    def put_many(self, packets: List[dict]) -> None:
        with self._connect() as db:
            for packet in packets:
                db.execute(
                    "insert or replace into evidence (id, session_key, created_at, packet_json, source_hash) values (?, ?, ?, ?, ?)",
                    (
                        packet["id"],
                        packet.get("session_key", "default"),
                        int(packet.get("created_at", 0)),
                        json.dumps(packet, ensure_ascii=False),
                        packet.get("source_hash", ""),
                    ),
                )

    def get_by_hashes(self, session_key: str, source_hashes: List[str]) -> Dict[str, dict]:
        """Return {source_hash: evidence_packet} for images already analyzed in this session."""
        if not source_hashes:
            return {}
        with self._connect() as db:
            placeholders = ",".join("?" for _ in source_hashes)
            rows = db.execute(
                f"select source_hash, packet_json from evidence where session_key = ? and source_hash in ({placeholders}) order by created_at desc",
                (session_key, *source_hashes),
            ).fetchall()
        result: Dict[str, dict] = {}
        for row in rows:
            if row[0] not in result:
                result[row[0]] = json.loads(row[1])
        return result

    def recent(self, session_key: str, limit: int = 5) -> List[dict]:
        with self._connect() as db:
            rows = db.execute(
                "select packet_json from evidence where session_key = ? order by created_at desc limit ?",
                (session_key, limit),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
