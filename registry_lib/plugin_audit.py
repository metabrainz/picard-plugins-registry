"""Audit Picard v3 plugins for use of Picard code outside the plugin API.

A plugin should import Picard code only from ``picard.plugin3.api`` (see
:mod:`registry_lib.picard_api`). Any other ``import picard...`` /
``from picard... import ...`` reaches into Picard internals and may break when
those internals change — exactly what this audit surfaces.

Detection is AST-based (not regex), so it correctly handles multi-line imports,
aliases and ``if TYPE_CHECKING:`` blocks, and ignores comments and strings. On
top of plain ``import`` statements it also flags *literal* dynamic imports
(``importlib.import_module("picard.x")`` / ``__import__("picard.x")``) and, in
breakage mode, checks a plugin's *direct calls* of imported Picard functions
against the target signature.

Limitations — this is an import/resolution checker, not a full compatibility
checker. It is deliberately conservative (it prefers to miss a problem over
raising a false alarm), and it CANNOT detect:

- Type or value changes of a name that still exists (e.g. a module-level list
  becoming a dict, or a constant changing value). The import still resolves, so
  the audit stays silent.
- Behavioral changes behind an unchanged signature (different return value,
  new exception, in-place vs. copy, changed ordering/units).
- Changes to class *members*: renamed/removed methods or attributes of a class
  a plugin uses or subclasses. Only the top-level class name is tracked.
- Method/attribute compatibility in general — only *direct function calls* of
  an imported name are signature-checked, not method calls on instances.
- Signature checks beyond the two unambiguous cases (unknown keyword arg; too
  many positional args). "Missing required argument" is not reported.
- Non-literal dynamic imports (``importlib.import_module(name)``), ``getattr``
  on a module, and other runtime indirection.
- Non-Python breakage: manifest/API-version mismatch, resource layout, Qt
  ``.ui`` changes, config option keys, removed signals/slots.

A clean breakage report therefore means "no plugin imports or calls anything we
removed, relocated, or changed the arity of" — not "no plugin will break".
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from registry_lib.picard_api import API_MODULE, ApiSurface, PicardSource
from registry_lib.signature import incompatible_reason


class Severity(str, Enum):
    """How concerning an out-of-API import is.

    Defined most-concerning first; ``rank`` reflects that definition order, so
    the set of levels and their ordering live in exactly one place. It subclasses
    ``str`` so a member compares equal to its label and serializes to JSON as
    ``"high"`` / ``"medium"`` / ``"low"`` with no extra conversion.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        """Sort key: 0 for the most concerning level (definition order)."""
        return list(type(self)).index(self)


# Backwards-friendly aliases (also what the classification table reads best as).
SEVERITY_HIGH = Severity.HIGH
SEVERITY_MEDIUM = Severity.MEDIUM
SEVERITY_LOW = Severity.LOW

# Classification of out-of-API Picard imports, keyed by the dotted path a plugin
# imported (module for ``import x``, ``module.name`` for ``from module import
# name``). Each entry is (severity, suggested API replacement). The
# longest/most-specific matching prefix wins; anything unmatched is low with no
# suggestion. Keeping severity and suggestion in one table avoids the two
# drifting apart.
_RULES: dict[str, tuple[Severity, str | None]] = {
    # UI internals: not part of the plugin API, highest breakage risk.
    "picard.ui": (SEVERITY_HIGH, "UI internals are not part of the plugin API (high breakage risk)"),
    # Common cases with a clear, documented API replacement.
    "picard.log": (SEVERITY_MEDIUM, "use api.logger"),
    "picard.config": (SEVERITY_MEDIUM, "use api.global_config / api.plugin_config"),
    "picard.i18n": (SEVERITY_MEDIUM, "use api.tr() / t_() from picard.plugin3.api"),
    "picard.webservice.api_helpers": (SEVERITY_MEDIUM, "use api.mb_api"),
    "picard.webservice": (SEVERITY_MEDIUM, "use api.web_service"),
    "picard.metadata": (SEVERITY_MEDIUM, "import Metadata from picard.plugin3.api"),
    "picard.album": (SEVERITY_MEDIUM, "import Album from picard.plugin3.api"),
    "picard.track": (SEVERITY_MEDIUM, "import Track from picard.plugin3.api"),
    "picard.cluster": (SEVERITY_MEDIUM, "import Cluster from picard.plugin3.api"),
    "picard.file": (SEVERITY_MEDIUM, "import File from picard.plugin3.api"),
    "picard.item": (SEVERITY_MEDIUM, "import MetadataItem from picard.plugin3.api"),
    "picard.script": (
        SEVERITY_MEDIUM,
        "import ScriptParser from picard.plugin3.api / use api.register_script_function",
    ),
    "picard.coverart": (SEVERITY_MEDIUM, "use the cover-art provider/image classes from picard.plugin3.api"),
    "picard.debug_opts": (SEVERITY_MEDIUM, "import DebugOpt from picard.plugin3.api"),
}

