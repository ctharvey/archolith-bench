#!/usr/bin/env python3
"""Python CLI Kanban board manager — single-file, JSON-persisted."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

STATE_FILE = Path(__file__).resolve().parent / "kanban.json"

PRIORITIES = {"low", "med", "high"}
COLUMNS = {"todo", "doing", "done"}


def _load() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open("r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: corrupt state file — {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        print("error: state file is not a valid object", file=sys.stderr)
        sys.exit(1)
    return data


def _save(state: dict[str, Any]) -> None:
    try:
        with STATE_FILE.open("w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        print(f"error: cannot write state — {e}", file=sys.stderr)
        sys.exit(1)


def _get_board(state: dict[str, Any], name: str) -> dict[str, Any] | None:
    return state.get(name)


def _require_board(state: dict[str, Any], name: str) -> dict[str, Any]:
    board = _get_board(state, name)
    if board is None:
        print(f"error: board '{name}' not found", file=sys.stderr)
        sys.exit(1)
    return board


def _next_id(board: dict[str, Any]) -> int:
    ids = set()
    for col in COLUMNS:
        for c in board.get(col, []):
            ids.add(c["id"])
    return (max(ids) + 1) if ids else 1


def cmd_create_board(args: argparse.Namespace) -> None:
    state = _load()
    name = args.name
    if name in state:
        print(f"error: board '{name}' already exists", file=sys.stderr)
        sys.exit(1)
    state[name] = {"todo": [], "doing": [], "done": []}
    _save(state)
    print(f"created board: {name}")


def cmd_list_boards(_: argparse.Namespace) -> None:
    state = _load()
    if not state:
        print("no boards")
        return
    for name in state:
        print(name)


def cmd_add_card(args: argparse.Namespace) -> None:
    state = _load()
    board = _require_board(state, args.board)
    priority = args.priority.lower()
    if priority not in PRIORITIES:
        print(f"error: invalid priority '{args.priority}' — use low/med/high", file=sys.stderr)
        sys.exit(1)
    card = {"id": _next_id(board), "title": args.title, "description": args.description or "", "priority": priority}
    board["todo"].append(card)
    _save(state)
    print(f"added card #{card['id']} to {args.board}/todo")


def cmd_move(args: argparse.Namespace) -> None:
    state = _load()
    board = _require_board(state, args.board)
    target_col = args.to.lower()
    if target_col not in COLUMNS:
        print(f"error: invalid column '{args.to}' — use todo/doing/done", file=sys.stderr)
        sys.exit(1)
    card_id = args.card_id
    found: dict | None = None
    for col in COLUMNS:
        for c in board.get(col, []):
            if c["id"] == card_id:
                found = c
                break
        if found:
            break
    if found is None:
        print(f"error: card #{card_id} not found on board '{args.board}'", file=sys.stderr)
        sys.exit(1)
    for col in COLUMNS:
        board[col] = [c for c in board.get(col, []) if c["id"] != card_id]
    board.setdefault(target_col, []).append(found)
    _save(state)
    print(f"moved card #{card_id} to {args.board}/{target_col}")


def cmd_list(args: argparse.Namespace) -> None:
    state = _load()
    board = _require_board(state, args.board)
    print(f"Board: {args.board}")
    for col in ("todo", "doing", "done"):
        cards = board.get(col, [])
        if not cards:
            print(f"  {col}: (empty)")
            continue
        print(f"  {col}:")
        for c in cards:
            print(f"    [#{c['id']}] {c['title']} ({c['priority']})")
            if c.get("description"):
                print(f"      {c['description']}")


def cmd_delete(args: argparse.Namespace) -> None:
    state = _load()
    board = _require_board(state, args.board)
    card_id = args.card_id
    found = False
    for col in COLUMNS:
        before = len(board.get(col, []))
        board[col] = [c for c in board.get(col, []) if c["id"] != card_id]
        if len(board[col]) < before:
            found = True
    if not found:
        print(f"error: card #{card_id} not found on board '{args.board}'", file=sys.stderr)
        sys.exit(1)
    _save(state)
    print(f"deleted card #{card_id}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="kanban", description="Kanban board manager")
    sub = parser.add_subparsers(dest="command", required=True)

    # create-board
    p = sub.add_parser("create-board", help="Create a new board")
    p.add_argument("name", help="Board name")
    p.set_defaults(func=cmd_create_board)

    # list-boards
    p = sub.add_parser("list-boards", help="List all boards")
    p.set_defaults(func=cmd_list_boards)

    # add-card
    p = sub.add_parser("add-card", help="Add a card to a board's todo column")
    p.add_argument("board", help="Board name")
    p.add_argument("title", help="Card title")
    p.add_argument("--description", "-d", default="", help="Card description")
    p.add_argument("--priority", "-p", default="med", choices=list(PRIORITIES), help="Card priority")
    p.set_defaults(func=cmd_add_card)

    # move
    p = sub.add_parser("move", help="Move a card between columns")
    p.add_argument("board", help="Board name")
    p.add_argument("card_id", type=int, help="Card ID")
    p.add_argument("to", choices=list(COLUMNS), help="Target column")
    p.set_defaults(func=cmd_move)

    # list
    p = sub.add_parser("list", help="List a board's cards")
    p.add_argument("board", help="Board name")
    p.set_defaults(func=cmd_list)

    # delete
    p = sub.add_parser("delete", help="Delete a card")
    p.add_argument("board", help="Board name")
    p.add_argument("card_id", type=int, help="Card ID")
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()