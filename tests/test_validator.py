"""Tests for copied validator module."""

from registry_lib.picard.validator import validate_manifest_dict


def test_validate_manifest_valid():
    """Test validation with valid manifest."""
    manifest = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }
    errors = validate_manifest_dict(manifest)
    assert errors == []


def test_validate_manifest_missing_required():
    """Test validation with missing required field."""
    manifest = {
        "uuid": "12345678-1234-4234-8234-123456789abc",
        "name": "Test Plugin",
    }
    errors = validate_manifest_dict(manifest)
    assert "Missing required field: description" in errors
    assert "Missing required field: api" in errors


def test_validate_manifest_invalid_uuid():
    """Test validation with invalid UUID."""
    manifest = {
        "uuid": "not-a-uuid",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "api": ["3.0"],
    }
    errors = validate_manifest_dict(manifest)
    assert any("uuid" in e.lower() for e in errors)