# Directory names that typically hold vendored third-party code; skip them so
# a plugin is not blamed for libraries it bundles.
_SKIP_DIRS = frozenset({".git", "__pycache__", "vendor", "vendored", "_vendor", "third_party", "libs", "site-packages"})


@dataclass(frozen=True)
class Finding:
    """One out-of-API use of Picard code.

    A finding is either a plain ``import picard.x`` (``name is None``) or a
    ``from picard.x import y`` (``name == "y"``). ``imported`` and ``kind`` are
    derived from ``module`` / ``name`` so there is a single source of truth.
    Use :meth:`for_import` / :meth:`for_from_import` to build one, rather than
    the positional constructor.
    """

    file: str  # path relative to the plugin root
    line: int
    module: str  # the picard module, e.g. "picard.ui.util"
    name: str | None  # imported name for a from-import; None for a plain import
    severity: Severity
    suggestion: str | None
    guarded: bool = False  # inside a try/except that catches ImportError (optional import)
    dynamic: bool = False  # a runtime import (importlib/__import__) with a literal picard target

    @classmethod
    def for_import(
        cls, file: str, line: int, module: str, severity: Severity, suggestion: str | None, *, guarded: bool
    ) -> Finding:
        """Build a finding for ``import picard.x``."""
        return cls(file, line, module, None, severity, suggestion, guarded)

    @classmethod
    def for_dynamic_import(cls, file: str, line: int, module: str) -> Finding:
        """Build a finding for a runtime ``importlib.import_module("picard.x")``.

        The module target is still checked for existence (so a literal dynamic
        import of a removed module is caught), but the suggestion flags that
        dynamic use is only partially verifiable.
        """
        return cls(
            file,
            line,
            module,
            None,
            SEVERITY_MEDIUM,
            "dynamic import of Picard code — only the module path is verified, not its use",
            dynamic=True,
        )

    @classmethod
    def for_from_import(
        cls, file: str, line: int, module: str, name: str, severity: Severity, suggestion: str | None, *, guarded: bool
    ) -> Finding:
        """Build a finding for ``from picard.x import name``."""
        return cls(file, line, module, name, severity, suggestion, guarded)

    @property
    def kind(self) -> str:
        if self.dynamic:
            return "dynamic-import"
        return "import" if self.name is None else "from-import"

    @property
    def imported(self) -> str:
        """The dotted path as written, e.g. "picard.ui.util.FileDialog"."""
        return self.module if self.name is None else f"{self.module}.{self.name}"

    def breaks_on(self, source: PicardSource) -> bool:
        """True if this import would fail to resolve against ``source``.

        For ``import picard.x`` the module must exist. For ``from picard.x
        import y`` the module must exist and ``y`` must be importable from it.

        A ``guarded`` import (inside a ``try`` that catches ``ImportError``) is
        never counted as breaking: the plugin intentionally tolerates it failing
        — typically a compatibility fallback across Picard versions.
        """
        if self.guarded:
            return False
        if not source.module_exists(self.module):
            return True
        # from-import: the imported name must also exist in the module.
        return self.name is not None and not source.name_exists(self.module, self.name)


