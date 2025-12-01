"""Tests for registry module."""

import pytest

from registry_lib.registry import Registry


@pytest.fixture
def temp_registry(tmp_path):
    """Create temporary registry."""
    registry_path = tmp_path / "plugins.json"
    return Registry(str(registry_path))


def test_registry_init_new(temp_registry):
    """Test creating new registry."""
    assert temp_registry.data["api_version"] == "3.0"
    assert temp_registry.data["plugins"] == []
    assert temp_registry.data["blacklist"] == []
    assert "last_updated" in temp_registry.data


def test_registry_save_and_load(tmp_path):
    """Test saving and loading registry."""
    registry_path = tmp_path / "plugins.json"
    registry = Registry(str(registry_path))

    plugin = {
        "id": "test-plugin",
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "git_url": "https://github.com/user/plugin",
    }
    registry.add_plugin(plugin)
    registry.save()

    # Load in new instance
    registry2 = Registry(str(registry_path))
    assert len(registry2.data["plugins"]) == 1
    assert registry2.data["plugins"][0]["id"] == "test-plugin"

    # Check trailing newline
    content = registry_path.read_text()
    assert content.endswith("\n")


def test_find_plugin(temp_registry):
    """Test finding plugin by ID."""
    plugin = {"id": "test-plugin", "name": "Test"}
    temp_registry.add_plugin(plugin)

    found = temp_registry.find_plugin("test-plugin")
    assert found is not None
    assert found["id"] == "test-plugin"

    not_found = temp_registry.find_plugin("nonexistent")
    assert not_found is None


def test_add_plugin_duplicate(temp_registry):
    """Test adding duplicate plugin."""
    plugin = {"id": "test-plugin", "name": "Test"}
    temp_registry.add_plugin(plugin)

    with pytest.raises(ValueError, match="already exists"):
        temp_registry.add_plugin(plugin)


def test_remove_plugin(temp_registry):
    """Test removing plugin."""
    plugin = {"id": "test-plugin", "name": "Test"}
    temp_registry.add_plugin(plugin)
    assert len(temp_registry.data["plugins"]) == 1

    temp_registry.remove_plugin("test-plugin")
    assert len(temp_registry.data["plugins"]) == 0


def test_add_blacklist(temp_registry):
    """Test adding blacklist entry."""
    entry = {"url": "https://github.com/bad/plugin", "reason": "Malicious"}
    temp_registry.add_blacklist(entry)

    assert len(temp_registry.data["blacklist"]) == 1
    assert temp_registry.data["blacklist"][0]["url"] == "https://github.com/bad/plugin"


def test_remove_blacklist(temp_registry):
    """Test removing blacklist entry."""
    entry = {"url": "https://github.com/bad/plugin", "reason": "Malicious"}
    temp_registry.add_blacklist(entry)
    assert len(temp_registry.data["blacklist"]) == 1

    temp_registry.remove_blacklist("https://github.com/bad/plugin")
    assert len(temp_registry.data["blacklist"]) == 0


def test_load_invalid_json(tmp_path):
    """Test loading invalid JSON shows helpful error."""
    registry_path = tmp_path / "invalid.json"
    registry_path.write_text('{"invalid": json}')

    with pytest.raises(ValueError, match="Invalid JSON"):
        Registry(str(registry_path))
