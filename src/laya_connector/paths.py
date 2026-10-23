"""Read items from project files so Claude never has to paste them."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


@dataclass(frozen=True)
class Item:
    id: str
    text: str


class PathError(ValueError):
    pass


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars < 5:
        return text[:max(max_chars, 0)]
    half = (max_chars - 3) // 2
    return text[:half] + " … " + text[-half:]


def _unsafe_pattern(pattern: str) -> bool:
    if not pattern:
        return True
    if pattern.startswith(("/", "\\")):
        return True
    for flavour in (PurePosixPath, PureWindowsPath):
        pure = flavour(pattern)
        if pure.anchor or ".." in pure.parts:
            return True
    return False


def _relative(root: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, RuntimeError):  # RuntimeError: symlink loop on py<=3.12
        return None


def _hidden(root: Path, path: Path) -> bool:
    """True for anything under a dot-dir/dotfile, __pycache__ or node_modules (venvs, secrets, logs)."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part.startswith(".") or part in ("__pycache__", "node_modules") for part in parts)


def _is_binary(path: Path) -> bool:
    with path.open("rb") as handle:
        return b"\0" in handle.read(8192)


def collect_paths(root: Path, patterns: list[str], max_items: int, max_chars: int) -> tuple[list[Item], int]:
    """Glob files under root. Matches inside hidden dirs, __pycache__ or node_modules are ignored
    silently (so a pattern aimed at a root dotfile such as .gitignore matches nothing). Once max_items
    is reached the remaining matches are only counted as skipped, without touching the disk."""
    items: list[Item] = []
    seen: set[str] = set()
    skipped = 0
    for pattern in patterns:
        if _unsafe_pattern(pattern):
            skipped += 1
            continue
        try:
            matches = sorted(root.glob(pattern))
        except (ValueError, NotImplementedError, OSError):
            skipped += 1
            continue
        for path in matches:
            if _hidden(root, path):
                continue
            if len(items) >= max_items:
                skipped += 1
                continue
            try:
                if not path.is_file():
                    continue
                rel = _relative(root, path)
                if rel is None or _is_binary(path):
                    skipped += 1
                    continue
                if rel in seen:
                    continue
                text =path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                skipped += 1
                continue
            seen.add(rel)
            items.append(Item(rel, truncate(text, max_chars)))
    return items, skipped


def collect_lines(root: Path, file: str, start: int | None, end: int | None,
                  max_items: int, max_chars: int) -> tuple[list[Item], int]:
    if _unsafe_pattern(file):
        raise PathError(f"refused: {file}")
    path = root / file
    try:
        if _relative(root, path) is None or not path.is_file() or _is_binary(path):
            raise PathError(f"refused: {file}")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise PathError(f"refused: {file}") from exc
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
