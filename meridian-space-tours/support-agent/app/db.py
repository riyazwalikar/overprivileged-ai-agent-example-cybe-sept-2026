"""Read helpers for the support-agent SQLite DB (destinations, trips, bookings)."""
import os
import sqlite3

DB_PATH = os.getenv("SUPPORT_DB_PATH", "/srv/data/support_agent.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_destinations():
    with _conn() as conn:
        rows = conn.execute(
            "SELECT name, tier, duration, key_spec, price_from "
            "FROM destinations ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def get_trips(destination=None, date=None):
    sql = (
        "SELECT t.id, d.name AS destination, t.launch_date, t.vehicle, "
        "t.seats_total, t.seats_remaining "
        "FROM trips t JOIN destinations d ON d.id = t.destination_id WHERE 1=1"
    )
    params = []
    if destination:
        sql += " AND d.name LIKE ?"
        params.append(f"%{destination}%")
    if date:
        sql += " AND t.launch_date LIKE ?"
        params.append(f"%{date}%")
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_booking(booking_id):
    with _conn() as conn:
        row = conn.execute(
            "SELECT booking_id, trip_id, status, passenger_first_name, seat "
            "FROM bookings WHERE booking_id = ?",
            (booking_id,),
        ).fetchone()
        return dict(row) if row else None
