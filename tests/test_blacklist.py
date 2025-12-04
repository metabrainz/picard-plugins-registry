"""Tests for blacklist operations."""

import pytest

from registry_lib.blacklist import add_blacklist
from registry_lib.registry import Registry


@pytest.fixture
def temp_registry(tmp_path):
    """Create temporary registry."""
    return Registry(str(tmp_path / "plugins.toml"))


def test_add_blacklist_by_url(temp_registry):
    """Test adding blacklist entry by URL."""
    entry = add_blacklist(temp_registry, url="https://github.com/bad/plugin", reason="Malicious code")

    assert entry["url"] == "https://github.com/bad/plugin"
    assert entry["reason"] == "Malicious code"
    assert "blacklisted_at" in entry
    assert len(temp_registry.data["blacklist"]) == 1


def test_add_blacklist_by_uuid(temp_registry):
    """Test adding blacklist entry by UUID."""
    entry = add_blacklist(temp_registry, uuid="12345678-1234-4234-8234-123456789abc", reason="Malicious plugin")

    assert entry["uuid"] == "12345678-1234-4234-8234-123456789abc"
    assert entry["reason"] == "Malicious plugin"
    assert "url" not in entry


def test_add_blacklist_by_regex(temp_registry):
    """Test adding blacklist entry by regex."""
    entry = add_blacklist(temp_registry, url_regex="^https://github\\.com/badorg/.*", reason="Compromised organization")

    assert entry["url_regex"] == "^https://github\\.com/badorg/.*"
    assert entry["reason"] == "Compromised organization"


def test_add_blacklist_uuid_and_url(temp_registry):
    """Test adding blacklist entry with both UUID and URL."""
    entry = add_blacklist(
        temp_registry,
        uuid="12345678-1234-4234-8234-123456789abc",
        url="https://github.com/bad/plugin",
        reason="Specific fork is malicious",
    )

    assert entry["uuid"] == "12345678-1234-4234-8234-123456789abc"
    assert entry["url"] == "https://github.com/bad/plugin"


def test_add_blacklist_no_identifier(temp_registry):
    """Test adding blacklist without identifier fails."""
    with pytest.raises(ValueError, match="At least one"):
        add_blacklist(temp_registry, reason="No identifier")


def test_add_blacklist_no_reason(temp_registry):
    """Test adding blacklist without reason fails."""
    with pytest.raises(ValueError, match="Reason is required"):
        add_blacklist(temp_registry, url="https://github.com/bad/plugin")
