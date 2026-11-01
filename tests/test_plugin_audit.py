"""Tests for the plugin API audit (AST scanner)."""

from pathlib import Path

import pytest

from registry_lib.picard_api import API_MODULE, ApiSurface, PicardSource
from registry_lib.plugin_audit import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    ParseError,
    Severity,
    audit_plugin_tree,
    breaking_findings,
    resolve_plugin_ref,
    signature_issues,
    summarize_severities,
)


# A fixed, offline API surface so tests never hit the network.
SURFACE = ApiSurface(
    ref="test",
    module=API_MODULE,
    exported_names=frozenset({"Album", "Track", "File", "Metadata", "PluginApi", "t_"}),
)


def _write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return tmp_path


def _audit(tmp_path: Path):
    return audit_plugin_tree("test-plugin", tmp_path, SURFACE)


def _write_tree(root: Path, files: dict[str, str]) -> Path:
    """Write ``{relpath: source}`` under ``root`` and return ``root``."""
    for rel, source in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return root


def _picard_tree(tmp_path: Path, files: dict[str, str]) -> PicardSource:
    """Build a fake Picard source tree under ``tmp_path/picard-src`` and wrap it."""
    root = _write_tree(tmp_path / "picard-src", files)
    return PicardSource(root, ref="test-branch", repo="zas/picard")


def _audit_plugin(tmp_path: Path, files: dict[str, str]):
    """Write a plugin tree (isolated under ``tmp_path/plugin``) and audit it."""
    root = _write_tree(tmp_path / "plugin", files)
    return audit_plugin_tree("p", root, SURFACE)


def test_clean_plugin_has_no_findings(tmp_path):
    _write(
        tmp_path,
        "__init__.py",
        "from picard.plugin3.api import Album, Metadata, PluginApi\ndef enable(api):\n    api.logger.info('ok')\n",
    )
    result = _audit(tmp_path)
    assert result.ok
    assert result.findings == ()
    assert result.files_scanned == 1


def test_from_import_internal_module_flagged(tmp_path):
    _write(tmp_path, "__init__.py", "from picard.metadata import Metadata\n")
    result = _audit(tmp_path)
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.imported == "picard.metadata.Metadata"
    assert f.kind == "from-import"
    assert f.severity == SEVERITY_MEDIUM
    assert f.suggestion and "picard.plugin3.api" in f.suggestion


def test_ui_import_is_high_severity(tmp_path):
    _write(tmp_path, "__init__.py", "from picard.ui.util import FileDialog\n")
    result = _audit(tmp_path)
    assert result.findings[0].severity == SEVERITY_HIGH


def test_plain_import_flagged(tmp_path):
    _write(tmp_path, "m.py", "import picard.config\n")
    result = _audit(tmp_path)
    assert len(result.findings) == 1
    assert result.findings[0].imported == "picard.config"
    assert result.findings[0].kind == "import"


def test_import_api_module_itself_is_allowed(tmp_path):
    _write(tmp_path, "m.py", "import picard.plugin3.api\n")
    assert _audit(tmp_path).ok


def test_commented_import_is_not_flagged(tmp_path):
    _write(
        tmp_path,
        "m.py",
        "# from picard.util import make_filename\n"
        "x = 'from picard.ui import NotAnImport'\n"
        "from picard.plugin3.api import Metadata\n",
    )
    assert _audit(tmp_path).ok


def test_type_checking_guarded_import_is_flagged(tmp_path):
    _write(
        tmp_path,
        "m.py",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from picard.ui.util import open_local_path\n",
    )
    result = _audit(tmp_path)
    assert len(result.findings) == 1
    assert result.findings[0].imported == "picard.ui.util.open_local_path"


def test_aliased_and_multiline_import(tmp_path):
    _write(
        tmp_path,
        "m.py",
        "from picard.metadata import (\n    Metadata as M,\n    MULTI_VALUED_JOINER,\n)\n",
    )
    result = _audit(tmp_path)
    imported = {f.imported for f in result.findings}
    assert imported == {"picard.metadata.Metadata", "picard.metadata.MULTI_VALUED_JOINER"}
    # Both reported on the statement's start line.
    assert all(f.line == 1 for f in result.findings)


