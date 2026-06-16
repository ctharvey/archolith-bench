#!/usr/bin/env python3
"""kanban.py — a single-file Python CLI Kanban app."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kanban.json")

BOARDS_DEFAULT: dict[str, Any] = {}
VALID_PRIORITIES = {"low", "med", "high"}
VALID_COLUMNS = {"todo", "doing", "done"}


@dataclass
class Card:
    title: str
    description: str
    priority: str  # low/med/high
    column: str = "todo"  # todo/doing/done


@dataclass
class Board:
    name: str
    cards: list[Card] = field(default_factory=list)


def _load() -> dict[str, Board]:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: corrupt or unreadable kanban.json: {e}", file=sys.stderr)
        sys.exit(1)
    boards: dict[str, Board] = {}
    for name, data in raw.items():
        boards[name] = Board(
            name=name,
            cards=[Card(**c) for c in data.get("cards", [])],
        )
    return boards


def _save(boards: dict[str, Board]) -> None:
    raw: dict[str, Any] = {}
    for name, board in boards.items():
        raw[name] = {"cards": [asdict(c) for c in board.cards]}
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(raw, f, indent=2)
    except OSError as e:
        print(f"error: could not write {DATA_FILE}: {e}", file=sys.stderr)
        sys.exit(1)


def _get_board(boards: dict[str, Board], name: str) -> Board:
    if name not in boards:
        print(f"error: board '{name}' not found", file=sys.stderr)
        sys.exit(1)
    return boards[name]


def _get_card(board: Board, title: str) -> Card:
    for c in board.cards:
        if c.title == title:
            return c
    print(f"error: card '{title}' not found in board '{board.name}'", file=sys.stderr)
    sys.exit(1)


# ---- subcommands ------------------------------------------------------------

def cmd_create_board(args: argparse.Namespace, boards: dict[str, Board]) -> None:
    name = args.name
    if name in boards:
        print(f"error: board '{name}' already exists", file=sys.stderr)
        sys.exit(1)
    boards[name] = Board(name=name)
    _save(boards)
    print(f"created board '{name}'")


def cmd_list_boards(args: argparse.Namespace, boards: dict[str, Board]) -> None:
    if not boards:
        print("no boards")
        return
    for name in boards:
        print(name)


def cmd_add_card(args: argparse.Namespace, boards: dict[str, Board]) -> None:
    board = _get_board(boards, args.board)
    if args.priority not in VALID_PRIORITIES:
        print(f"error: invalid priority '{args.priority}' (choose from {sorted(VALID_PRIORITIES)})", file=sys.stderr)
        sys.exit(1)
    for c in board.cards:
        if c.title == args.title:
            print(f"error: card '{args.title}' already exists in board '{args.board}'", file=sys.stderr)
            sys.exit(1)
    board.cards.append(Card(title=args.title, description=args.description, priority=args.priority))
    _save(boards)
    print(f"added card '{args.title}' to '{args.board}'")


def cmd_move(args: argparse.Namespace, boards: dict[str, Board]) -> None:
    board = _get_board(boards, args.board)
    card = _get_card(board, args.title)
    if args.to not in VALID_COLUMNS:
        print(f"error: invalid column '{args.to}' (choose from {sorted(VALID_COLUMNS)})", file=sys.stderr)
        sys.exit(1)
    card.column = args.to
    _save(boards)
    print(f"moved '{args.title}' to '{args.to}'")


def cmd_list(args: argparse.Namespace, boards: dict[str, Board]) -> None:
    board = _get_board(boards, args.board)
    if not board.cards:
        print(f"board '{args.board}' is empty")
        return
    for c in board.cards:
        print(f"  [{c.priority:>4}] {c.title:<20} ({c.column})  {c.description}")


def cmd_delete(args: argparse.Namespace, boards: dict[str, Board]) -> None:
    board = _get_board(boards, args.board)
    card = _get_card(board, args.title)
    board.cards.remove(card)
    _save(boards)
    print(f"deleted card '{args.title}' from '{args.board}'")


# ---- argparse ---------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kanban", description="CLI Kanban board manager")
    subs = p.add_subparsers(title="subcommands", dest="command", required=True)

    sp = subs.add_parser("create-board", help="create a new board")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_create_board)

    sp = subs.add_parser("list-boards", help="list all boards")
    sp.set_defaults(func=cmd_list_boards)

    sp = subs.add_parser("add-card", help="add a card to a board")
    sp.add_argument("board")
    sp.add_argument("title")
    sp.add_argument("description")
    sp.add_argument("priority", choices=sorted(VALID_PRIORITIES))
    sp.set_defaults(func=cmd_add_card)

    sp = subs.add_parser("move", help="move a card between columns")
    sp.add_argument("board")
    sp.add_argument("title")
    sp.add_argument("to", choices=sorted(VALID_COLUMNS))
    sp.set_defaults(func=cmd_move)

    sp = subs.add_parser("list", help="list a board's cards")
    sp.add_argument("board")
    sp.set_defaults(func=cmd_list)

    sp = subs.add_parser("delete", help="delete a card")
    sp.add_argument("board")
    sp.add_argument("title")
    sp.set_defaults(func=cmd_delete)

    return p


def main() -> None:
    boards = _load()
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args, boards)


if __name__ == "__main__":
    main()