@dataclass(frozen=True)
class ParseError:
    """A plugin file that could not be analyzed (unreadable or invalid syntax).

    An unparseable file is a problem in its own right: the audit cannot prove it
    stays within the plugin API, so it is reported rather than silently skipped.
    """

    file: str  # path relative to the plugin root
    message: str


@dataclass(frozen=True)
class CallSite:
    """A direct call, in a plugin, of a name imported from Picard.

    Recorded during the scan so a later breakage check can compare the call's
    arguments against the target function's signature. ``arg_count`` and
    ``keywords`` capture just what the signature check needs; ``has_spread`` is
    set when the call uses ``*args``/``**kwargs``, which makes arity checking
    inconclusive.
    """

    file: str
    line: int
    module: str  # the picard module the callee was imported from
    name: str  # the callee's name as defined in Picard
    arg_count: int  # number of positional args at the call site
    keywords: tuple[str, ...]  # explicit keyword-arg names at the call site
    has_spread: bool  # call uses *args or **kwargs (arity unknown)


@dataclass(frozen=True)
class CallIssue:
    """A plugin call that is incompatible with the target function signature."""

    file: str
    line: int
    callee: str  # "module.name"
    reason: str


@dataclass(frozen=True)
class PluginAuditResult:
    """Audit result for a single plugin."""

    plugin_id: str
    files_scanned: int
    findings: tuple[Finding, ...]
    parse_errors: tuple[ParseError, ...] = ()
    calls: tuple[CallSite, ...] = ()  # direct calls of imported Picard names

    @property
    def ok(self) -> bool:
        return not self.findings and not self.parse_errors


def _classify(dotted_path: str) -> tuple[Severity, str | None]:
    """Return (severity, suggestion) for an imported ``picard`` dotted path.

    Matches the most specific prefix in ``_RULES`` (so
    ``picard.webservice.api_helpers`` wins over ``picard.webservice``);
    unmatched paths are low severity with no suggestion.
    """
    best: tuple[Severity, str | None] = (SEVERITY_LOW, None)
    best_len = -1
    for prefix, rule in _RULES.items():
        if (dotted_path == prefix or dotted_path.startswith(prefix + ".")) and len(prefix) > best_len:
            best, best_len = rule, len(prefix)
    return best


def _is_picard(module: str) -> bool:
    return module == "picard" or module.startswith("picard.")


# Exception names that signal an "optional import" fallback when caught.
_IMPORT_GUARD_EXCEPTIONS = frozenset({"ImportError", "ModuleNotFoundError"})


def _exc_name(node: ast.expr | None) -> str | None:
    """Return the simple name of an exception expression, if any."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _handler_catches_importerror(handler: ast.ExceptHandler) -> bool:
    """True if an ``except`` clause catches ImportError (or is bare)."""
    exc = handler.type
    if exc is None:
        return True  # bare `except:` swallows everything, including ImportError
    exprs = exc.elts if isinstance(exc, ast.Tuple) else [exc]
    return any(_exc_name(e) in _IMPORT_GUARD_EXCEPTIONS for e in exprs)


def _guarded_import_nodes(tree: ast.AST) -> set[int]:
    """Return ids of import nodes inside a try that catches ImportError.

    These are intentional optional imports (compatibility fallbacks); a failure
    to resolve them is expected and must not be reported as breakage.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(_handler_catches_importerror(h) for h in node.handlers):
            for stmt in node.body:
                for inner in ast.walk(stmt):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        guarded.add(id(inner))
    return guarded


