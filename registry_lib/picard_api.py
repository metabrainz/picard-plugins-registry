"""Resolve the Picard plugin-API surface and (optionally) a Picard source tree.

A Picard v3 plugin is only supposed to import Picard code from
``picard.plugin3.api`` (see Picard's ``docs/PLUGINSV3/API.md``):

    "Classes that are considered part of the API like Metadata, Track, Album,
    etc. should be imported directly from picard.plugin3.api instead from
    elsewhere in Picard."

This module provides two things, for the two audit questions:

- :func:`fetch_api_surface` — the sanctioned API surface (``picard.plugin3.api``
  plus its ``__all__``). Used by the *conformance* audit: "does the plugin obey
  the documented API contract?" It fetches just ``api.py`` over HTTP, so it is
  cheap and needs no clone.

- :class:`PicardSource` / :func:`load_picard_source` — a checked-out Picard
  source tree at a given ref, able to answer "does ``picard.X`` still exist?"
  and "is name ``N`` still importable from ``picard.X``?". Used by the
  *breakage* audit: "will this plugin's imports still resolve on *this* Picard
  branch?" — the real signal for a refactoring branch that moves or renames
  internals without changing ``__all__``.

Both accept a configurable repository (default ``metabrainz/picard``) so the
audit can target a fork and its feature branches (e.g. ``myfork/picard`` ->
``my-refactor-branch``).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import requests

from registry_lib.signature import Signature, find_function_def


# The one module a plugin is allowed to import Picard code from.
API_MODULE = "picard.plugin3.api"

# Default Picard repository, as "owner/repo" on GitHub.
DEFAULT_PICARD_REPO = "metabrainz/picard"

# Raw source of a single file at a given ref on a GitHub repo.
_RAW_URL = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

# Clone URL for a full Picard source tree.
_CLONE_URL = "https://github.com/{repo}.git"

_FETCH_TIMEOUT = 20


class ApiSurfaceError(Exception):
    """Raised when the Picard API surface cannot be resolved."""


@dataclass(frozen=True)
class ApiSurface:
    """The sanctioned plugin-API surface for one Picard ref.

    Attributes:
        ref: The Picard git ref the surface was resolved from.
        repo: The ``owner/repo`` the surface was resolved from.
        module: The allowed import module (``picard.plugin3.api``).
        exported_names: Names exported by that module (its ``__all__``).
    """

    ref: str
    repo: str = DEFAULT_PICARD_REPO
    module: str = API_MODULE
    exported_names: frozenset[str] = frozenset()


def _extract_dunder_all(source: str) -> list[str]:
    """Return the string entries of a module's ``__all__`` list."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if not isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        raise ApiSurfaceError("picard.plugin3.api __all__ is not a literal list/tuple/set")
                    names = [
                        el.value for el in node.value.elts if isinstance(el, ast.Constant) and isinstance(el.value, str)
                    ]
                    return names
    raise ApiSurfaceError("picard.plugin3.api does not define __all__")


def fetch_api_surface(ref: str = "master", repo: str = DEFAULT_PICARD_REPO) -> ApiSurface:
    """Resolve the plugin-API surface from Picard source at ``ref``.

    Args:
        ref: Picard git ref — a branch (default ``master``), tag (e.g.
            ``release-3.0.3``) or commit SHA.
        repo: ``owner/repo`` on GitHub (default ``metabrainz/picard``).

    Returns:
        ApiSurface for that ref.

    Raises:
        ApiSurfaceError: If the source cannot be fetched or parsed.
    """
    url = _RAW_URL.format(repo=repo, ref=ref, path="picard/plugin3/api.py")
    try:
        response = requests.get(url, timeout=_FETCH_TIMEOUT)
    except requests.RequestException as e:
        raise ApiSurfaceError(f"Could not fetch picard.plugin3.api at {repo}@{ref}: {e}") from e
    if response.status_code == 404:
        raise ApiSurfaceError(f"picard.plugin3.api not found at {repo}@{ref} (is the ref/tag correct?): {url}")
    if response.status_code != 200:
        raise ApiSurfaceError(f"Fetching picard.plugin3.api at {repo}@{ref} failed: HTTP {response.status_code}")

    names = _extract_dunder_all(response.text)
    return ApiSurface(ref=ref, repo=repo, module=API_MODULE, exported_names=frozenset(names))


