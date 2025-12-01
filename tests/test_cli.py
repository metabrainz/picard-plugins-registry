"""Tests for CLI module."""

from unittest.mock import patch

from registry_lib.cli import main


@patch("sys.argv", ["registry", "--registry", "test.json", "plugin", "list"])
@patch("registry_lib.cli.Registry")
def test_cli_plugin_list(mock_registry):
    """Test plugin list command."""
    mock_registry.return_value.data = {"plugins": [{"id": "test", "name": "Test", "trust_level": "community"}]}

    main()

    mock_registry.assert_called_once_with("test.json")


@patch("sys.argv", ["registry", "--registry", "test.json", "blacklist", "list"])
@patch("registry_lib.cli.Registry")
def test_cli_blacklist_list(mock_registry):
    """Test blacklist list command."""
    mock_registry.return_value.data = {"blacklist": [{"url": "https://github.com/bad/plugin", "reason": "Bad"}]}

    main()

    mock_registry.assert_called_once_with("test.json")


@patch("sys.argv", ["registry", "plugin", "add", "https://github.com/user/plugin", "--trust", "community"])
@patch("registry_lib.cli.add_plugin")
@patch("registry_lib.cli.Registry")
def test_cli_plugin_add(mock_registry, mock_add_plugin):
    """Test plugin add command."""
    mock_add_plugin.return_value = {"id": "plugin", "name": "Plugin"}

    main()

    mock_add_plugin.assert_called_once()
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
