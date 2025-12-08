"""Tests for plugin operations."""

from unittest.mock import patch

import pytest

from registry_lib.plugin import add_plugin
from registry_lib.registry import Registry


@pytest.fixture
def temp_registry(tmp_path):
    """Create temporary registry."""
    return Registry(str(tmp_path / "plugins.toml"))


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_basic(mock_fetch, temp_registry):
    """Test adding a basic plugin."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
        "authors": ["Test Author"],
    }

    plugin = add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    assert plugin["id"] == "test-plugin"
    assert plugin["uuid"] == "12345678-1234-4234-8234-123456789abc"
    assert plugin["name"] == "Test Plugin"
    assert plugin["trust_level"] == "community"
    assert plugin["authors"] == ["Test Author"]
    assert "added_at" in plugin
    assert "updated_at" in plugin


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_with_categories(mock_fetch, temp_registry):
    """Test adding plugin with custom categories."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    plugin = add_plugin(
        temp_registry, "https://github.com/user/test-plugin", "community", categories=["metadata", "coverart"]
    )

    assert plugin["categories"] == ["metadata", "coverart"]


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_with_i18n(mock_fetch, temp_registry):
    """Test adding plugin with translations."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
        "name_i18n": {"de": "Test Plugin DE"},
        "description_i18n": {"de": "Ein Test Plugin"},
    }

    plugin = add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    assert plugin["name_i18n"] == {"de": "Test Plugin DE"}
    assert plugin["description_i18n"] == {"de": "Ein Test Plugin"}


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_with_multi_refs(mock_fetch, temp_registry):
    """Test adding plugin with multiple refs."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    plugin = add_plugin(
        temp_registry, "https://github.com/user/test-plugin", "community", refs="main:4.0,picard-v3:3.0-3.99"
    )

    assert "refs" in plugin
    assert len(plugin["refs"]) == 2
    assert plugin["refs"][0] == {"name": "main", "min_api_version": "4.0"}
    assert plugin["refs"][1] == {"name": "picard-v3", "min_api_version": "3.0", "max_api_version": "3.99"}


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_invalid_trust_level(mock_fetch, temp_registry):
    """Test adding plugin with invalid trust level."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    with pytest.raises(ValueError, match="Invalid trust level"):
        add_plugin(temp_registry, "https://github.com/user/test-plugin", "invalid")


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_duplicate(mock_fetch, temp_registry):
    """Test adding duplicate plugin by URL."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    with pytest.raises(ValueError, match="Plugin with git URL.*already exists"):
        add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_duplicate_uuid(mock_fetch, temp_registry):
    """Test adding plugin with duplicate UUID."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    # Try to add different plugin with same UUID
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Another Plugin",
        "version": "1.0.0",
        "description": "Another plugin",
        "api": ["3.0"],
    }

    with pytest.raises(ValueError, match="Plugin with UUID.*already exists"):
        add_plugin(temp_registry, "https://github.com/user/another-plugin", "community")


@patch("registry_lib.plugin.fetch_manifest")
def test_add_plugin_duplicate_id(mock_fetch, temp_registry):
    """Test adding plugin with duplicate ID (derived from URL)."""
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    # Try to add with different UUID but same derived ID (same URL base)
    mock_fetch.return_value = {
        "uuid": "87654321-4321-4321-8321-cba987654321",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }

    with pytest.raises(ValueError, match="Plugin with ID.*already exists"):
        add_plugin(temp_registry, "https://github.com/user/test-plugin.git", "community")


@patch("registry_lib.plugin.fetch_manifest")
def test_update_plugin(mock_fetch, temp_registry):
    """Test updating plugin metadata."""
    # Add plugin first
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "Old description",
        "api": ["3.0"],
        "authors": ["Old Author"],
    }
    add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    # Update with new manifest
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin Updated",
        "version": "2.0.0",
        "description": "New description",
        "api": ["3.0"],
        "authors": ["New Author"],
    }

    from registry_lib.plugin import update_plugin

    plugin = update_plugin(temp_registry, "test-plugin")

    assert plugin["name"] == "Test Plugin Updated"
    assert plugin["description"] == "New description"
    assert plugin["authors"] == ["New Author"]


@patch("registry_lib.plugin.fetch_manifest")
def test_update_plugin_uuid_changed(mock_fetch, temp_registry):
    """Test that updating plugin with changed UUID raises error."""
    # Add plugin first
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "Test description",
        "api": ["3.0"],
        "authors": ["Test Author"],
    }
    add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    # Try to update with different UUID
    mock_fetch.return_value = {
        "uuid": "87654321-4321-4321-8321-cba987654321",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "Test description",
        "api": ["3.0"],
        "authors": ["Test Author"],
    }

    from registry_lib.plugin import update_plugin

    with pytest.raises(ValueError, match="UUID mismatch.*UUIDs must not change"):
        update_plugin(temp_registry, "test-plugin")


@patch("registry_lib.plugin.fetch_manifest")
def test_update_plugin_invalid_manifest(mock_fetch, temp_registry):
    """Test that updating plugin with invalid manifest raises error."""
    # Add plugin first
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "Test description",
        "api": ["3.0"],
        "authors": ["Test Author"],
    }
    add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    # Try to update with invalid manifest (missing required field)
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        # Missing required 'name' field
        "description": "Test description",
        "api": ["3.0"],
    }

    from registry_lib.plugin import update_plugin

    with pytest.raises(ValueError, match="Manifest validation failed.*Missing required field: name"):
        update_plugin(temp_registry, "test-plugin")


@patch("registry_lib.picard.validator.render_markdown")
@patch("registry_lib.plugin.fetch_manifest")
def test_update_plugin_long_description_with_html(mock_fetch, mock_render_markdown, temp_registry):
    """Test that updating plugin with HTML in long_description raises error and calls render_markdown."""
    # Add plugin first
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "Test description",
        "api": ["3.0"],
    }
    add_plugin(temp_registry, "https://github.com/user/test-plugin", "community")

    # Try to update with HTML in long_description
    mock_fetch.return_value = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "description": "Test description",
        "api": ["3.0"],
        "long_description": "This is a <b>bold</b> description with HTML tags",
    }

    from registry_lib.plugin import update_plugin

    with pytest.raises(ValueError, match="Manifest validation failed.*contains HTML tags"):
        update_plugin(temp_registry, "test-plugin")

    mock_render_markdown.assert_called_once_with(
        "This is a <b>bold</b> description with HTML tags", output_format='html'
    )
