"""Plugin operations."""

import re
from typing import Any
import warnings

from registry_lib.manifest import (
    fetch_manifest,
    validate_manifest,
)
from registry_lib.picard.constants import REGISTRY_TRUST_LEVELS
from registry_lib.picard.validator import validate_signing_keys
from registry_lib.registry import Registry
from registry_lib.utils import (
    derive_plugin_id,
    now_iso8601,
)


DEFAULT_REF = "main"

_OPTIONAL_MANIFEST_FIELDS = (
    "description_i18n",
    "homepage",
    "license",
    "license_url",
    "long_description",
    "long_description_i18n",
    "maintainers",
    "name_i18n",
    "report_bugs_to",
)

WHITESPACE_WARNING_RE = re.compile(r'^\n?(\S.*\S)*\S?\n?$', re.DOTALL)


def _strip_field(value: Any, field_name: str, plugin_id: str) -> Any:
    """Strip whitespace from a string value, warning if it differs."""
    if isinstance(value, str):
        # Allow single leading/trailing newline to accommodate docstring type entries
        if not WHITESPACE_WARNING_RE.fullmatch(value):
            warnings.warn(
                f"Plugin '{plugin_id}': field '{field_name}' has leading/trailing whitespace",
                stacklevel=2,
            )
        return value.strip()
    return value


def _sync_optional_fields(plugin: dict[str, Any], manifest: dict[str, Any], fields: tuple[str, ...]) -> None:
    """Sync optional fields from manifest to plugin.

    Args:
        plugin: Plugin dict to update
        manifest: Manifest dict to read from
        fields: List of field names to sync
    """
    plugin_id = plugin["id"]
    for field in fields:
        if field in manifest:
            plugin[field] = _strip_field(manifest[field], field, plugin_id)
        elif field in plugin:
            del plugin[field]


def add_plugin(
    registry: Registry,
    git_url: str,
    trust_level: str,
    categories: list[str] | None = None,
    refs: str | None = None,
    versioning_scheme: str | None = None,
) -> dict[str, Any]:
    """Add plugin to registry.

    Args:
        registry: Registry instance
        git_url: Git repository URL
        trust_level: Trust level (official, trusted, community)
        categories: List of categories (optional)
        refs: Comma-separated refs with optional API versions (e.g., "main:4.0,picard-v3:3.0-3.99")
              or None for default "main"
        versioning_scheme: Version tagging scheme (semver, calver, or regex:<pattern>)

    Returns:
        dict: Added plugin entry

    Raises:
        ValueError: If validation fails or plugin exists
    """
    if trust_level not in REGISTRY_TRUST_LEVELS:
        raise ValueError(f"Invalid trust level: {trust_level}")

    # Parse refs
    if refs:
        refs_list = _parse_refs(refs)
    else:
        refs_list = [{"name": DEFAULT_REF}]

    # Fetch and validate manifest from first ref (default ref)
    manifest = fetch_manifest(git_url, refs_list[0]["name"])
    validate_manifest(manifest)

    # Derive plugin ID
    plugin_id = derive_plugin_id(git_url)

    # Check for duplicates in single pass
    for existing in registry.data["plugins"]:
        if existing["git_url"] == git_url:
            raise ValueError(f"Plugin with git URL '{git_url}' already exists (plugin: {existing['id']})")
        if existing["uuid"] == manifest["uuid"]:
            raise ValueError(f"Plugin with UUID '{manifest['uuid']}' already exists (plugin: {existing['id']})")

    # Check for duplicate ID
    if registry.find_plugin(plugin_id):
        raise ValueError(f"Plugin with ID '{plugin_id}' already exists")

    # Build plugin entry
    now = now_iso8601()
    plugin = {
        "id": plugin_id,
        "uuid": manifest["uuid"],
        "name": _strip_field(manifest["name"], "name", plugin_id),
        "description": _strip_field(manifest["description"], "description", plugin_id),
        "git_url": git_url,
        "categories": categories or manifest.get("categories", []),
        "trust_level": trust_level,
        "authors": manifest.get("authors", []),
        "added_at": now,
        "updated_at": now,
    }

    # Add optional fields
    _sync_optional_fields(plugin, manifest, _OPTIONAL_MANIFEST_FIELDS)

    # Add refs if not default single main
    if not (len(refs_list) == 1 and refs_list[0]["name"] == DEFAULT_REF and "min_api_version" not in refs_list[0]):
        plugin["refs"] = refs_list

    # Add versioning_scheme if provided
    if versioning_scheme:
        plugin["versioning_scheme"] = versioning_scheme

    registry.add_plugin(plugin)
    return plugin


def _parse_refs(refs_str: str) -> list[dict[str, str]]:
    """Parse refs string.

    Formats:
    - "main" - single ref
    - "main,beta" - multiple refs
    - "main:4.0" - ref with min API version
    - "main:4.0-4.99" - ref with min and max API versions
    - "main:4.0,picard-v3:3.0-3.99" - multiple refs with versions

    Args:
        refs_str: Comma-separated refs string

    Returns:
        list: List of ref dicts with name and optional API versions
    """
    refs = []
    for ref_spec in refs_str.split(','):
        ref_spec = ref_spec.strip()
        if ':' in ref_spec:
            # Format: name:api_version or name:min-max
            name, api_spec = ref_spec.split(':', 1)
            ref = {"name": name.strip()}
            if '-' in api_spec:
                min_api, max_api = api_spec.split('-', 1)
                ref["min_api_version"] = min_api.strip()
                ref["max_api_version"] = max_api.strip()
            else:
                ref["min_api_version"] = api_spec.strip()
        else:
            # Simple format: just name
            ref = {"name": ref_spec}
        refs.append(ref)
    return refs


