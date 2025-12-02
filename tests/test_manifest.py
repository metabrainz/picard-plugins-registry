"""Tests for manifest module."""

from unittest.mock import Mock, patch

import pytest

from registry_lib.manifest import fetch_manifest, validate_manifest


@patch("registry_lib.manifest.requests.get")
def test_fetch_manifest_success(mock_get):
    """Test successful manifest fetch."""
    mock_response = Mock()
    mock_response.text = """
uuid = "12345678-1234-4234-8234-123456789abc"
name = "Test Plugin"
version = "1.0.0"
description = "A test plugin"
api = ["3.0"]
"""
    mock_get.return_value = mock_response

    manifest = fetch_manifest("https://github.com/user/plugin", "main")

    assert manifest["uuid"] == "12345678-1234-4234-8234-123456789abc"
    assert manifest["name"] == "Test Plugin"
    mock_get.assert_called_once()


@patch("registry_lib.manifest.requests.get")
def test_fetch_manifest_with_git_suffix(mock_get):
    """Test manifest fetch with .git suffix."""
    mock_response = Mock()
    mock_response.text = """
uuid = "12345678-1234-4234-8234-123456789abc"
name = "Test Plugin"
version = "1.0.0"
description = "A test plugin"
api = ["3.0"]
"""
    mock_get.return_value = mock_response

    fetch_manifest("https://github.com/user/plugin.git", "main")

    # Should strip .git suffix from repo name
    call_url = mock_get.call_args[0][0]
    assert "plugin.git" not in call_url
    assert "plugin/main" in call_url


@patch("registry_lib.manifest.requests.get")
def test_fetch_manifest_gitlab(mock_get):
    """Test successful manifest fetch from GitLab."""
    mock_response = Mock()
    mock_response.text = """
uuid = "12345678-1234-4234-8234-123456789abc"
name = "Test Plugin"
version = "1.0.0"
description = "A test plugin"
api = ["3.0"]
"""
    mock_get.return_value = mock_response

    manifest = fetch_manifest("https://gitlab.com/user/plugin", "main")

    assert manifest["uuid"] == "12345678-1234-4234-8234-123456789abc"
    call_url = mock_get.call_args[0][0]
    assert "gitlab.com/user/plugin/-/raw/main/MANIFEST.toml" in call_url


def test_fetch_manifest_unsupported():
    """Test fetch manifest with unsupported URL."""
    with pytest.raises(ValueError, match="Only GitHub and GitLab URLs are supported"):
        fetch_manifest("https://bitbucket.org/user/plugin")


def test_validate_manifest_valid():
    """Test validation with valid manifest."""
    manifest = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }
    validate_manifest(manifest)  # Should not raise


def test_validate_manifest_invalid():
    """Test validation with invalid manifest."""
    manifest = {
        "uuid": "invalid-uuid",
        "name": "Test Plugin",
    }
    with pytest.raises(ValueError, match="Manifest validation failed"):
        validate_manifest(manifest)
