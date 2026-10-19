"""Seed the support-agent DB (destinations, trips, bookings).

Fixed Faker seed and drop-and-recreate tables: idempotent and re-runnable.
Destinations are the real catalog from marketing.meridianspacetours.com.
"""
import os
import sqlite3

from faker import Faker

DB_PATH = os.getenv("SUPPORT_DB_PATH", "/srv/data/support_agent.db")

DESTINATIONS = [
    # (name, tier, duration, key_spec, price_from)
    ("Stratosphere", "Suborbital", "90 minutes", "100 km (Kármán line)", 95000),
    ("Orbital Horizon", "Low Earth Orbit", "3 days", "400 km", 450000),
    ("Lunar Passage", "Cislunar", "7 days", "384,400 km", 1200000),
    ("Mars Flyby", "Deep Space", "500 days", "225M km", None),  # price on request
]

TRIPS = [
    # (id, destination, launch_date, seats_total, seats_remaining)
    # seats_remaining = seats_total - manifest passengers (see ops-internal seed)
    ("STRATO-01", "Stratosphere", "2026-09-18", 12, 0),
    ("STRATO-02", "Stratosphere", "2026-10-09", 12, 3),
    ("ORBITAL-01", "Orbital Horizon", "2026-09-25", 16, 0),
    ("ORBITAL-02", "Orbital Horizon", "2026-11-14", 16, 5),
    ("ORBITAL-03", "Orbital Horizon", "2027-01-22", 16, 6),
    ("LUNAR-01", "Lunar Passage", "2026-10-02", 20, 0),
    ("LUNAR-02", "Lunar Passage", "2027-02-06", 20, 5),
    ("MARS-01", "Mars Flyby", "2027-04-15", 14, 2),
    ("MARS-02", "Mars Flyby", "2027-09-30", 14, 4),
]

BOOKINGS = [
    # (booking_id, trip_id, status, seat)
    # Seats overlap the manifest rows seeded by ops-internal.
    ("MST-4F9K2A", "LUNAR-01", "Confirmed", "1A"),
    ("MST-8T2XQ7", "ORBITAL-01", "Confirmed", "3B"),
    ("MST-1P6RD3", "STRATO-01", "Pending", "2C"),
    ("MST-5N8WL9", "LUNAR-01", "Confirmed", "4A"),
    ("MST-9C3VH6", "ORBITAL-02", "Scrubbed", "1D"),
    ("MST-2J7YM4", "STRATO-02", "Confirmed", "3A"),
]


def main():
    Faker.seed(42)  # fixed seed: identical data on every run
    fake = Faker()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        DROP TABLE IF EXISTS bookings;
        DROP TABLE IF EXISTS trips;
        DROP TABLE IF EXISTS destinations;
        CREATE TABLE destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tier TEXT NOT NULL,
            duration TEXT NOT NULL,
            key_spec TEXT NOT NULL,
            price_from INTEGER
        );
        CREATE TABLE trips (
            id TEXT PRIMARY KEY,
            destination_id INTEGER NOT NULL,
            launch_date TEXT NOT NULL,
            vehicle TEXT NOT NULL,
            seats_total INTEGER NOT NULL,
            seats_remaining INTEGER NOT NULL
        );
        CREATE TABLE bookings (
            booking_id TEXT PRIMARY KEY,
            trip_id TEXT NOT NULL,
            status TEXT NOT NULL,
            passenger_first_name TEXT NOT NULL,
            seat TEXT NOT NULL
        );
        """
    )

    for name, tier, duration, spec, price in DESTINATIONS:
        conn.execute(
            "INSERT INTO destinations (name, tier, duration, key_spec, price_from) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, tier, duration, spec, price),
        )

    for trip_id, dest, date, total, remaining in TRIPS:
        conn.execute(
            "INSERT INTO trips (id, destination_id, launch_date, vehicle, "
            "seats_total, seats_remaining) "
            "VALUES (?, (SELECT id FROM destinations WHERE name = ?), ?, "
            "'Meridian Voyager', ?, ?)",
            (trip_id, dest, date, total, remaining),
        )

    for booking_id, trip_id, status, seat in BOOKINGS:
        conn.execute(
            "INSERT INTO bookings (booking_id, trip_id, status, "
            "passenger_first_name, seat) VALUES (?, ?, ?, ?, ?)",
            (booking_id, trip_id, status, fake.first_name(), seat),
        )

    conn.commit()
    conn.close()
    print(f"Seeded support-agent DB at {DB_PATH}")


if __name__ == "__main__":
    main()
