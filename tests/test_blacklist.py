"""Tests for blacklist operations."""

import pytest

from registry_lib.blacklist import add_blacklist
from registry_lib.registry import Registry


@pytest.fixture
def temp_registry(tmp_path):
    """Create temporary registry."""
    return Registry(str(tmp_path / "plugins.json"))


def test_add_blacklist_basic(temp_registry):
    """Test adding basic blacklist entry."""
    entry = add_blacklist(temp_registry, "https://github.com/bad/plugin", "Malicious code")

    assert entry["url"] == "https://github.com/bad/plugin"
    assert entry["reason"] == "Malicious code"
    assert "blacklisted_at" in entry
    assert len(temp_registry.data["blacklist"]) == 1


def test_add_blacklist_pattern(temp_registry):
    """Test adding blacklist pattern."""
    entry = add_blacklist(temp_registry, "https://github.com/badorg/*", "Compromised organization")

    assert entry["url"] == "https://github.com/badorg/*"
    assert entry["reason"] == "Compromised organization"
