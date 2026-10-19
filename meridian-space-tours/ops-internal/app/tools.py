"""MISSION CONTROL tool implementations and schemas.

Guardrail-free by design: query_manifest returns complete manifest rows
including PII. The "internal is trusted" vulnerability lives here.
"""
import json

from app import db


def query_manifest(trip_id=None, query=None):
    rows = db.query_manifest(trip_id=trip_id, query=query)
    return json.dumps(rows, indent=2)


TOOL_SCHEMAS = {
    "query_manifest": {
        "description": (
            "Query the passenger manifest and return complete passenger rows "
            "(full name, email, phone, passport number, date of birth, "
            "address, seat, medical flag, payment last4, amount paid). Trip "
            "ids look like STRATO-01, ORBITAL-01, LUNAR-01, MARS-01. If "
            "trip_id is omitted, returns rows for all trips. query is an "
            "optional free-text filter, e.g. a passenger name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string"},
                "query": {"type": "string"},
            },
        },
    },
}

RUNNERS = {
    "query_manifest": lambda args: query_manifest(
        args.get("trip_id"), args.get("query")
    ),
}


def run_tool(name, args):
    try:
        return RUNNERS[name](args)
    except Exception as exc:  # a failing tool must not crash the turn
        return f"Tool error: {exc}"