def test_relative_import_is_not_flagged(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py", "from . import helpers\nfrom .util import thing\n")
    assert _audit(tmp_path).ok


def test_non_picard_import_is_not_flagged(tmp_path):
    _write(tmp_path, "m.py", "import os\nfrom requests import get\n")
    assert _audit(tmp_path).ok


def test_unexported_name_from_api_module_is_flagged(tmp_path):
    # Importing a name that picard.plugin3.api does not export.
    _write(tmp_path, "m.py", "from picard.plugin3.api import Album, SomethingPrivate\n")
    result = _audit(tmp_path)
    assert len(result.findings) == 1
    assert result.findings[0].imported == "picard.plugin3.api.SomethingPrivate"
    assert result.findings[0].severity == SEVERITY_MEDIUM


def test_star_import_from_api_module_is_allowed(tmp_path):
    _write(tmp_path, "m.py", "from picard.plugin3.api import *\n")
    assert _audit(tmp_path).ok


def test_vendored_dirs_are_skipped(tmp_path):
    _write(tmp_path, "__init__.py", "from picard.plugin3.api import Metadata\n")
    _write(tmp_path, "vendor/lib.py", "from picard.ui import Something\n")
    _write(tmp_path, "_vendor/x.py", "import picard.config\n")
    result = _audit(tmp_path)
    assert result.ok
    assert result.files_scanned == 1  # only __init__.py


def test_syntax_error_is_reported_not_crashing(tmp_path):
    _write(tmp_path, "bad.py", "def oops(:\n")
    result = _audit(tmp_path)
    assert not result.ok
    assert len(result.parse_errors) == 1
    assert result.parse_errors[0].file == "bad.py"


def test_util_import_is_low_severity(tmp_path):
    _write(tmp_path, "m.py", "from picard.util import some_helper\n")
    assert _audit(tmp_path).findings[0].severity == SEVERITY_LOW


def test_from_picard_import_log_maps_to_logger(tmp_path):
    # `from picard import log` must classify by the full path picard.log,
    # not the bare module 'picard' (regression: was low/no-suggestion).
    _write(tmp_path, "m.py", "from picard import log\n")
    result = _audit(tmp_path)
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.imported == "picard.log"
    assert f.severity == SEVERITY_MEDIUM
    assert f.suggestion == "use api.logger"


def test_webservice_api_helpers_wins_over_webservice(tmp_path):
    # Most-specific prefix must win.
    _write(tmp_path, "m.py", "from picard.webservice.api_helpers import MBAPIHelper\n")
    f = _audit(tmp_path).findings[0]
    assert f.severity == SEVERITY_MEDIUM
    assert f.suggestion == "use api.mb_api"


def test_summarize_severities(tmp_path):
    _write(
        tmp_path,
        "m.py",
        "from picard.ui import A\n"  # high
        "from picard.metadata import B\n"  # medium
        "from picard.util import C\n",  # low
    )
    result = _audit(tmp_path)
    counts = summarize_severities(result.findings)
    assert counts == {SEVERITY_HIGH: 1, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 1}


@pytest.mark.parametrize(
    "plugin, override, expected",
    [
        ({}, None, None),
        ({}, "v1.2.3", "v1.2.3"),
        ({"refs": [{"name": "master"}]}, None, "master"),
        ({"refs": [{"name": "a"}, {"name": "b"}]}, None, "b"),
        ({"refs": [{"name": "master"}]}, "override", "override"),
    ],
)
def test_resolve_plugin_ref(plugin, override, expected):
    assert resolve_plugin_ref(plugin, override) == expected


# --- Breakage resolution against a Picard source tree ---------------------


def test_picard_source_module_exists(tmp_path):
    source = _picard_tree(
        tmp_path,
        {
            "picard/__init__.py": "",
            "picard/metadata.py": "class Metadata: ...\n",
            "picard/ui/__init__.py": "",
        },
    )
    assert source.module_exists("picard")
    assert source.module_exists("picard.metadata")
    assert source.module_exists("picard.ui")  # package via __init__.py
    assert not source.module_exists("picard.gone")
    assert not source.module_exists("notpicard.x")


def test_picard_source_name_exists(tmp_path):
    source = _picard_tree(
        tmp_path,
        {
            "picard/__init__.py": "import picard.log as log\n",
            "picard/metadata.py": "MULTI_VALUED_JOINER = ';'\nclass Metadata: ...\n",
            "picard/log.py": "def debug(): ...\n",
            "picard/collection/__init__.py": "from picard.collection.base import Collection\n",
            "picard/collection/base.py": "class Collection: ...\n",
        },
    )
    assert source.name_exists("picard.metadata", "Metadata")
    assert source.name_exists("picard.metadata", "MULTI_VALUED_JOINER")
    assert not source.name_exists("picard.metadata", "Removed")
    # Re-exported name in a package __init__.
    assert source.name_exists("picard.collection", "Collection")
    # `from picard import log` where log is a submodule.
    assert source.name_exists("picard", "log")
    # Name in a module that doesn't exist at all.
    assert not source.name_exists("picard.gone", "Anything")


def test_finding_breaks_on_when_module_removed(tmp_path):
    # Plugin imports picard.collection.Collection; our branch dropped the module.
    source = _picard_tree(tmp_path, {"picard/__init__.py": ""})
    result = _audit_plugin(tmp_path, {"__init__.py": "from picard.collection import Collection\n"})
    breaking = breaking_findings(result, source)
    assert len(breaking) == 1
    assert breaking[0].imported == "picard.collection.Collection"


def test_finding_does_not_break_when_still_resolvable(tmp_path):
    # Same import, but the module/name still exists on the branch.
    source = _picard_tree(
        tmp_path,
        {"picard/__init__.py": "", "picard/collection.py": "class Collection: ...\n"},
    )
    result = _audit_plugin(tmp_path, {"__init__.py": "from picard.collection import Collection\n"})
    assert breaking_findings(result, source) == ()


def test_finding_breaks_when_name_removed_but_module_kept(tmp_path):
    source = _picard_tree(
        tmp_path,
        {"picard/__init__.py": "", "picard/metadata.py": "class Metadata: ...\n"},  # OldHelper is gone
    )
    result = _audit_plugin(tmp_path, {"__init__.py": "from picard.metadata import Metadata, OldHelper\n"})
    breaking = breaking_findings(result, source)
    assert {f.imported for f in breaking} == {"picard.metadata.OldHelper"}


def test_plain_import_breaks_when_module_removed(tmp_path):
    source = _picard_tree(tmp_path, {"picard/__init__.py": ""})
    result = _audit_plugin(tmp_path, {"m.py": "import picard.config\n"})
    breaking = breaking_findings(result, source)
    assert len(breaking) == 1
    assert breaking[0].imported == "picard.config"


def test_guarded_import_not_counted_as_breakage(tmp_path):
    # A try/except ImportError fallback: the first import may fail on newer
    # Picard, but the plugin tolerates it. It must not count as breakage.
    source = _picard_tree(
        tmp_path,
        {
            "picard/__init__.py": "",
            "picard/ui/__init__.py": "",
            "picard/ui/util.py": "def open_local_path(): ...\n",
        },
    )
    result = _audit_plugin(
        tmp_path,
        {
            "__init__.py": "try:\n"
            "    from picard.util import open_local_path\n"
            "except ImportError:\n"
            "    from picard.ui.util import open_local_path\n"
        },
    )
    # Both imports are still reported as findings (conformance view)...
    assert len(result.findings) == 2
    # ...but neither counts as a breakage: the guarded one is tolerated and the
    # fallback resolves.
    assert breaking_findings(result, source) == ()


def test_guarded_import_marked_guarded(tmp_path):
    _write(
        tmp_path,
        "m.py",
        "try:\n    import picard.config\nexcept ImportError:\n    picard = None\n",
    )
    result = _audit(tmp_path)
    assert len(result.findings) == 1
    assert result.findings[0].guarded is True


def test_unguarded_import_not_marked_guarded(tmp_path):
    _write(tmp_path, "m.py", "import picard.config\n")
    assert _audit(tmp_path).findings[0].guarded is False


def test_try_catching_other_exception_does_not_guard(tmp_path):
    # A try that only catches something unrelated does NOT make the import optional.
    _write(
        tmp_path,
        "m.py",
        "try:\n    from picard.metadata import Gone\nexcept ValueError:\n    pass\n",
    )
    assert _audit(tmp_path).findings[0].guarded is False


# --- Severity type --------------------------------------------------------


def test_severity_rank_orders_high_first():
    assert Severity.HIGH.rank < Severity.MEDIUM.rank < Severity.LOW.rank


def test_severity_sorts_high_first_natively():
    # rank drives the sort; most concerning comes first.
    ordered = sorted([Severity.LOW, Severity.HIGH, Severity.MEDIUM], key=lambda s: s.rank)
    assert ordered == [Severity.HIGH, Severity.MEDIUM, Severity.LOW]


def test_severity_compares_and_serializes_as_its_label():
    import json

    assert Severity.HIGH == "high"
    assert Severity.HIGH.value == "high"
    assert json.dumps({"s": Severity.HIGH.value}) == '{"s": "high"}'


def test_parse_error_fields():
    err = ParseError(file="a/b.py", message="syntax error: boom")
    assert err.file == "a/b.py"
    assert err.message == "syntax error: boom"


# --- Dynamic imports ------------------------------------------------------


def test_dynamic_importlib_is_flagged(tmp_path):
    _write(tmp_path, "m.py", "import importlib\nx = importlib.import_module('picard.config')\n")
    result = _audit(tmp_path)
    dynamic = [f for f in result.findings if f.kind == "dynamic-import"]
    assert len(dynamic) == 1
    assert dynamic[0].module == "picard.config"
    assert dynamic[0].severity == SEVERITY_MEDIUM


def test_dunder_import_is_flagged(tmp_path):
    _write(tmp_path, "m.py", "m = __import__('picard.metadata')\n")
    result = _audit(tmp_path)
    assert any(f.kind == "dynamic-import" and f.module == "picard.metadata" for f in result.findings)


def test_dynamic_import_of_non_picard_is_ignored(tmp_path):
    _write(tmp_path, "m.py", "import importlib\nimportlib.import_module('os.path')\n")
    assert _audit(tmp_path).ok


def test_dynamic_import_non_literal_is_ignored(tmp_path):
    # A computed module name cannot be resolved statically; out of scope.
    _write(tmp_path, "m.py", "import importlib\nname = 'picard.x'\nimportlib.import_module(name)\n")
    assert _audit(tmp_path).ok


def test_dynamic_import_breaks_when_module_removed(tmp_path):
    source = _picard_tree(tmp_path, {"picard/__init__.py": ""})
    result = _audit_plugin(tmp_path, {"m.py": "import importlib\nimportlib.import_module('picard.gone')\n"})
    breaking = breaking_findings(result, source)
    assert len(breaking) == 1
    assert breaking[0].module == "picard.gone"


# --- Signature / call compatibility ---------------------------------------


def test_signature_issue_unknown_keyword(tmp_path):
    source = _picard_tree(tmp_path, {"picard/__init__.py": "", "picard/util.py": "def helper(path):\n    pass\n"})
    result = _audit_plugin(tmp_path, {"m.py": "from picard.util import helper\nhelper(path='x', mode='old')\n"})
    issues = signature_issues(result, source)
    assert len(issues) == 1
    assert issues[0].callee == "picard.util.helper"
    assert "mode" in issues[0].reason


def test_signature_issue_too_many_positional(tmp_path):
    source = _picard_tree(tmp_path, {"picard/__init__.py": "", "picard/util.py": "def helper(path):\n    pass\n"})
    result = _audit_plugin(tmp_path, {"m.py": "from picard.util import helper\nhelper('a', 'b')\n"})
    issues = signature_issues(result, source)
    assert len(issues) == 1
    assert "at most 1 positional" in issues[0].reason


def test_signature_ok_when_call_matches(tmp_path):
    source = _picard_tree(
        tmp_path, {"picard/__init__.py": "", "picard/util.py": "def helper(path, mode='r'):\n    pass\n"}
    )
    result = _audit_plugin(tmp_path, {"m.py": "from picard.util import helper\nhelper('a', mode='w')\n"})
    assert signature_issues(result, source) == ()


def test_signature_alias_is_traced(tmp_path):
    source = _picard_tree(tmp_path, {"picard/__init__.py": "", "picard/util.py": "def helper(path):\n    pass\n"})
    result = _audit_plugin(tmp_path, {"m.py": "from picard.util import helper as h\nh('a', 'b')\n"})
    issues = signature_issues(result, source)
    assert len(issues) == 1
    assert issues[0].callee == "picard.util.helper"


def test_signature_spread_call_is_skipped(tmp_path):
    # *args / **kwargs at the call site make arity unknown; don't false-positive.
    source = _picard_tree(tmp_path, {"picard/__init__.py": "", "picard/util.py": "def helper(path):\n    pass\n"})
    result = _audit_plugin(tmp_path, {"m.py": "from picard.util import helper\nargs = ['a', 'b']\nhelper(*args)\n"})
    assert signature_issues(result, source) == ()


def test_signature_not_checked_for_non_function(tmp_path):
    # helper resolves to a class, not a plain def: signature check can't apply.
    source = _picard_tree(tmp_path, {"picard/__init__.py": "", "picard/util.py": "class helper:\n    pass\n"})
    result = _audit_plugin(tmp_path, {"m.py": "from picard.util import helper\nhelper('a', 'b', 'c')\n"})
    assert signature_issues(result, source) == ()
