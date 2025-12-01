"""Tests for CLI ref commands."""

import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from registry_lib.cli import main


def test_cli_ref_add(capsys):
    """Test ref add command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_file = Path(tmpdir) / "plugins.json"
        registry_data = {
            "api_version": "3.0",
            "last_updated": "2025-01-01T00:00:00Z",
            "plugins": [
                {
                    "id": "test-plugin",
                    "uuid": "12345678-1234-4234-8234-123456789abc",
                    "name": "Test Plugin",
                    "description": "A test plugin",
                    "git_url": "https://github.com/user/plugin",
                    "categories": ["metadata"],
                    "trust_level": "community",
                    "authors": ["Test Author"],
                    "added_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                }
            ],
            "blacklist": [],
        }
        registry_file.write_text(json.dumps(registry_data, indent=2))

        with patch(
            "sys.argv",
            [
                "registry",
                "--registry",
                str(registry_file),
                "ref",
                "add",
                "test-plugin",
                "develop",
                "--description",
                "Dev branch",
                "--min-api-version",
                "4.0",
            ],
        ):
            main()

        captured = capsys.readouterr()
        assert "Added ref: develop" in captured.out

        # Verify ref was added
        data = json.loads(registry_file.read_text())
        plugin = data["plugins"][0]
        assert "refs" in plugin
        assert len(plugin["refs"]) == 1
        assert plugin["refs"][0]["name"] == "develop"
        assert plugin["refs"][0]["description"] == "Dev branch"
        assert plugin["refs"][0]["min_api_version"] == "4.0"


def test_cli_ref_edit(capsys):
    """Test ref edit command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_file = Path(tmpdir) / "plugins.json"
        registry_data = {
            "api_version": "3.0",
            "last_updated": "2025-01-01T00:00:00Z",
            "plugins": [
                {
                    "id": "test-plugin",
                    "uuid": "12345678-1234-4234-8234-123456789abc",
                    "name": "Test Plugin",
                    "description": "A test plugin",
                    "git_url": "https://github.com/user/plugin",
                    "categories": ["metadata"],
                    "trust_level": "community",
                    "authors": ["Test Author"],
                    "added_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "refs": [{"name": "develop", "min_api_version": "4.0"}],
                }
            ],
            "blacklist": [],
        }
        registry_file.write_text(json.dumps(registry_data, indent=2))

        with patch(
            "sys.argv",
            [
                "registry",
                "--registry",
                str(registry_file),
                "ref",
                "edit",
                "test-plugin",
                "develop",
                "--max-api-version",
                "4.99",
            ],
        ):
            main()

        captured = capsys.readouterr()
        assert "Updated ref: develop" in captured.out

        # Verify ref was updated
        data = json.loads(registry_file.read_text())
        plugin = data["plugins"][0]
        assert plugin["refs"][0]["max_api_version"] == "4.99"


def test_cli_ref_rename(capsys):
    """Test ref rename via edit command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_file = Path(tmpdir) / "plugins.json"
        registry_data = {
            "api_version": "3.0",
            "last_updated": "2025-01-01T00:00:00Z",
            "plugins": [
                {
                    "id": "test-plugin",
                    "uuid": "12345678-1234-4234-8234-123456789abc",
                    "name": "Test Plugin",
                    "description": "A test plugin",
                    "git_url": "https://github.com/user/plugin",
                    "categories": ["metadata"],
                    "trust_level": "community",
                    "authors": ["Test Author"],
                    "added_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "refs": [{"name": "develop"}],
                }
            ],
            "blacklist": [],
        }
        registry_file.write_text(json.dumps(registry_data, indent=2))

        with patch(
            "sys.argv",
            ["registry", "--registry", str(registry_file), "ref", "edit", "test-plugin", "develop", "--name", "beta"],
        ):
            main()

        captured = capsys.readouterr()
        assert "Updated ref: beta" in captured.out

        # Verify ref was renamed
        data = json.loads(registry_file.read_text())
        plugin = data["plugins"][0]
        assert plugin["refs"][0]["name"] == "beta"


def test_cli_ref_list(capsys):
    """Test ref list command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_file = Path(tmpdir) / "plugins.json"
        registry_data = {
            "api_version": "3.0",
            "last_updated": "2025-01-01T00:00:00Z",
            "plugins": [
                {
                    "id": "test-plugin",
                    "uuid": "12345678-1234-4234-8234-123456789abc",
                    "name": "Test Plugin",
                    "description": "A test plugin",
                    "git_url": "https://github.com/user/plugin",
                    "categories": ["metadata"],
                    "trust_level": "community",
                    "authors": ["Test Author"],
                    "added_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "refs": [
                        {"name": "main", "description": "Main branch", "min_api_version": "4.0"},
                        {
                            "name": "picard-v3",
                            "description": "Picard 3.x",
                            "min_api_version": "3.0",
                            "max_api_version": "3.99",
                        },
                    ],
                }
            ],
            "blacklist": [],
        }
        registry_file.write_text(json.dumps(registry_data, indent=2))

        with patch("sys.argv", ["registry", "--registry", str(registry_file), "ref", "list", "test-plugin"]):
            main()

        captured = capsys.readouterr()
        assert "main - Main branch (API 4.0+)" in captured.out
        assert "picard-v3 - Picard 3.x (API 3.0-3.99)" in captured.out


def test_cli_ref_list_no_refs(capsys):
    """Test ref list command with no refs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_file = Path(tmpdir) / "plugins.json"
        registry_data = {
            "api_version": "3.0",
            "last_updated": "2025-01-01T00:00:00Z",
            "plugins": [
                {
                    "id": "test-plugin",
                    "uuid": "12345678-1234-4234-8234-123456789abc",
                    "name": "Test Plugin",
                    "description": "A test plugin",
                    "git_url": "https://github.com/user/plugin",
                    "categories": ["metadata"],
                    "trust_level": "community",
                    "authors": ["Test Author"],
                    "added_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                }
            ],
            "blacklist": [],
        }
        registry_file.write_text(json.dumps(registry_data, indent=2))

        with patch("sys.argv", ["registry", "--registry", str(registry_file), "ref", "list", "test-plugin"]):
            main()

        captured = capsys.readouterr()
        assert "No refs defined (using default: main)" in captured.out


def test_cli_ref_remove(capsys):
    """Test ref remove command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_file = Path(tmpdir) / "plugins.json"
        registry_data = {
            "api_version": "3.0",
            "last_updated": "2025-01-01T00:00:00Z",
            "plugins": [
                {
                    "id": "test-plugin",
                    "uuid": "12345678-1234-4234-8234-123456789abc",
                    "name": "Test Plugin",
                    "description": "A test plugin",
                    "git_url": "https://github.com/user/plugin",
                    "categories": ["metadata"],
                    "trust_level": "community",
                    "authors": ["Test Author"],
                    "added_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "refs": [{"name": "develop"}],
                }
            ],
            "blacklist": [],
        }
        registry_file.write_text(json.dumps(registry_data, indent=2))

        with patch(
            "sys.argv", ["registry", "--registry", str(registry_file), "ref", "remove", "test-plugin", "develop"]
        ):
            main()

        captured = capsys.readouterr()
        assert "Removed ref: develop" in captured.out

        # Verify ref was removed
        data = json.loads(registry_file.read_text())
        plugin = data["plugins"][0]
        assert "refs" not in plugin
