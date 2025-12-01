"""MANIFEST.toml fetching and validation."""

import sys

import requests

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from registry_lib.picard.validator import validate_manifest_dict


def fetch_manifest(git_url, ref="main"):
    """Fetch MANIFEST.toml from git repository.

    Args:
        git_url: Git repository URL (GitHub only)
        ref: Git ref (branch, tag, or commit)

    Returns:
        dict: Parsed MANIFEST.toml content

    Raises:
        ValueError: If URL is not GitHub or manifest is invalid
        requests.HTTPError: If manifest cannot be fetched
    """
    if "github.com" not in git_url:
        raise ValueError(f"Only GitHub URLs are supported: {git_url}")

    # Convert to raw URL
    raw_url = git_url.replace("github.com", "raw.githubusercontent.com")
    raw_url = raw_url.rstrip("/").removesuffix(".git")
    manifest_url = f"{raw_url}/{ref}/MANIFEST.toml"

    response = requests.get(manifest_url, timeout=10)
    response.raise_for_status()

    return tomllib.loads(response.text)


def validate_manifest(manifest):
    """Validate MANIFEST.toml structure.

    Args:
        manifest: Parsed MANIFEST.toml dict

    Raises:
        ValueError: If manifest is invalid
    """
    errors = validate_manifest_dict(manifest)
    if errors:
        raise ValueError(f"Manifest validation failed: {', '.join(errors)}")
