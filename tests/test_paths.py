import os
from pathlib import Path

import pytest

from laya_connector.paths import PathError, collect_lines, collect_paths, truncate


def make_tree(root):
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("print('a')", encoding="utf-8")
    (root / "src" / "b.py").write_text("print('b')", encoding="utf-8")
    (root / "src" / "blob.bin").write_bytes(b"\x00\x01binary")
    (root / "log.txt").write_text("first\n\nsecond\nthird\n", encoding="utf-8")


def test_truncate():
    assert truncate("short", 10) == "short"
    out = truncate("a" * 50 + "b" * 50, 23)
    assert out.startswith("a" * 10) and out.endswith("b" * 10) and " … " in out and len(out) <= 23


def test_collect_paths_glob_relative_ids(tmp_path):
    make_tree(tmp_path)
    items, skipped = collect_paths(tmp_path, ["src/*.py"], max_items=10, max_chars=100)
    assert [i.id for i in items] == ["src/a.py", "src/b.py"] and skipped == 0


def test_collect_paths_skips_binary_and_dedupes(tmp_path):
    make_tree(tmp_path)
    items, skipped = collect_paths(tmp_path, ["src/*", "src/a.py"], max_items=10, max_chars=100)
    assert [i.id for i in items] == ["src/a.py", "src/b.py"] and skipped == 1


@pytest.mark.parametrize("pattern", ["../*", "/etc/*", "src/../../x"])
def test_collect_paths_refuses_escape(tmp_path, pattern):
    make_tree(tmp_path)
    items, skipped = collect_paths(tmp_path, [pattern], max_items=10, max_chars=100)
    assert items == [] and skipped == 1


def test_collect_paths_refuses_symlink_escape(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        os.symlink(outside, root / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    items, skipped = collect_paths(root, ["*.txt"], max_items=10, max_chars=100)
    assert items == [] and skipped == 1


def test_collect_paths_caps_items(tmp_path):
    make_tree(tmp_path)
    items, skipped = collect_paths(tmp_path, ["src/*.py"], max_items=1, max_chars=100)
    assert len(items) == 1 and skipped == 1


def test_collect_lines_range_and_blanks(tmp_path):
    make_tree(tmp_path)
    items, skipped = collect_lines(tmp_path, "log.txt", None, None, max_items=10, max_chars=100)
    assert [(i.id, i.text) for i in items] == [("1", "first"), ("3", "second"), ("4", "third")]
    items, _ = collect_lines(tmp_path, "log.txt", 3, 3, max_items=10, max_chars=100)
    assert [i.id for i in items] == ["3"]


@pytest.mark.parametrize("file", ["../x.txt", "missing.txt", "src/blob.bin"])
def test_collect_lines_refuses(tmp_path, file):
    make_tree(tmp_path)
    with pytest.raises(PathError):
        collect_lines(tmp_path, file, None, None, max_items=10, max_chars=100)


@pytest.mark.parametrize("n", range(0, 7))
def test_truncate_never_exceeds_limit(n):
    assert len(truncate("x" * 50, n)) <= n


def test_truncate_small_limits_return_prefix():
    assert truncate("abcdefgh", 0) == ""
    assert truncate("abcdefgh", -4) == ""
    assert truncate("abcdefgh", 3) == "abc"


@pytest.mark.parametrize("pattern", ["", "C:foo", "C:/x/*", "\\\\server\\share\\*"])
def test_collect_paths_refuses_malformed_patterns(tmp_path, pattern):
    make_tree(tmp_path)
    items, skipped = collect_paths(tmp_path, [pattern], max_items=10, max_chars=100)
    assert items == [] and skipped == 1


@pytest.mark.parametrize("file", ["", "C:foo", "C:/x/*", "\\\\server\\share\\log.txt"])
def test_collect_lines_refuses_malformed_paths(tmp_path, file):
    make_tree(tmp_path)
    with pytest.raises(PathError):
        collect_lines(tmp_path, file, None, None, max_items=10, max_chars=100)


def test_collect_paths_skips_unreadable_file(tmp_path, monkeypatch):
    make_tree(tmp_path)
    original = Path.read_text

    def flaky(self, *args, **kwargs):
        if self.name == "a.py":
            raise PermissionError("denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky)
    items, skipped = collect_paths(tmp_path, ["src/*.py"], max_items=10, max_chars=100)
    assert [i.id for i in items] == ["src/b.py"] and skipped == 1


def test_collect_lines_unreadable_file_raises_path_error(tmp_path, monkeypatch):
    make_tree(tmp_path)

    def denied(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(PathError):
        collect_lines(tmp_path, "log.txt", None, None, max_items=10, max_chars=100)
