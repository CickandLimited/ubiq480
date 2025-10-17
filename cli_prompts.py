"""Shared helpers for building interactive command-line menus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


class MenuCancelled(RuntimeError):
    """Raised when the user aborts an interactive menu."""


def _normalise_tokens(response: str) -> list[str]:
    separators = {",", " "}
    tokens: list[str] = []
    current = []
    for char in response:
        if char in separators:
            if current:
                tokens.append("".join(current))
                current.clear()
            continue
        current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


@dataclass(frozen=True)
class MenuOption:
    """Represents a selectable entry in an interactive menu."""

    key: str
    label: str


def prompt_for_menu_selection(
    title: str,
    options: Sequence[MenuOption],
    *,
    allow_multiple: bool = False,
    input_func: Callable[[str], str] | None = None,
    print_func: Callable[[str], None] = print,
) -> list[str]:
    """Prompt the user to choose one or more entries from *options*.

    ``allow_multiple`` toggles whether the user can select more than one option in
    a single response.  The helper re-prompts until a valid choice is provided or
    the user aborts the interaction (``q``/``quit``/``exit``) or triggers an EOF.
    ``input_func`` mirrors :func:`input` to aid testing.
    """

    if not options:
        raise ValueError("options must not be empty")

    prompt_input = input if input_func is None else input_func

    while True:
        print_func(title)
        for index, option in enumerate(options, start=1):
            print_func(f"  {index}) {option.label}")

        if allow_multiple:
            prompt = "Enter one or more numbers (comma or space separated), or 'q' to cancel: "
        else:
            prompt = "Enter the number of your choice, or 'q' to cancel: "

        try:
            response = prompt_input(prompt)
        except (EOFError, KeyboardInterrupt) as exc:  # pragma: no cover - exercised via MenuCancelled tests
            raise MenuCancelled from exc

        response = response.strip()
        if not response:
            print_func("Please choose at least one option.")
            continue

        lowered = response.lower()
        if lowered in {"q", "quit", "exit"}:
            raise MenuCancelled

        raw_tokens: Iterable[str]
        if allow_multiple:
            raw_tokens = _normalise_tokens(response)
        else:
            raw_tokens = [response]

        tokens = [token for token in raw_tokens if token]
        if not tokens:
            print_func("Please choose at least one option.")
            continue

        try:
            indexes = [int(token) for token in tokens]
        except ValueError:
            print_func("Selections must be numeric.")
            continue

        if not allow_multiple and len(indexes) > 1:
            print_func("Only one option can be selected.")
            continue

        max_index = len(options)
        if any(index < 1 or index > max_index for index in indexes):
            print_func("Selection out of range. Try again.")
            continue

        seen: set[int] = set()
        result: list[str] = []
        for index in indexes:
            if index in seen:
                continue
            seen.add(index)
            result.append(options[index - 1].key)
        return result