def picard_clone_url(repo: str = DEFAULT_PICARD_REPO) -> str:
    """Return the git clone URL for a Picard ``owner/repo``."""
    return _CLONE_URL.format(repo=repo)


def _module_to_relpaths(dotted: str) -> tuple[str, str]:
    """Map a dotted module (``picard.a.b``) to its candidate file paths.

    Returns ``(module_file, package_init)`` relative paths, e.g.
    ``("picard/a/b.py", "picard/a/b/__init__.py")``.
    """
    parts = dotted.split(".")
    module_file = Path(*parts).with_suffix(".py")
    package_init = Path(*parts, "__init__.py")
    return str(module_file), str(package_init)


def _top_level_names(source: str) -> frozenset[str]:
    """Return names a module binds at top level (defs, assignments, imports).

    This is the set of names ``from <module> import <name>`` can resolve,
    including re-exported imports. It intentionally over-approximates (it does
    not evaluate ``__all__`` or conditionals) — for a breakage check a false
    negative (claiming something broke when it did not) is worse than a false
    positive, so being generous about what "exists" is the safe direction.
    """
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                _collect_assigned(target, names)
        elif isinstance(node, (ast.AnnAssign,)):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name)
    return frozenset(names)


def _collect_assigned(target: ast.expr, names: set[str]) -> None:
    """Add names bound by an assignment target (handles tuple/list unpacking)."""
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for el in target.elts:
            _collect_assigned(el, names)


class PicardSource:
    """A checked-out Picard source tree, for resolving plugin imports.

    Given the root of a Picard clone, answers whether a dotted ``picard.*``
    module exists and whether a given name is importable from it. Results are
    cached per module.
    """

    def __init__(self, root: Path, ref: str, repo: str):
        self.root = root
        self.ref = ref
        self.repo = repo
        self._name_cache: dict[str, frozenset[str] | None] = {}

    def module_exists(self, dotted: str) -> bool:
        """True if ``dotted`` resolves to a module or package file in the tree."""
        if not (dotted == "picard" or dotted.startswith("picard.")):
            return False
        return self._module_file(dotted) is not None

    def name_exists(self, dotted_module: str, name: str) -> bool:
        """True if ``name`` is importable from ``dotted_module``.

        A name "exists" if the module defines/binds it at top level, OR if
        ``dotted_module.name`` is itself a submodule (so ``from picard.x import
        y`` where ``y`` is the module ``picard.x.y``).
        """
        if self.module_exists(f"{dotted_module}.{name}"):
            return True
        top = self._top_names(dotted_module)
        return top is not None and name in top

    def function_signature(self, dotted_module: str, name: str) -> Signature | None:
        """Return the signature of top-level function ``name`` in the module.

        Returns None if the module/function is absent or ``name`` is not a
        plain function (e.g. a class or a re-exported import) — callers treat
        "unknown" as "cannot check", never as a breakage.
        """
        path = self._module_file(dotted_module)
        if path is None:
            return None
        try:
            node = find_function_def(path.read_text(encoding="utf-8"), name)
        except (OSError, UnicodeDecodeError, SyntaxError):
            return None
        return Signature.from_function_def(node) if node is not None else None

    def _module_file(self, dotted: str) -> Path | None:
        module_rel, package_rel = _module_to_relpaths(dotted)
        for rel in (module_rel, package_rel):
            candidate = self.root / rel
            if candidate.is_file():
                return candidate
        return None

    def _top_names(self, dotted_module: str) -> frozenset[str] | None:
        if dotted_module in self._name_cache:
            return self._name_cache[dotted_module]
        path = self._module_file(dotted_module)
        result: frozenset[str] | None = None
        if path is not None:
            try:
                result = _top_level_names(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, SyntaxError):
                result = None
        self._name_cache[dotted_module] = result
        return result
