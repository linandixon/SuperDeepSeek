import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "evidence.sqlite3"


class EvidenceStore:
    def __init__(self, path: Path = DB_PATH, retention_days: int = 14):
        self.path = path
        self.retention_days = retention_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()
        self.prune()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with closing(self._connect()) as db, db:
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

    def prune(self) -> None:
        if not self.retention_days:
            return
        cutoff = int(time.time()) - self.retention_days * 86400
        with closing(self._connect()) as db, db:
            db.execute("delete from evidence where created_at < ?", (cutoff,))

    def put_many(self, packets: List[dict]) -> None:
        with closing(self._connect()) as db, db:
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

    def get_by_hashes(self, source_hashes: List[str]) -> Dict[str, dict]:
        """Return {source_hash: evidence_packet} for images already analyzed (content-addressed, cross-session).

        Observations are produced at temperature=0, so the same image always yields the same result.
        Sharing the cache across sessions saves vision worker calls without leaking session context.
        """
        if not source_hashes:
            return {}
        with closing(self._connect()) as db:
            placeholders = ",".join("?" for _ in source_hashes)
            rows = db.execute(
                f"select source_hash, packet_json from evidence where source_hash in ({placeholders}) order by created_at desc",
                tuple(source_hashes),
            ).fetchall()
        result: Dict[str, dict] = {}
        for row in rows:
            if row[0] not in result:
                result[row[0]] = json.loads(row[1])
        return result

    def recent(self, session_key: str, limit: int = 5) -> List[dict]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "select packet_json from evidence where session_key = ? order by created_at desc limit ?",
                (session_key, limit),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