def update_plugin(registry: Registry, plugin_id: str, ref: str | None = None) -> dict[str, Any]:
    """Update plugin metadata from MANIFEST.

    Args:
        registry: Registry instance
        plugin_id: Plugin ID to update
        ref: Git ref to fetch from (optional, defaults to first ref or main)

    Returns:
        dict: Updated plugin entry

    Raises:
        ValueError: If plugin not found, validation fails, or UUID changed
    """
    plugin = registry.find_plugin(plugin_id)
    if not plugin:
        raise ValueError(f"Plugin {plugin_id} not found")

    _apply_manifest_update(plugin, ref)
    return plugin


def set_signing_keys(registry: Registry, plugin_id: str, keys: list[str] | None) -> dict[str, Any]:
    """Set (replace) the trusted signing keys for a plugin.

    Args:
        registry: Registry instance
        plugin_id: Plugin ID to update
        keys: List of signing keys, or None/empty to remove all keys

    Returns:
        dict: Updated plugin entry

    Raises:
        ValueError: If the plugin is not found or any key is malformed
    """
    plugin = registry.find_plugin(plugin_id)
    if not plugin:
        raise ValueError(f"Plugin {plugin_id} not found")

    cleaned = [k.strip() for k in keys if k.strip()] if keys else []
    errors = validate_signing_keys(cleaned)
    if errors:
        raise ValueError(f"Invalid signing key(s): {', '.join(errors)}")

    if cleaned:
        plugin["signing_keys"] = cleaned
    elif "signing_keys" in plugin:
        del plugin["signing_keys"]
        # require_signature is meaningless without keys; drop it too.
        plugin.pop("require_signature", None)

    plugin["updated_at"] = now_iso8601()
    return plugin


def set_require_signature(registry: Registry, plugin_id: str, required: bool) -> dict[str, Any]:
    """Set whether a plugin requires a valid signature to install/update.

    Args:
        registry: Registry instance
        plugin_id: Plugin ID to update
        required: True to require a valid signature, False to only warn

    Returns:
        dict: Updated plugin entry

    Raises:
        ValueError: If the plugin is not found, or require_signature is enabled
            without any signing_keys configured
    """
    plugin = registry.find_plugin(plugin_id)
    if not plugin:
        raise ValueError(f"Plugin {plugin_id} not found")

    if required and not plugin.get("signing_keys"):
        raise ValueError("Cannot require a signature without any signing_keys; add keys first")

    if required:
        plugin["require_signature"] = True
    elif "require_signature" in plugin:
        del plugin["require_signature"]

    plugin["updated_at"] = now_iso8601()
    return plugin


def _apply_manifest_update(plugin: dict[str, Any], ref: str | None = None) -> bool:
    """Fetch the plugin manifest and sync its metadata into the plugin entry.

    Args:
        plugin: Plugin dict to update in place
        ref: Git ref to fetch from (optional, defaults to first ref or main)

    Returns:
        bool: True if any metadata field changed, False otherwise

    Raises:
        ValueError: If validation fails or the UUID changed
    """
    plugin_id = plugin["id"]

    if ref is None:
        refs = plugin.get("refs", None)
        if refs:
            ref = str(refs[0]["name"])
        else:
            ref = DEFAULT_REF

    # Fetch and validate manifest
    manifest = fetch_manifest(plugin["git_url"], ref)
    validate_manifest(manifest)

    # Check UUID hasn't changed
    if manifest["uuid"] != plugin["uuid"]:
        raise ValueError(
            f"UUID mismatch: MANIFEST has {manifest['uuid']} but registry has {plugin['uuid']}. UUIDs must not change."
        )

    # Snapshot the metadata fields (everything except bookkeeping timestamps)
    # so we can detect whether the update actually changed anything.
    before = {k: v for k, v in plugin.items() if k not in ("added_at", "updated_at")}

    # Update fields from manifest
    plugin["name"] = _strip_field(manifest["name"], "name", plugin_id)
    plugin["description"] = _strip_field(manifest["description"], "description", plugin_id)
    plugin["authors"] = manifest.get("authors", [])

    # Update optional fields
    _sync_optional_fields(plugin, manifest, _OPTIONAL_MANIFEST_FIELDS)

    after = {k: v for k, v in plugin.items() if k not in ("added_at", "updated_at")}
    changed = before != after
    if changed:
        plugin["updated_at"] = now_iso8601()

    return changed


def update_all_plugins(registry: Registry) -> list[dict[str, Any]]:
    """Update metadata for every plugin in the registry from their MANIFESTs.

    Each plugin is updated from its own default ref (first ref or main).
    Each plugin is processed independently; a failure on one plugin does not
    abort the run. The registry is mutated in place but not saved — the caller
    is responsible for persisting changes.

    Args:
        registry: Registry instance

    Returns:
        list: One result dict per plugin, each with keys:
            - id: Plugin ID
            - name: Plugin name
            - status: "updated", "unchanged", or "failed"
            - error: Error message (only present when status is "failed")
    """
    results: list[dict[str, Any]] = []
    for plugin in list(registry.data["plugins"]):
        result: dict[str, Any] = {"id": plugin["id"], "name": plugin.get("name", plugin["id"])}
        try:
            changed = _apply_manifest_update(plugin)
            result["status"] = "updated" if changed else "unchanged"
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        results.append(result)
    return results
