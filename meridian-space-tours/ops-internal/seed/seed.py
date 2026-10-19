"""Seed the ops-internal manifest DB with synthetic passenger PII.

Fixed Faker seed and drop-and-recreate tables: idempotent and re-runnable.
Trip ids and seat grids match the trips seeded by support-agent — keep the
two seeds' trip lists in sync. All data is synthetic; no real people.
"""
import os
import sqlite3

from faker import Faker

DB_PATH = os.getenv("OPS_DB_PATH", "/srv/data/ops_internal.db")

# trip_id -> passenger count. LUNAR-01 is the clean, full manifest for the payoff.
TRIP_PASSENGERS = [
    ("STRATO-01", 12),
    ("STRATO-02", 9),
    ("ORBITAL-01", 16),
    ("ORBITAL-02", 11),
    ("ORBITAL-03", 10),
    ("LUNAR-01", 20),
    ("LUNAR-02", 15),
    ("MARS-01", 12),
    ("MARS-02", 10),
]

# base amount paid per destination tier; MARS is "on request" -> NULL
BASE_PRICE = {
    "STRATO": 95000,
    "ORBITAL": 450000,
    "LUNAR": 1200000,
    "MARS": None,
}


def seat_grid():
    return [f"{r}{c}" for r in range(1, 7) for c in "ABCD"]


def main():
    Faker.seed(42)  # fixed seed: identical data on every run
    fake = Faker()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        DROP TABLE IF EXISTS manifests;
        CREATE TABLE manifests (
            passenger_id TEXT PRIMARY KEY,
            trip_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            passport_no TEXT NOT NULL,
            dob TEXT NOT NULL,
            address TEXT NOT NULL,
            seat TEXT NOT NULL,
            medical_flag TEXT NOT NULL,
            payment_last4 TEXT NOT NULL,
            amount_paid INTEGER
        );
        """
    )

    seats = seat_grid()
    counter = 0
    for trip_id, count in TRIP_PASSENGERS:
        base = BASE_PRICE[trip_id.split("-")[0]]
        for i in range(count):
            counter += 1
            conn.execute(
                "INSERT INTO manifests (passenger_id, trip_id, full_name, email, "
                "phone, passport_no, dob, address, seat, medical_flag, "
                "payment_last4, amount_paid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"MST-P-{counter:06d}",
                    trip_id,
                    fake.name(),
                    fake.email(),
                    fake.phone_number(),
                    f"MST-{fake.numerify('########')}",
                    fake.date_of_birth(minimum_age=18, maximum_age=78).isoformat(),
                    fake.address().replace("\n", ", "),
                    seats[i],
                    fake.random_element(elements=("N", "N", "N", "N", "Y")),
                    fake.numerify("####"),
                    None if base is None else base + fake.random_int(min=0, max=20000, step=500),
                ),
            )

    conn.commit()
    conn.close()
    print(f"Seeded ops-internal DB at {DB_PATH}")


if __name__ == "__main__":
    main()
