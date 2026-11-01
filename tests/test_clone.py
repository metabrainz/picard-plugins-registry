"""Tests for cloning plugin trees (ephemeral and cached)."""

from pathlib import Path
import shutil
import subprocess

import pytest

from registry_lib.clone import CloneError, clone_tree


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def source_repo(tmp_path):
    """Create a local git repo (served via file://) with one commit on 'main'."""
    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo = tmp_path / "source"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "t@example.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "plugin.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "initial", cwd=repo)
    return repo


def _url(repo: Path) -> str:
    return f"file://{repo}"


def test_ephemeral_clone_yields_tree_and_cleans_up(source_repo):
    captured: Path | None = None
    with clone_tree(_url(source_repo), "main") as tree:
        captured = tree
        assert (tree / "plugin.py").read_text() == "VALUE = 1\n"
    # Temp tree removed on exit.
    assert captured is not None
    assert not captured.exists()


def test_cached_clone_persists(tmp_path, source_repo):
    cache = tmp_path / "cache"
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        slot = tree
        assert (tree / "plugin.py").exists()
    # Cached slot persists after the context exits.
    assert slot.exists()
    assert (slot / "plugin.py").exists()


def test_cached_clone_reused_and_refreshed(tmp_path, source_repo):
    cache = tmp_path / "cache"
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        first_slot = tree

    # Add a new commit upstream.
    (source_repo / "plugin.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git("add", ".", cwd=source_repo)
    _git("commit", "-q", "-m", "update", cwd=source_repo)

    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        # Same slot reused (not a fresh temp dir)...
        assert tree == first_slot
        # ...and refreshed to the new upstream content.
        assert (tree / "plugin.py").read_text() == "VALUE = 2\n"


def test_corrupt_cache_slot_is_reclone(tmp_path, source_repo):
    cache = tmp_path / "cache"
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        slot = tree
    # Corrupt the slot by removing its .git dir.
    shutil.rmtree(slot / ".git")
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        assert (tree / "plugin.py").exists()
        assert (tree / ".git").is_dir()


def test_manually_removed_cache_slot_is_recloned(tmp_path, source_repo):
    cache = tmp_path / "cache"
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        slot = tree
    # User wiped the whole slot between runs.
    shutil.rmtree(slot)
    assert not slot.exists()
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        assert tree == slot  # same deterministic slot path
        assert (tree / "plugin.py").exists()
        assert (tree / ".git").is_dir()


def test_junk_cache_slot_is_replaced(tmp_path, source_repo):
    cache = tmp_path / "cache"
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        slot = tree
    # Slot exists but is not a git repo (leftover junk / interrupted clone).
    shutil.rmtree(slot)
    slot.mkdir()
    (slot / "junk.txt").write_text("x", encoding="utf-8")
    with clone_tree(_url(source_repo), "main", cache_dir=cache) as tree:
        assert (tree / "plugin.py").exists()
        assert not (tree / "junk.txt").exists()


def test_clone_failure_raises(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    missing = tmp_path / "does-not-exist"
    with pytest.raises(CloneError):
        with clone_tree(f"file://{missing}", "main"):
            pass
