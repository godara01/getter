"""Tiny CLI over the admin API.

    python -m getter_api.admin sessions --status failed
    python -m getter_api.admin session SESSION_ID
    python -m getter_api.admin regrade SESSION_ID
    python -m getter_api.admin delete-user USER_ID
    python -m getter_api.admin audit --action admin.session.view

Environment: GETTER_ADMIN_API_URL (default http://localhost:8100) and either
GETTER_ADMIN_TOKEN (a Clerk session token) or GETTER_ADMIN_EMAIL (dev auth only).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx


def call(method: str, path: str, params: dict[str, Any] | None = None) -> Any:
    headers: dict[str, str] = {}
    if token := os.environ.get("GETTER_ADMIN_TOKEN"):
        headers["authorization"] = f"Bearer {token}"
    elif email := os.environ.get("GETTER_ADMIN_EMAIL"):
        headers["x-dev-user-email"] = email
    base = os.environ.get("GETTER_ADMIN_API_URL", "http://localhost:8100")
    response = httpx.request(
        method,
        base + path,
        params={k: v for k, v in (params or {}).items() if v is not None},
        headers=headers,
        timeout=30,
    )
    if response.status_code >= 400:
        sys.exit(f"error {response.status_code}: {response.text}")
    return response.json()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m getter_api.admin")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("sessions", help="list sessions")
    for name in ("status", "user_id", "template_id", "min_cost_inr", "max_cost_inr"):
        p.add_argument("--" + name.replace("_", "-"), dest=name)
    p.add_argument("--limit", type=int, default=50)
    for name, help_text in (
        ("session", "show a session with transcript and scores (audited)"),
        ("regrade", "grade a session again"),
        ("delete-user", "process a deletion request for a user id"),
    ):
        sub.add_parser(name, help=help_text).add_argument("id")
    p = sub.add_parser("audit", help="view audit log entries")
    for name in ("action", "actor_user_id", "target_type", "target_id"):
        p.add_argument("--" + name.replace("_", "-"), dest=name)
    p.add_argument("--limit", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    values = vars(args)
    match args.command:
        case "sessions":
            keys = ("status", "user_id", "template_id", "min_cost_inr", "max_cost_inr", "limit")
            result = call("GET", "/admin/sessions", {k: values[k] for k in keys})
        case "session":
            result = call("GET", f"/admin/sessions/{args.id}")
        case "regrade":
            result = call("POST", f"/admin/sessions/{args.id}/regrade")
        case "delete-user":
            result = call("POST", f"/admin/users/{args.id}/deletion")
        case _:
            audit_keys = ("action", "actor_user_id", "target_type", "target_id", "limit")
            result = call("GET", "/admin/audit", {k: values[k] for k in audit_keys})
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
