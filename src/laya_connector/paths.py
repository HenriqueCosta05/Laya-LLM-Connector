"""Read items from project files so Claude never has to paste them."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePath


@dataclass(frozen=True)
class Item:
    id: str
    text: str


class PathError(ValueError):
    pass


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = (max_chars - 3) // 2
    return text[:half] + " … " + text[-half:]


def _unsafe_pattern(pattern: str) -> bool:
    pure = PurePath(pattern)
    return pure.is_absolute() or pattern.startswith(("/", "\\")) or ".." in pure.parts


def _relative(root: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _is_binary(path: Path) -> bool:
    with path.open("rb") as handle:
        return b"\0" in handle.read(8192)


def collect_paths(root: Path, patterns: list[str], max_items: int, max_chars: int) -> tuple[list[Item], int]:
    items: list[Item] = []
    seen: set[str] = set()
    skipped = 0
    for pattern in patterns:
        if _unsafe_pattern(pattern):
            skipped += 1
            continue
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = _relative(root, path)
            if rel is None or _is_binary(path):
                skipped += 1
                continue
            if rel in seen:
                continue
            if len(items) >= max_items:
                skipped += 1
                continue
            seen.add(rel)
            items.append(Item(rel, truncate(path.read_text(encoding="utf-8", errors="replace"), max_chars)))
    return items, skipped


def collect_lines(root: Path, file: str, start: int | None, end: int | None,
                  max_items: int, max_chars: int) -> tuple[list[Item], int]:
    path = root / file
    if _unsafe_pattern(file) or _relative(root, path) is None or not path.is_file() or _is_binary(path):
        raise PathError(f"refused: {file}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    first = max(1, start or 1)
    last = min(len(lines), end or len(lines))
    items: list[Item] = []
    skipped = 0
    for number in range(first, last + 1):
        text = lines[number - 1].strip()
        if not text:
            continue
        if len(items) >= max_items:
            skipped += 1
            continue
        items.append(Item(str(number), truncate(text, max_chars)))
    return items, skipped
