"""Clone a plugin repository tree for auditing.

The manifest fetcher only needs a single file, but auditing needs the whole
plugin source tree. This does a shallow (``--depth 1``) clone of a given ref.

Two modes:

- Ephemeral (default): clone into a temp dir, removed on exit. Always fresh;
  nothing left on disk. Best for CI.
- Cached (``cache_dir`` given): keep a persistent shallow clone per repository
  and refresh it on subsequent runs, to avoid re-downloading unchanged repos
  during repeated local runs.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile


CLONE_TIMEOUT = 60


class CloneError(Exception):
    """Raised when cloning a repository fails."""


def _find_git() -> str:
    git = shutil.which("git")
    if not git:
        raise CloneError("git executable not found in PATH")
    return git


def _run_git(args: list[str], cwd: str | None = None) -> None:
    """Run a git command, raising CloneError on failure/timeout."""
    try:
        subprocess.run(args, capture_output=True, check=True, timeout=CLONE_TIMEOUT, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        raise CloneError(f"git command timed out after {CLONE_TIMEOUT}s: {' '.join(args)}") from e
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace").strip() if e.stderr else ""
        raise CloneError(f"git command failed ({' '.join(args[1:3])}…): {stderr}") from e


def _shallow_clone(git: str, git_url: str, ref: str | None, dest: str) -> None:
    """Shallow-clone ``git_url`` at ``ref`` into the (empty) ``dest`` dir."""
    cmd = [git, "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [git_url, dest]
    _run_git(cmd)


def _cache_slot(cache_dir: Path, git_url: str) -> Path:
    """Return a stable per-repository directory inside ``cache_dir``.

    The directory name combines a sanitized repo name with a short hash of the
    URL, so different URLs never collide and the name stays human-readable.
    """
    digest = hashlib.sha256(git_url.encode("utf-8")).hexdigest()[:12]
    name = git_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") or "repo"
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name)
    return cache_dir / f"{safe}-{digest}"


def _refresh_cached(git: str, git_url: str, ref: str | None, slot: Path) -> bool:
    """Refresh an existing cached shallow clone to ``ref``.

    Returns True on success, False if the cache is unusable (caller re-clones).
    """
    if not (slot / ".git").is_dir():
        return False
    try:
        if ref:
            _run_git([git, "fetch", "--depth", "1", "origin", ref], cwd=str(slot))
            _run_git([git, "checkout", "-f", "FETCH_HEAD"], cwd=str(slot))
        else:
            _run_git([git, "fetch", "--depth", "1", "origin"], cwd=str(slot))
            _run_git([git, "checkout", "-f", "FETCH_HEAD"], cwd=str(slot))
        # Drop any untracked leftovers from a previous checkout.
        _run_git([git, "clean", "-fdx"], cwd=str(slot))
        return True
    except CloneError:
        return False


@contextmanager
def clone_tree(git_url: str, ref: str | None = None, cache_dir: str | Path | None = None) -> Generator[Path]:
    """Provide a checked-out plugin tree at ``ref``; yield its path.

    Args:
        git_url: Repository URL.
        ref: Branch or tag to check out. ``None`` uses the repository's default
            branch. (A bare commit SHA is not supported by ``--branch`` on a
            shallow clone; registry refs are branch/tag names.)
        cache_dir: If given, keep a persistent shallow clone per repository here
            and refresh it on reuse. If ``None`` (default), clone into a temp
            dir that is removed on exit.

    Yields:
        Path to the checked-out working tree. For the ephemeral mode it is
        removed on exit; for the cached mode it persists under ``cache_dir``.

    Raises:
        CloneError: If the clone/refresh fails or times out.
    """
    git = _find_git()

    if cache_dir is None:
        tmpdir = tempfile.mkdtemp(prefix="picard-plugin-audit-")
        try:
            _shallow_clone(git, git_url, ref, tmpdir)
            yield Path(tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    slot = _cache_slot(cache_root, git_url)

    if slot.exists():
        if not _refresh_cached(git, git_url, ref, slot):
            # Stale/corrupt cache slot: start clean.
            shutil.rmtree(slot, ignore_errors=True)
            _shallow_clone(git, git_url, ref, str(slot))
    else:
        _shallow_clone(git, git_url, ref, str(slot))

    # Cached clones persist; do not remove on exit.
    yield slot
