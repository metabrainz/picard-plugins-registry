"""Tests for versioning_scheme feature."""

from unittest.mock import patch

import pytest

from registry_lib.plugin import add_plugin
from registry_lib.registry import Registry


@pytest.fixture
def temp_registry(tmp_path):
    """Create temporary registry."""
    return Registry(str(tmp_path / "plugins.toml"))


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_with_versioning_scheme_semver(mock_fetch, temp_registry):
    """Test adding plugin with semver versioning scheme."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    plugin = add_plugin(
        temp_registry,
        "https://github.com/user/plugin",
        "community",
        versioning_scheme="semver",
    )
    assert plugin["versioning_scheme"] == "semver"


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_with_versioning_scheme_regex(mock_fetch, temp_registry):
    """Test adding plugin with custom regex versioning scheme."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    plugin = add_plugin(
        temp_registry,
        "https://github.com/user/plugin",
        "community",
        versioning_scheme="regex:^version\\d+\\.\\d+\\.\\d+$",
    )
    assert plugin["versioning_scheme"] == "regex:^version\\d+\\.\\d+\\.\\d+$"


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_without_versioning_scheme(mock_fetch, temp_registry):
    """Test adding plugin without versioning scheme."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    plugin = add_plugin(
        temp_registry,
        "https://github.com/user/plugin",
        "community",
    )
    assert "versioning_scheme" not in plugin


@patch("registry_lib.plugin.fetch_manifest")
def test_versioning_scheme_persists_in_registry(mock_fetch, temp_registry, tmp_path):
    """Test that versioning_scheme is saved and loaded correctly."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    add_plugin(
        temp_registry,
        "https://github.com/user/plugin",
        "community",
        versioning_scheme="semver",
    )
    temp_registry.save()

    # Load registry and verify
    registry2 = Registry(str(tmp_path / "plugins.toml"))
    plugin = registry2.find_plugin("plugin")
    assert plugin["versioning_scheme"] == "semver"
