import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "traces.sqlite3"


class TraceStore:
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
                create table if not exists traces (
                  trace_id text primary key,
                  started_at real not null,
                  ended_at real,
                  client_protocol text,
                  client_name text,
                  incoming_model text,
                  resolved_profile_id text,
                  resolved_role text,
                  upstream_provider_id text,
                  upstream_model text,
                  status text,
                  latency_ms integer,
                  usage_json text,
                  sanitizer_json text,
                  steps_json text,
                  request_json text,
                  response_json text
                )
                """
            )

    def put(self, record: Dict[str, Any]) -> None:
        record = dict(record)
        record.setdefault("started_at", time.time())
        with self._connect() as db:
            db.execute(
                """
                insert or replace into traces values
                (:trace_id, :started_at, :ended_at, :client_protocol, :client_name,
                 :incoming_model, :resolved_profile_id, :resolved_role,
                 :upstream_provider_id, :upstream_model, :status, :latency_ms,
                 :usage_json, :sanitizer_json, :steps_json, :request_json, :response_json)
                """,
                self._row(record),
            )

    def list(self, limit: int = 100) -> List[dict]:
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "select * from traces order by started_at desc limit ?", (limit,)
            ).fetchall()
        return [self._decode(dict(row)) for row in rows]

    def get(self, trace_id: str) -> Optional[dict]:
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("select * from traces where trace_id = ?", (trace_id,)).fetchone()
        return self._decode(dict(row)) if row else None

    def clear(self) -> None:
        with self._connect() as db:
            db.execute("delete from traces")

    def _row(self, record: Dict[str, Any]) -> dict:
        def dumps(key):
            return json.dumps(record.get(key) or {}, ensure_ascii=False)

        return {
            "trace_id": record["trace_id"],
            "started_at": record.get("started_at"),
            "ended_at": record.get("ended_at"),
            "client_protocol": record.get("client_protocol"),
            "client_name": record.get("client_name"),
            "incoming_model": record.get("incoming_model"),
            "resolved_profile_id": record.get("resolved_profile_id"),
            "resolved_role": record.get("resolved_role"),
            "upstream_provider_id": record.get("upstream_provider_id"),
            "upstream_model": record.get("upstream_model"),
            "status": record.get("status"),
            "latency_ms": record.get("latency_ms"),
            "usage_json": dumps("usage"),
            "sanitizer_json": dumps("sanitizer"),
            "steps_json": dumps("steps"),
            "request_json": dumps("request"),
            "response_json": dumps("response"),
        }

    def _decode(self, row: dict) -> dict:
        for src, dst in [
            ("usage_json", "usage"),
            ("sanitizer_json", "sanitizer"),
            ("steps_json", "steps"),
            ("request_json", "request"),
            ("response_json", "response"),
        ]:
            row[dst] = json.loads(row.pop(src) or "{}")
        return row