def _iter_python_files(root: Path) -> Iterator[Path]:
    """Yield plugin-owned ``.py`` files under ``root``, skipping vendored dirs."""
    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _scan_source(source: str, rel_path: str, surface: ApiSurface) -> tuple[list[Finding], list[CallSite]]:
    """Return (out-of-API findings, call sites) for one file's source.

    Call sites are the direct calls of names imported from a Picard module;
    they let a later breakage check compare arguments against target signatures.
    """
    tree = ast.parse(source)
    guarded_nodes = _guarded_import_nodes(tree)

    findings: list[Finding] = []
    # Map a local name bound by `from picard.x import f [as g]` to (module, f),
    # so calls through the local name can be traced back to the Picard callee.
    imported_callables: dict[str, tuple[str, str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            findings += _scan_import(node, rel_path, guarded=id(node) in guarded_nodes)
        elif isinstance(node, ast.ImportFrom):
            findings += _scan_import_from(
                node, rel_path, surface, guarded=id(node) in guarded_nodes, bindings=imported_callables
            )
        elif isinstance(node, ast.Call):
            dynamic = _dynamic_import_finding(node, rel_path)
            if dynamic is not None:
                findings.append(dynamic)

    calls = list(_collect_calls(tree, rel_path, imported_callables))
    return findings, calls


def _dynamic_import_finding(node: ast.Call, rel_path: str) -> Finding | None:
    """A finding for ``importlib.import_module("picard.x")`` / ``__import__``.

    Only literal picard string targets are recognized; non-literal arguments
    cannot be resolved statically and are out of scope.
    """
    target = _dynamic_import_target(node)
    if target is None or not _is_picard(target):
        return None
    return Finding.for_dynamic_import(rel_path, node.lineno, target)


def _dynamic_import_target(node: ast.Call) -> str | None:
    """Return the literal module string of a dynamic import call, if any."""
    func = node.func
    is_import_module = isinstance(func, ast.Attribute) and func.attr == "import_module"
    is_dunder_import = isinstance(func, ast.Name) and func.id == "__import__"
    if not (is_import_module or is_dunder_import):
        return None
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None


def _collect_calls(tree: ast.AST, rel_path: str, bindings: dict[str, tuple[str, str]]) -> Iterator[CallSite]:
    """Yield call sites for calls made through an imported Picard callable."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        binding = bindings.get(node.func.id)
        if binding is None:
            continue
        module, name = binding
        has_spread = any(isinstance(a, ast.Starred) for a in node.args) or any(kw.arg is None for kw in node.keywords)
        yield CallSite(
            file=rel_path,
            line=node.lineno,
            module=module,
            name=name,
            arg_count=sum(1 for a in node.args if not isinstance(a, ast.Starred)),
            keywords=tuple(kw.arg for kw in node.keywords if kw.arg is not None),
            has_spread=has_spread,
        )


def _scan_import(node: ast.Import, rel_path: str, *, guarded: bool) -> Iterator[Finding]:
    """Yield findings for ``import picard...`` statements."""
    for alias in node.names:
        module = alias.name
        if _is_picard(module) and module != API_MODULE:
            severity, suggestion = _classify(module)
            yield Finding.for_import(rel_path, node.lineno, module, severity, suggestion, guarded=guarded)


def _scan_import_from(
    node: ast.ImportFrom,
    rel_path: str,
    surface: ApiSurface,
    *,
    guarded: bool,
    bindings: dict[str, tuple[str, str]],
) -> Iterator[Finding]:
    """Yield findings for ``from picard... import name`` statements.

    Also records local-name -> (module, name) bindings for non-API imports, so
    later call sites can be matched to the Picard callee.
    """
    # Ignore relative imports (node.module is the plugin's own package).
    module = node.module or ""
    if node.level > 0 or not _is_picard(module):
        return

    for alias in node.names:
        if alias.name == "*":
            continue
        if module != API_MODULE:
            bindings[alias.asname or alias.name] = (module, alias.name)
        if module == API_MODULE:
            # Allowed module: flag only names it does NOT export.
            if alias.name not in surface.exported_names:
                suggestion = f"'{alias.name}' is not exported by {API_MODULE}"
                yield Finding.for_from_import(
                    rel_path, node.lineno, module, alias.name, SEVERITY_MEDIUM, suggestion, guarded=guarded
                )
        else:
            # Classify by the full dotted path so `from picard import log` maps
            # to picard.log rather than the bare module 'picard'.
            severity, suggestion = _classify(f"{module}.{alias.name}")
            yield Finding.for_from_import(
                rel_path, node.lineno, module, alias.name, severity, suggestion, guarded=guarded
            )


def audit_plugin_tree(plugin_id: str, root: Path, surface: ApiSurface) -> PluginAuditResult:
    """Audit a plugin source tree for out-of-API Picard use.

    Args:
        plugin_id: The plugin's registry id (for reporting).
        root: Path to the plugin's checked-out source tree.
        surface: The sanctioned Picard API surface to check against.

    Returns:
        PluginAuditResult with all findings and any files that failed to parse.
    """
    findings: list[Finding] = []
    parse_errors: list[ParseError] = []
    calls: list[CallSite] = []
    files_scanned = 0

    for path in _iter_python_files(root):
        rel = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            parse_errors.append(ParseError(rel, f"could not read: {e}"))
            continue
        files_scanned += 1
        try:
            file_findings, file_calls = _scan_source(source, rel, surface)
        except SyntaxError as e:
            parse_errors.append(ParseError(rel, f"syntax error: {e}"))
            continue
        findings.extend(file_findings)
        calls.extend(file_calls)

    # Stable ordering: by file, then line, then imported name.
    findings.sort(key=lambda f: (f.file, f.line, f.imported))
    calls.sort(key=lambda c: (c.file, c.line, c.name))
    return PluginAuditResult(
        plugin_id=plugin_id,
        files_scanned=files_scanned,
        findings=tuple(findings),
        parse_errors=tuple(parse_errors),
        calls=tuple(calls),
    )


def breaking_findings(result: PluginAuditResult, source: PicardSource) -> tuple[Finding, ...]:
    """Return the subset of ``result`` findings that do not resolve on ``source``.

    This is the *breakage* view: of all the out-of-API Picard imports a plugin
    makes, which ones would actually fail to import against the given Picard
    source tree (e.g. a refactoring branch). An empty result means the plugin's
    Picard imports all still resolve on that branch.
    """
    return tuple(f for f in result.findings if f.breaks_on(source))


def signature_issues(result: PluginAuditResult, source: PicardSource) -> tuple[CallIssue, ...]:
    """Return calls whose arguments are incompatible with the target signature.

    For each recorded call of a Picard function, if that function still resolves
    to a plain ``def`` on ``source`` and the call uses no argument spread, the
    call's arguments are checked against the signature. Only unambiguous
    mismatches are reported (unknown keyword, too many positionals).
    """
    issues: list[CallIssue] = []
    for call in result.calls:
        if call.has_spread:
            continue
        sig = source.function_signature(call.module, call.name)
        if sig is None:
            continue  # not a plain function on target (class, re-export, gone): can't check
        reason = incompatible_reason(call.arg_count, call.keywords, sig)
        if reason is not None:
            issues.append(CallIssue(call.file, call.line, f"{call.module}.{call.name}", reason))
    return tuple(issues)


def summarize_severities(findings: Iterable[Finding]) -> dict[Severity, int]:
    """Count findings per severity (keys cover every level, even if zero)."""
    counts = {severity: 0 for severity in Severity}
    for f in findings:
        counts[f.severity] += 1
    return counts


def resolve_plugin_ref(plugin: dict, override: str | None = None) -> str | None:
    """Pick the git ref to audit for a registry plugin entry.

    Precedence: explicit ``override`` > the plugin's last declared ref name >
    ``None`` (clone the repository's default branch).
    """
    if override:
        return override
    refs = plugin.get("refs") or []
    if refs:
        # Last declared ref is the newest/most-relevant by registry convention.
        name = refs[-1].get("name")
        if name:
            return str(name)
    return None
