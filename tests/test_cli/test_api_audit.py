"""Tests for the ``audit-api`` CLI command.

These focus on the command wiring and its resilience: a broken plugin (syntax
error, unreadable file) must not abort the whole run, and an unanalyzable file
must be surfaced as a problem (non-zero exit) rather than a silent pass.
"""

from contextlib import contextmanager
import json
from unittest.mock import patch

import pytest

from registry_lib.cli import main
from registry_lib.picard_api import ApiSurface


# A fixed, offline API surface so these tests never hit the network.
_AUDIT_SURFACE = ApiSurface(ref="test", exported_names=frozenset({"Metadata"}))


def _fake_clone_factory(trees_by_url):
    """Build a clone_tree replacement yielding a prepared tree per git_url."""

    @contextmanager
    def fake_clone(git_url, ref=None, cache_dir=None):
        yield trees_by_url[git_url]

    return fake_clone


def _two_plugins(mock_registry, mock_clone, tmp_path, *, broken_src: str, clean_src: str) -> None:
    """Wire the mocks for a 'broken' then 'clean' plugin with the given sources."""
    trees = {}
    for plugin_id, src in (("broken", broken_src), ("clean", clean_src)):
        root = tmp_path / plugin_id
        root.mkdir()
        (root / "__init__.py").write_text(src, encoding="utf-8")
        trees[f"url://{plugin_id}"] = root
    mock_registry.return_value.data = {
        "plugins": [
            {"id": "broken-plugin", "git_url": "url://broken"},
            {"id": "clean-plugin", "git_url": "url://clean"},
        ]
    }
    mock_clone.side_effect = _fake_clone_factory(trees)


# A syntax error that cannot be parsed, used across the resilience tests.
_BROKEN_SRC = "def oops(:\n"


@patch("sys.argv", ["registry", "audit-api"])
@patch("registry_lib.cli.clone_tree")
@patch("registry_lib.cli.fetch_api_surface", return_value=_AUDIT_SURFACE)
@patch("registry_lib.cli.Registry")
def test_audit_continues_past_plugin_with_syntax_error(mock_registry, _surface, mock_clone, tmp_path, capsys):
    """A plugin whose source has a syntax error is reported, not fatal.

    The audit must still process the following plugin in the same run.
    """
    _two_plugins(
        mock_registry,
        mock_clone,
        tmp_path,
        broken_src=_BROKEN_SRC,
        clean_src="from picard.plugin3.api import Metadata\n",
    )

    # A syntax error in one plugin must not abort the run, but an unanalyzable
    # file is a problem, so the command exits non-zero after processing all.
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1

    out = capsys.readouterr().out
    # Both plugins were processed...
    assert "broken-plugin" in out
    assert "clean-plugin" in out
    # ...the broken file was reported as a failure to analyze (a problem)...
    assert "syntax error" in out
    assert "could not analyze" in out
    # ...and the clean plugin still came out clean.
    assert "clean-plugin: clean" in out


@patch("sys.argv", ["registry", "audit-api", "--json"])
@patch("registry_lib.cli.clone_tree")
@patch("registry_lib.cli.fetch_api_surface", return_value=_AUDIT_SURFACE)
@patch("registry_lib.cli.Registry")
def test_audit_syntax_error_recorded_in_json(mock_registry, _surface, mock_clone, tmp_path, capsys):
    """JSON output records the broken file under parse_errors and keeps going."""
    _two_plugins(mock_registry, mock_clone, tmp_path, broken_src=_BROKEN_SRC, clean_src="x = 1\n")

    with pytest.raises(SystemExit):
        main()

    payload = json.loads(capsys.readouterr().out)
    by_id = {r["plugin_id"]: r for r in payload["results"]}
    assert set(by_id) == {"broken-plugin", "clean-plugin"}
    assert by_id["broken-plugin"]["parse_errors"]
    assert "syntax error" in by_id["broken-plugin"]["parse_errors"][0]["error"]
    # The unparseable file is counted and makes the plugin not-ok.
    assert payload["total_unparsed"] == 1
    assert by_id["broken-plugin"]["ok"] is False


# --- Local path mode (--path): audit a directory without the registry -----


def _local_plugin(tmp_path, source: str):
    root = tmp_path / "myplugin"
    root.mkdir()
    (root / "__init__.py").write_text(source, encoding="utf-8")
    return root


@patch("registry_lib.cli.fetch_api_surface", return_value=_AUDIT_SURFACE)
@patch("registry_lib.cli.Registry")
def test_audit_local_path_conformance(mock_registry, _surface, tmp_path, capsys):
    """--path audits a local dir directly: no registry, no clone."""
    root = _local_plugin(tmp_path, "from picard.metadata import Metadata\n")
    with patch("sys.argv", ["registry", "audit-api", "--path", str(root)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1  # a finding was reported
    out = capsys.readouterr().out
    assert "myplugin" in out
    assert "picard.metadata.Metadata" in out
    # The registry must not be consulted in local-path mode.
    mock_registry.assert_not_called()


@patch("registry_lib.cli.fetch_api_surface", return_value=_AUDIT_SURFACE)
@patch("registry_lib.cli.Registry")
def test_audit_local_path_clean(mock_registry, _surface, tmp_path, capsys):
    """A clean local plugin exits 0."""
    root = _local_plugin(tmp_path, "from picard.plugin3.api import Metadata\n")
    with patch("sys.argv", ["registry", "audit-api", "--path", str(root)]):
        main()  # no SystemExit on a clean result
    assert "clean" in capsys.readouterr().out
    mock_registry.assert_not_called()


@patch("registry_lib.cli.fetch_api_surface", return_value=_AUDIT_SURFACE)
@patch("registry_lib.cli.Registry")
def test_audit_local_path_not_a_directory(mock_registry, _surface, tmp_path, capsys):
    missing = tmp_path / "nope"
    with patch("sys.argv", ["registry", "audit-api", "--path", str(missing)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    assert "not a directory" in capsys.readouterr().err


@patch("registry_lib.cli.fetch_api_surface", return_value=_AUDIT_SURFACE)
@patch("registry_lib.cli.Registry")
def test_audit_path_and_plugin_id_conflict(mock_registry, _surface, tmp_path, capsys):
    root = _local_plugin(tmp_path, "x = 1\n")
    with patch("sys.argv", ["registry", "audit-api", "some-id", "--path", str(root)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    assert "not both" in capsys.readouterr().err
