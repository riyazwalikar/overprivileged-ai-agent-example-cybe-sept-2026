"""Read helpers for the ops-internal manifest DB (synthetic passenger PII)."""
import os
import sqlite3

DB_PATH = os.getenv("OPS_DB_PATH", "/srv/data/ops_internal.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_manifest(trip_id=None, query=None):
    sql = "SELECT * FROM manifests WHERE 1=1"
    params = []
    if trip_id:
        sql += " AND trip_id = ?"
        params.append(trip_id)
    if query:
        sql += " AND (full_name LIKE ? OR email LIKE ? OR passenger_id LIKE ?)"
        params += [f"%{query}%"] * 3
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
