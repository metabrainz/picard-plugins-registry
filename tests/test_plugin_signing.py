"""Tests for plugin signing key operations."""

from unittest.mock import patch

import pytest

from registry_lib.plugin import (
    add_plugin,
    set_require_signature,
    set_signing_keys,
)
from registry_lib.registry import Registry


SSH_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabcDEFghijklmnop maintainer@example"
PGP_KEY = "openpgp:4AC0A7FE37970823F5F4ABDDD859F01B646C07A7"


@pytest.fixture
def temp_registry(tmp_path):
    return Registry(str(tmp_path / "plugins.toml"))


@pytest.fixture
def plugin_id(temp_registry):
    """Add a plugin and return its id."""
    with patch("registry_lib.plugin.fetch_manifest") as mock_fetch:
        mock_fetch.return_value = {
            "uuid": "6de6a3bf-a524-42b6-83cb-a36b2ec2e246",
            "name": "Test Plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "api": ["3.0"],
        }
        plugin = add_plugin(temp_registry, "https://github.com/user/test-plugin", "trusted")
    return plugin["id"]


def test_set_signing_keys_valid(temp_registry, plugin_id):
    plugin = set_signing_keys(temp_registry, plugin_id, [SSH_KEY, PGP_KEY])
    assert plugin["signing_keys"] == [SSH_KEY, PGP_KEY]


def test_set_signing_keys_strips_blank_entries(temp_registry, plugin_id):
    plugin = set_signing_keys(temp_registry, plugin_id, ["  ", SSH_KEY, ""])
    assert plugin["signing_keys"] == [SSH_KEY]


def test_set_signing_keys_rejects_invalid(temp_registry, plugin_id):
    with pytest.raises(ValueError, match="Invalid signing key"):
        set_signing_keys(temp_registry, plugin_id, ["not-a-key"])


def test_set_signing_keys_clear_removes_field(temp_registry, plugin_id):
    set_signing_keys(temp_registry, plugin_id, [SSH_KEY])
    plugin = set_signing_keys(temp_registry, plugin_id, None)
    assert "signing_keys" not in plugin


def test_set_signing_keys_clear_also_drops_require_signature(temp_registry, plugin_id):
    set_signing_keys(temp_registry, plugin_id, [SSH_KEY])
    set_require_signature(temp_registry, plugin_id, True)
    plugin = set_signing_keys(temp_registry, plugin_id, [])
    assert "signing_keys" not in plugin
    assert "require_signature" not in plugin


def test_set_signing_keys_unknown_plugin(temp_registry):
    with pytest.raises(ValueError, match="not found"):
        set_signing_keys(temp_registry, "nope", [SSH_KEY])


def test_require_signature_needs_keys(temp_registry, plugin_id):
    with pytest.raises(ValueError, match="without any signing_keys"):
        set_require_signature(temp_registry, plugin_id, True)


def test_require_signature_enable_then_disable(temp_registry, plugin_id):
    set_signing_keys(temp_registry, plugin_id, [SSH_KEY])
    plugin = set_require_signature(temp_registry, plugin_id, True)
    assert plugin["require_signature"] is True
    plugin = set_require_signature(temp_registry, plugin_id, False)
    assert "require_signature" not in plugin


def test_require_signature_unknown_plugin(temp_registry):
    with pytest.raises(ValueError, match="not found"):
        set_require_signature(temp_registry, "nope", True)
