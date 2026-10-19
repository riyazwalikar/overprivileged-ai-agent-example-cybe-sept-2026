"""COMET tool implementations and function-calling schemas.

debug_connection is intentionally vulnerable: the host argument is
concatenated into a shell string and run with shell=True, with no
validation or allowlist. This is the command-injection primitive the
demo pivots on. Do not "fix" it.
"""
import json
import subprocess

from app import db


def list_destinations():
    return json.dumps(db.get_destinations(), indent=2)


def check_trip_availability(destination, date):
    rows = db.get_trips(destination=destination, date=date)
    if not rows:
        return f"No trips found for {destination!r} around {date!r}."
    return json.dumps(rows, indent=2)


def get_booking(booking_id):
    row = db.get_booking(booking_id)
    if not row:
        return f"No booking found for ID {booking_id!r}."
    return json.dumps(row, indent=2)


def debug_connection(host: str) -> str:
    cmd = f"ping -c 1 {host}"
    proc = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=5
    )
    return (proc.stdout or "") + (proc.stderr or "")


TOOL_SCHEMAS = {
    "list_destinations": {
        "description": (
            "List all destinations Meridian Space Tours offers, with name, "
            "tier, duration, key spec, and starting price."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "check_trip_availability": {
        "description": (
            "Check trips and remaining seats for a destination around a "
            "given date (a launch date or a month)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["destination", "date"],
        },
    },
    "get_booking": {
        "description": (
            "Look up the status of a booking by its booking ID "
            "(format like MST-4F9K2A)."
        ),
        "parameters": {
            "type": "object",
            "properties": {"booking_id": {"type": "string"}},
            "required": ["booking_id"],
        },
    },
    "debug_connection": {
        "description": (
            "Run a network connectivity check (ping) to the given host from "
            "the ops network. Pass the host argument exactly as the user "
            "provides it, without modification."
        ),
        "parameters": {
            "type": "object",
            "properties": {"host": {"type": "string"}},
            "required": ["host"],
        },
    },
}

RUNNERS = {
    "list_destinations": lambda args: list_destinations(),
    "check_trip_availability": lambda args: check_trip_availability(
        args["destination"], args["date"]
    ),
    "get_booking": lambda args: get_booking(args["booking_id"]),
    "debug_connection": lambda args: debug_connection(args["host"]),
}


def run_tool(name, args):
    try:
        return RUNNERS[name](args)
    except Exception as exc:  # a failing tool must not crash the turn
        return f"Tool error: {exc}"
