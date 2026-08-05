#!/usr/bin/env python3
"""CLI helper for the XCI Kanban API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://app.xci.ro/api/v1"
IN_PROGRESS_TERMS = ("progress", "doing", "active", "started")


class APIError(RuntimeError):
    pass


def request(method: str, path: str, *, args: argparse.Namespace, body: dict[str, Any] | None = None, query: dict[str, Any] | None = None) -> Any:
    base_url = args.base_url.rstrip("/")
    url = f"{base_url}{path}"
    if query:
        clean_query = {k: v for k, v in query.items() if v is not None}
        if clean_query:
            url = f"{url}?{urllib.parse.urlencode(clean_query)}"

    token = args.token or os.environ.get("XCI_API_TOKEN")
    if not token:
        raise APIError("Missing token. Set XCI_API_TOKEN or pass --token.")

    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            payload = resp.read()
            if not payload:
                return {"status": resp.status}
            try:
                return json.loads(payload.decode("utf-8"))
            except json.JSONDecodeError:
                return payload.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise APIError(f"HTTP {exc.code}: {payload or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise APIError(f"Request failed: {exc.reason}") from exc


def compact_item(item: dict[str, Any], fields: list[str]) -> str:
    parts = []
    for field in fields:
        value = item.get(field)
        if value not in (None, ""):
            parts.append(f"{field}={value}")
    return "  ".join(parts)


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def print_items(data: Any, fields: list[str]) -> None:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                print(compact_item(item, fields))
            else:
                print(item)
    elif isinstance(data, dict):
        print(compact_item(data, fields))
    else:
        print(data)


def list_boards(args: argparse.Namespace) -> Any:
    return request("GET", "/boards", args=args)


def list_columns(args: argparse.Namespace) -> Any:
    return request("GET", f"/boards/{args.board_id}/columns", args=args)


def list_members(args: argparse.Namespace) -> Any:
    return request("GET", f"/boards/{args.board_id}/members", args=args)


def list_tags(args: argparse.Namespace) -> Any:
    return request("GET", f"/boards/{args.board_id}/tags", args=args)


def list_cards(args: argparse.Namespace) -> Any:
    return request(
        "GET",
        f"/boards/{args.board_id}/cards",
        args=args,
        query={"columnID": getattr(args, "column_id", None)},
    )


def get_card(args: argparse.Namespace) -> Any:
    return request("GET", f"/boards/{args.board_id}/cards/{args.card_id}", args=args)


def create_card(args: argparse.Namespace) -> Any:
    body: dict[str, Any] = {"title": args.title}
    optional = {
        "description": args.description,
        "column_id": args.column_id,
        "assignee_id": args.assignee_id,
    }
    body.update({k: v for k, v in optional.items() if v is not None})
    if args.tag_id:
        body["tag_ids"] = args.tag_id
    return request("POST", f"/boards/{args.board_id}/cards", args=args, body=body)


def update_card(args: argparse.Namespace) -> Any:
    body = {
        "title": args.title,
        "description": args.description,
        "assignee_id": args.assignee_id,
    }
    body = {k: v for k, v in body.items() if v is not None}
    if not body:
        raise APIError("No update fields provided.")
    return request("PUT", f"/boards/{args.board_id}/cards/{args.card_id}", args=args, body=body)


def delete_card(args: argparse.Namespace) -> Any:
    return request("DELETE", f"/boards/{args.board_id}/cards/{args.card_id}", args=args)


def move_card(args: argparse.Namespace) -> Any:
    return request(
        "PATCH",
        f"/boards/{args.board_id}/cards/{args.card_id}/status",
        args=args,
        body={"column_id": args.column_id},
    )


def create_tag(args: argparse.Namespace) -> Any:
    return request("POST", f"/boards/{args.board_id}/tags", args=args, body={"name": args.name, "color": args.color})


def update_tag(args: argparse.Namespace) -> Any:
    body = {"name": args.name, "color": args.color}
    body = {k: v for k, v in body.items() if v is not None}
    if not body:
        raise APIError("No update fields provided.")
    return request("PUT", f"/boards/{args.board_id}/tags/{args.tag_id}", args=args, body=body)


def delete_tag(args: argparse.Namespace) -> Any:
    return request("DELETE", f"/boards/{args.board_id}/tags/{args.tag_id}", args=args)


def assign_tag(args: argparse.Namespace) -> Any:
    return request(
        "POST",
        f"/boards/{args.board_id}/cards/{args.card_id}/tags",
        args=args,
        body={"tag_id": args.tag_id},
    )


def remove_tag(args: argparse.Namespace) -> Any:
    return request("DELETE", f"/boards/{args.board_id}/cards/{args.card_id}/tags/{args.tag_id}", args=args)


def show_board(args: argparse.Namespace) -> dict[str, Any]:
    columns = list_columns(args)
    cards = list_cards(args)
    return {"columns": columns, "cards": cards}


def show_in_progress(args: argparse.Namespace) -> dict[str, Any]:
    columns = list_columns(args)
    matches = [
        col for col in columns
        if any(term in str(col.get("name", "")).lower() for term in IN_PROGRESS_TERMS)
    ]
    if not matches:
        return {
            "available_columns": columns,
            "matched_columns": [],
            "cards": [],
            "message": "No in-progress-like column name found.",
        }

    cards = []
    for col in matches:
        col_cards = request("GET", f"/boards/{args.board_id}/cards", args=args, query={"columnID": col.get("id")})
        cards.extend({"column": col, "card": card} for card in col_cards)
    return {"matched_columns": matches, "cards": cards}


def print_result(args: argparse.Namespace, data: Any) -> None:
    if args.raw:
        print_json(data)
        return

    command = args.command
    if command == "list-boards":
        print_items(data, ["id", "name", "organization_id"])
    elif command == "list-columns":
        print_items(data, ["id", "name", "position"])
    elif command == "list-members":
        print_items(data, ["id", "user_id", "full_name", "email", "role"])
    elif command == "list-tags":
        print_items(data, ["id", "name", "color"])
    elif command in ("list-cards", "get-card", "create-card", "update-card", "move-card", "delete-card"):
        print_items(data, ["id", "number", "title", "board_column_id", "assignee_name", "due_date"])
    elif command in ("create-tag", "update-tag", "delete-tag"):
        print_items(data, ["id", "name", "color"])
    elif command in ("assign-tag", "remove-tag"):
        print_items(data, ["id", "number", "title", "board_column_id"])
    elif command == "show-board":
        print("Columns:")
        print_items(data["columns"], ["id", "name", "position"])
        print("\nCards:")
        print_items(data["cards"], ["id", "number", "title", "board_column_id", "assignee_name"])
    elif command == "show-in-progress":
        if data.get("message"):
            print(data["message"])
            print("Available columns:")
            print_items(data["available_columns"], ["id", "name", "position"])
            return
        for item in data["cards"]:
            col = item["column"]
            card = item["card"]
            print(f"column={col.get('name')}({col.get('id')})  {compact_item(card, ['id', 'number', 'title', 'assignee_name', 'due_date'])}")
    else:
        print_json(data)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=os.environ.get("XCI_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--token", default=None, help="Bearer JWT. Defaults to XCI_API_TOKEN.")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--raw", action="store_true", help="Print raw JSON.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the XCI Kanban API.")
    add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-boards").set_defaults(func=list_boards)

    for name, func in (
        ("list-columns", list_columns),
        ("list-members", list_members),
        ("list-tags", list_tags),
        ("list-cards", list_cards),
        ("show-board", show_board),
        ("show-in-progress", show_in_progress),
    ):
        p = sub.add_parser(name)
        p.add_argument("--board-id", type=int, required=True)
        if name == "list-cards":
            p.add_argument("--column-id", type=int)
        p.set_defaults(func=func)

    p = sub.add_parser("get-card")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--card-id", type=int, required=True)
    p.set_defaults(func=get_card)

    p = sub.add_parser("create-card")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description")
    p.add_argument("--column-id", type=int)
    p.add_argument("--assignee-id", type=int)
    p.add_argument("--tag-id", type=int, action="append")
    p.set_defaults(func=create_card)

    p = sub.add_parser("update-card")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--card-id", type=int, required=True)
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--assignee-id", type=int)
    p.set_defaults(func=update_card)

    p = sub.add_parser("delete-card")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--card-id", type=int, required=True)
    p.set_defaults(func=delete_card)

    p = sub.add_parser("move-card")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--card-id", type=int, required=True)
    p.add_argument("--column-id", type=int, required=True)
    p.set_defaults(func=move_card)

    p = sub.add_parser("create-tag")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--color", required=True)
    p.set_defaults(func=create_tag)

    p = sub.add_parser("update-tag")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--tag-id", type=int, required=True)
    p.add_argument("--name")
    p.add_argument("--color")
    p.set_defaults(func=update_tag)

    p = sub.add_parser("delete-tag")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--tag-id", type=int, required=True)
    p.set_defaults(func=delete_tag)

    p = sub.add_parser("assign-tag")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--card-id", type=int, required=True)
    p.add_argument("--tag-id", type=int, required=True)
    p.set_defaults(func=assign_tag)

    p = sub.add_parser("remove-tag")
    p.add_argument("--board-id", type=int, required=True)
    p.add_argument("--card-id", type=int, required=True)
    p.add_argument("--tag-id", type=int, required=True)
    p.set_defaults(func=remove_tag)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        data = args.func(args)
        print_result(args, data)
    except APIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
