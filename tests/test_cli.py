"""Tests for CLI module."""

from unittest.mock import patch

import pytest

from registry_lib.cli import main


@patch("sys.argv", ["registry", "--registry", "test.toml", "plugin", "list"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_list(mock_registry):
    """Test plugin list command."""
    mock_registry.return_value.data = {"plugins": [{"id": "test", "name": "Test", "trust_level": "community"}]}

    main()

    mock_registry.assert_called_once_with("test.toml")


@patch("sys.argv", ["registry", "plugin", "list", "--verbose"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_list_verbose(mock_registry):
    """Test plugin list verbose command."""
    mock_registry.return_value.data = {
        "plugins": [
            {
                "id": "test",
                "name": "Test",
                "uuid": "6de6a3bf-a524-42b6-83cb-a36b2ec2e246",
                "description": "Test plugin",
                "git_url": "https://github.com/user/plugin",
                "trust_level": "community",
                "categories": ["metadata"],
                "authors": ["Test Author"],
                "report_bugs_to": "https://github.com/user/plugin/issues",
                "license": "GPL-2.0-or-later",
                "license_url": "https://www.gnu.org/licenses/gpl-2.0.html",
                "homepage": "https://example.com/plugin",
                "added_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            }
        ]
    }

    main()

    # Should print detailed info without errors


@patch("sys.argv", ["registry", "--registry", "test.toml", "blacklist", "list"])
@patch("registry_lib.cli.Registry")
def test_cli_blacklist_list(mock_registry):
    """Test blacklist list command."""
    mock_registry.return_value.data = {"blacklist": [{"url": "https://github.com/bad/plugin", "reason": "Bad"}]}

    main()

    mock_registry.assert_called_once_with("test.toml")


@patch("sys.argv", ["registry", "plugin", "add", "https://github.com/user/plugin", "--trust", "community"])
@patch("registry_lib.cli.add_plugin")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_add(mock_registry, mock_add_plugin):
    """Test plugin add command."""
    mock_add_plugin.return_value = {"id": "plugin", "name": "Plugin"}

    main()

    mock_add_plugin.assert_called_once()
    mock_registry.return_value.save.assert_called_once()


@patch(
    "sys.argv",
    [
        "registry",
        "plugin",
        "add",
        "https://github.com/user/plugin",
        "--trust",
        "community",
        "--versioning-scheme",
        "semver",
    ],
)
@patch("registry_lib.cli.add_plugin")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_add_with_versioning_scheme(mock_registry, mock_add_plugin):
    """Test plugin add command with versioning scheme."""
    mock_add_plugin.return_value = {"id": "plugin", "name": "Plugin"}

    main()

    args = mock_add_plugin.call_args
    assert args[1]["versioning_scheme"] == "semver"
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "plugin", "edit", "test-plugin", "--trust", "official"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_edit(mock_registry):
    """Test plugin edit command."""
    mock_plugin = {"id": "test-plugin", "name": "Test Plugin", "trust_level": "community"}
    mock_registry.return_value.find_plugin.return_value = mock_plugin

    main()

    assert mock_plugin["trust_level"] == "official"
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "plugin", "edit", "test-plugin", "--versioning-scheme", "semver"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_edit_versioning_scheme(mock_registry):
    """Test plugin edit command with versioning scheme."""
    mock_plugin = {"id": "test-plugin", "name": "Test Plugin", "trust_level": "community"}
    mock_registry.return_value.find_plugin.return_value = mock_plugin

    main()

    assert mock_plugin["versioning_scheme"] == "semver"
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "plugin", "edit", "test-plugin", "--versioning-scheme", ""])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_edit_remove_versioning_scheme(mock_registry):
    """Test plugin edit command removing versioning scheme."""
    mock_plugin = {
        "id": "test-plugin",
        "name": "Test Plugin",
        "trust_level": "community",
        "versioning_scheme": "semver",
    }
    mock_registry.return_value.find_plugin.return_value = mock_plugin

    main()

    assert "versioning_scheme" not in mock_plugin
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "plugin", "redirect", "test-plugin", "https://github.com/old/url"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_redirect(mock_registry):
    """Test plugin redirect command."""
    mock_plugin = {"id": "test-plugin", "name": "Test Plugin", "git_url": "https://github.com/new/url"}
    mock_registry.return_value.find_plugin.return_value = mock_plugin

    main()

    assert "redirect_from" in mock_plugin
    assert "https://github.com/old/url" in mock_plugin["redirect_from"]
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "plugin", "redirect", "test-plugin", "https://github.com/old/url", "--remove"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_redirect_remove(mock_registry):
    """Test plugin redirect remove command."""
    mock_plugin = {
        "id": "test-plugin",
        "name": "Test Plugin",
        "git_url": "https://github.com/new/url",
        "redirect_from": ["https://github.com/old/url"],
    }
    mock_registry.return_value.find_plugin.return_value = mock_plugin

    main()

    assert "redirect_from" not in mock_plugin
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "validate"])
@patch("registry_lib.cli.Registry")
def test_cli_validate(mock_registry):
    """Test validate command."""
    mock_registry.return_value.data = {
        "plugins": [{"id": "p1", "uuid": "u1", "git_url": "url1"}],
        "blacklist": [],
    }

    main()

    # Should not raise any errors


@patch("sys.argv", ["registry", "plugin", "show", "test-plugin"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_show(mock_registry):
    """Test plugin show command."""
    mock_plugin = {
        "id": "test-plugin",
        "name": "Test Plugin",
        "uuid": "6de6a3bf-a524-42b6-83cb-a36b2ec2e246",
        "description": "A test plugin",
        "git_url": "https://github.com/user/plugin",
        "trust_level": "community",
        "categories": ["metadata"],
        "authors": ["Test Author"],
        "report_bugs_to": "https://github.com/user/plugin/issues",
        "license": "GPL-2.0-or-later",
        "license_url": "https://www.gnu.org/licenses/gpl-2.0.html",
        "homepage": "https://example.com/plugin",
        "added_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    mock_registry.return_value.find_plugin.return_value = mock_plugin

    main()

    # Should print plugin details without errors


@patch("sys.argv", ["registry", "stats"])
@patch("registry_lib.cli.Registry")
def test_cli_stats(mock_registry):
    """Test stats command."""
    mock_registry.return_value.data = {
        "plugins": [
            {"id": "p1", "trust_level": "official", "categories": ["metadata"]},
            {"id": "p2", "trust_level": "community", "categories": ["metadata", "ui"]},
        ],
        "blacklist": [],
    }

    main()


@patch("sys.argv", ["registry", "output"])
@patch("registry_lib.cli.Registry")
def test_cli_output_toml(mock_registry, capsys):
    """Test output command with TOML format (default)."""
    mock_registry.return_value.data = {
        "api_version": "3.0",
        "plugins": [{"id": "test", "name": "Test"}],
        "blacklist": [],
    }

    main()

    captured = capsys.readouterr()
    assert "api_version = \"3.0\"" in captured.out
    assert "plugins = [" in captured.out
    assert "id = \"test\"" in captured.out


@patch("sys.argv", ["registry", "output", "--format", "json"])
@patch("registry_lib.cli.Registry")
def test_cli_output_json(mock_registry, capsys):
    """Test output command with JSON format."""
    mock_registry.return_value.data = {
        "api_version": "3.0",
        "plugins": [{"id": "test", "name": "Test"}],
        "blacklist": [],
    }

    main()

    captured = capsys.readouterr()
    assert '"api_version": "3.0"' in captured.out
    assert '"plugins"' in captured.out
    assert '"id": "test"' in captured.out

    # Should print stats without errors


@patch("sys.argv", ["registry", "plugin", "update-all"])
@patch("registry_lib.cli.update_all_plugins")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_update_all(mock_registry, mock_update_all):
    """Test plugin update-all saves when there are updates."""
    mock_update_all.return_value = [
        {"id": "p1", "name": "Plugin 1", "status": "updated"},
        {"id": "p2", "name": "Plugin 2", "status": "unchanged"},
    ]

    main()

    mock_update_all.assert_called_once()
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "plugin", "update-all"])
@patch("registry_lib.cli.update_all_plugins")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_update_all_no_changes(mock_registry, mock_update_all):
    """Test plugin update-all does not save when nothing changed."""
    mock_update_all.return_value = [
        {"id": "p1", "name": "Plugin 1", "status": "unchanged"},
    ]

    main()

    mock_registry.return_value.save.assert_not_called()


@patch("sys.argv", ["registry", "plugin", "update-all", "--dry-run"])
@patch("registry_lib.cli.update_all_plugins")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_update_all_dry_run(mock_registry, mock_update_all):
    """Test plugin update-all dry-run never saves."""
    mock_update_all.return_value = [
        {"id": "p1", "name": "Plugin 1", "status": "updated"},
    ]

    main()

    mock_registry.return_value.save.assert_not_called()


@patch("sys.argv", ["registry", "plugin", "update-all"])
@patch("registry_lib.cli.update_all_plugins")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_update_all_failure_exit_code(mock_registry, mock_update_all):
    """Test plugin update-all exits non-zero when a plugin fails."""
    mock_update_all.return_value = [
        {"id": "p1", "name": "Plugin 1", "status": "updated"},
        {"id": "p2", "name": "Plugin 2", "status": "failed", "error": "boom"},
    ]

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    # Updated plugins should still be saved even if another fails
    mock_registry.return_value.save.assert_called_once()


@patch(
    "sys.argv",
    [
        "registry",
        "plugin",
        "set-keys",
        "my-plugin",
        "--key",
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabcDEFghij",
    ],
)
@patch("registry_lib.cli.set_signing_keys")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_set_keys(mock_registry, mock_set_keys):
    """Test plugin set-keys command passes keys to the lib and saves."""
    mock_set_keys.return_value = {
        "id": "my-plugin",
        "name": "My Plugin",
        "signing_keys": ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabcDEFghij"],
    }

    main()

    args, _ = mock_set_keys.call_args
    assert args[1] == "my-plugin"
    assert args[2] == ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabcDEFghij"]
    mock_registry.return_value.save.assert_called_once()


@patch("sys.argv", ["registry", "plugin", "set-keys", "my-plugin", "--clear"])
@patch("registry_lib.cli.set_signing_keys")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_set_keys_clear(mock_registry, mock_set_keys):
    """Test plugin set-keys --clear passes None to the lib."""
    mock_set_keys.return_value = {"id": "my-plugin", "name": "My Plugin"}

    main()

    args, _ = mock_set_keys.call_args
    assert args[2] is None


@patch("sys.argv", ["registry", "plugin", "edit", "my-plugin", "--require-signature"])
@patch("registry_lib.cli.set_require_signature")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_edit_require_signature(mock_registry, mock_set_require):
    """Test plugin edit --require-signature toggles the flag on."""
    plugin = {"id": "my-plugin", "name": "My Plugin"}
    mock_registry.return_value.find_plugin.return_value = plugin

    main()

    args, _ = mock_set_require.call_args
    assert args[1] == "my-plugin"
    assert args[2] is True


@patch("sys.argv", ["registry", "plugin", "edit", "my-plugin", "--no-require-signature"])
@patch("registry_lib.cli.set_require_signature")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_edit_no_require_signature(mock_registry, mock_set_require):
    """Test plugin edit --no-require-signature toggles the flag off."""
    plugin = {"id": "my-plugin", "name": "My Plugin"}
    mock_registry.return_value.find_plugin.return_value = plugin

    main()

    args, _ = mock_set_require.call_args
    assert args[2] is False
