"""Command-line interface."""

import argparse
import json
import sys
from typing import Any

import tomli_w

from registry_lib import colors
from registry_lib.blacklist import add_blacklist
from registry_lib.manifest import (
    fetch_manifest,
    validate_manifest,
)
from registry_lib.picard.constants import REGISTRY_TRUST_LEVELS
from registry_lib.plugin import (
    DEFAULT_REF,
    add_plugin,
    set_require_signature,
    set_signing_keys,
    update_all_plugins,
    update_plugin,
)
from registry_lib.registry import Registry
from registry_lib.utils import now_iso8601


def _format_trust(trust_level: str) -> str:
    """Format trust level with color."""
    if trust_level == "official":
        return colors.green(trust_level)
    elif trust_level == "trusted":
        return colors.yellow(trust_level)
    return trust_level


def _print_plugin_details(plugin: dict[str, Any], indent: str = "") -> None:
    """Print detailed plugin information."""
    print(f"{indent}{colors.dim('ID:')} {colors.cyan(plugin['id'])}")
    print(f"{indent}{colors.dim('Name:')} {colors.bold(plugin['name'])}")
    print(f"{indent}{colors.dim('UUID:')} {plugin['uuid']}")
    print(f"{indent}{colors.dim('Description:')} {plugin['description']}")
    print(f"{indent}{colors.dim('URL:')} {colors.blue(plugin['git_url'])}")
    print(f"{indent}{colors.dim('Trust Level:')} {_format_trust(plugin['trust_level'])}")
    print(f"{indent}{colors.dim('Categories:')} {', '.join(plugin.get('categories', []))}")
    print(f"{indent}{colors.dim('Authors:')} {', '.join(plugin.get('authors', []))}")
    if 'maintainers' in plugin:
        print(f"{indent}{colors.dim('Maintainers:')} {', '.join(plugin['maintainers'])}")
    if 'report_bugs_to' in plugin:
        print(f"{indent}{colors.dim('Report Bugs To:')} {colors.blue(plugin['report_bugs_to'])}")
    if 'license' in plugin:
        print(f"{indent}{colors.dim('License:')} {plugin['license']}")
    if 'license_url' in plugin:
        print(f"{indent}{colors.dim('License URL:')} {colors.blue(plugin['license_url'])}")
    if 'homepage' in plugin:
        print(f"{indent}{colors.dim('Homepage:')} {colors.blue(plugin['homepage'])}")
    if 'long_description' in plugin:
        print(f"{indent}{colors.dim('Long Description:')} ({len(plugin['long_description'])} chars)")
    for lang, text in sorted(plugin.get('long_description_i18n', {}).items()):
        print(f"{indent}{colors.dim(f'Long Description[{lang}]:')} ({len(text)} chars)")
    if 'versioning_scheme' in plugin:
        print(f"{indent}{colors.dim('Versioning Scheme:')} {plugin['versioning_scheme']}")
    if plugin.get('signing_keys'):
        required = plugin.get('require_signature', False)
        suffix = ' (required)' if required else ''
        print(f"{indent}{colors.dim('Signing Keys:')} {len(plugin['signing_keys'])}{suffix}")
    if 'redirect_from' in plugin:
        print(f"{indent}{colors.dim('Redirects from:')} {', '.join(plugin['redirect_from'])}")
    print(f"{indent}{colors.dim('Added:')} {plugin['added_at']}")
    print(f"{indent}{colors.dim('Updated:')} {plugin['updated_at']}")


def get_plugin_or_exit(registry: Registry, plugin_id: str) -> dict[str, Any]:
    """Get plugin from registry or exit with error.

    Args:
        registry: Registry instance
        plugin_id: Plugin ID to find

    Returns:
        dict: Plugin entry
    """
    plugin = registry.find_plugin(plugin_id)
    if not plugin:
        print(f"Error: Plugin {plugin_id} not found", file=sys.stderr)
        sys.exit(1)
    return plugin


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate registry file."""
    registry = Registry(args.registry)
    errors = []

    # Check for duplicate IDs
    ids = [p['id'] for p in registry.data['plugins']]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate plugin IDs found")

    # Check for duplicate UUIDs
    uuids = [p['uuid'] for p in registry.data['plugins']]
    if len(uuids) != len(set(uuids)):
        errors.append("Duplicate plugin UUIDs found")

    # Check for duplicate git URLs
    urls = [p['git_url'] for p in registry.data['plugins']]
    if len(urls) != len(set(urls)):
        errors.append("Duplicate git URLs found")

    if errors:
        for error in errors:
            print(colors.red(f"Error: {error}"), file=sys.stderr)
        sys.exit(1)
    else:
        print(
            colors.green(
                f"✓ Registry valid: {len(registry.data['plugins'])} plugins, {len(registry.data['blacklist'])} blacklist entries"
            )
        )


def cmd_stats(args: argparse.Namespace) -> None:
    """Show registry statistics."""
    registry = Registry(args.registry)
    plugins = registry.data['plugins']

    # Count by trust level
    trust_counts = {}
    for plugin in plugins:
        trust = plugin.get('trust_level', 'unknown')
        trust_counts[trust] = trust_counts.get(trust, 0) + 1

    # Count by category
    category_counts = {}
    for plugin in plugins:
        for cat in plugin.get('categories', []):
            category_counts[cat] = category_counts.get(cat, 0) + 1

    print(f"Total plugins: {colors.bold(str(len(plugins)))}")
    print(f"Blacklist entries: {colors.bold(str(len(registry.data['blacklist'])))}")
    print()
    print(colors.bold("By trust level:"))
    for trust, count in sorted(trust_counts.items()):
        print(f"  {_format_trust(trust)}: {count}")
    print()
    print(colors.bold("By category:"))
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat}: {count}")


def cmd_output(args: argparse.Namespace) -> None:
    """Output registry in specified format."""
    registry = Registry(args.registry)

    if args.format == "json":
        print(json.dumps(registry.data, indent=2, ensure_ascii=False))
    elif args.format == "toml":
        print(tomli_w.dumps(registry.data, multiline_strings=True, indent=2))
    elif args.format == "human":
        plugins = registry.data['plugins']
        blacklist = registry.data['blacklist']

        print(
            f"Registry: {colors.bold(str(len(plugins)))} plugins, {colors.bold(str(len(blacklist)))} blacklist entries\n"
        )
        print("=" * 80)

        for plugin in plugins:
            print()
            _print_plugin_details(plugin, indent="  ")

        if blacklist:
            print("\n" + "=" * 80)
            print(f"\n{colors.bold(f'Blacklist ({len(blacklist)} entries):')}\n")
            for entry in blacklist:
                print(f"• {colors.red(entry.get('git_url', entry.get('uuid', 'Unknown')))}")
                if entry.get('reason'):
                    print(f"  {colors.dim('Reason:')} {entry['reason']}")
                if entry.get('date'):
                    print(f"  {colors.dim('Date:')} {entry['date']}")
                print()
    else:
        print(f"Error: Unknown format '{args.format}'", file=sys.stderr)
        sys.exit(1)


def cmd_display(args: argparse.Namespace) -> None:
    """Display registry in human-readable format."""
    args.format = "human"
    cmd_output(args)


def cmd_plugin_redirect(args: argparse.Namespace) -> None:
    """Add, remove, or list redirects for plugin that moved URLs."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)

    if args.list:
        # List redirects
        redirects = plugin.get('redirect_from', [])
        if not redirects:
            print("No redirects defined")
        else:
            for url in redirects:
                print(f"{url} -> {plugin['git_url']}")
    elif args.remove:
        # Remove URL from redirect_from
        if 'redirect_from' in plugin and args.old_url in plugin['redirect_from']:
            plugin['redirect_from'].remove(args.old_url)
            if not plugin['redirect_from']:
                del plugin['redirect_from']
            plugin["updated_at"] = now_iso8601()
            registry.save()
            print(colors.green(f"Removed redirect: {args.old_url}"))
        else:
            print(f"Error: Redirect {args.old_url} not found", file=sys.stderr)
            sys.exit(1)
    else:
        # Initialize redirect_from if not present
        if 'redirect_from' not in plugin:
            plugin['redirect_from'] = []

        # Add old URL to redirect_from
        if args.old_url not in plugin['redirect_from']:
            plugin['redirect_from'].append(args.old_url)

        plugin["updated_at"] = now_iso8601()
        registry.save()
        print(colors.green(f"Added redirect: {args.old_url} -> {plugin['git_url']}"))


def cmd_plugin_ref_add(args: argparse.Namespace) -> None:
    """Add ref to plugin."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)

    # Initialize refs if not present
    if 'refs' not in plugin:
        plugin['refs'] = []

    # Check if ref already exists
    for ref in plugin['refs']:
        if ref['name'] == args.ref_name:
            print(f"Error: Ref {args.ref_name} already exists", file=sys.stderr)
            sys.exit(1)

    # Build ref entry
    ref = {"name": args.ref_name}
    if args.description:
        ref["description"] = args.description
    if args.min_api_version:
        ref["min_api_version"] = args.min_api_version
    if args.max_api_version:
        ref["max_api_version"] = args.max_api_version

    plugin['refs'].append(ref)
    plugin["updated_at"] = now_iso8601()
    registry.save()
    print(colors.green(f"Added ref: {args.ref_name}"))


def cmd_plugin_ref_edit(args: argparse.Namespace) -> None:
    """Edit ref in plugin."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)

    # Find ref
    ref = None
    for r in plugin.get('refs', []):
        if r['name'] == args.ref_name:
            ref = r
            break

    if not ref:
        print(f"Error: Ref {args.ref_name} not found", file=sys.stderr)
        sys.exit(1)

    # Check if new name conflicts
    if args.new_name and args.new_name != args.ref_name:
        for r in plugin.get('refs', []):
            if r['name'] == args.new_name:
                print(f"Error: Ref {args.new_name} already exists", file=sys.stderr)
                sys.exit(1)
        ref["name"] = args.new_name

    # Update fields
    if args.description is not None:
        if args.description:
            ref["description"] = args.description
        elif "description" in ref:
            del ref["description"]
    if args.min_api_version:
        ref["min_api_version"] = args.min_api_version
    if args.max_api_version:
        ref["max_api_version"] = args.max_api_version

    plugin["updated_at"] = now_iso8601()
    registry.save()
    print(colors.green(f"Updated ref: {args.new_name if args.new_name else args.ref_name}"))


def cmd_plugin_ref_remove(args: argparse.Namespace) -> None:
    """Remove ref from plugin."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)

    if 'refs' not in plugin:
        print("Error: Plugin has no refs", file=sys.stderr)
        sys.exit(1)

    # Remove ref
    original_len = len(plugin['refs'])
    plugin['refs'] = [r for r in plugin['refs'] if r['name'] != args.ref_name]

    if len(plugin['refs']) == original_len:
        print(f"Error: Ref {args.ref_name} not found", file=sys.stderr)
        sys.exit(1)

    # Remove refs field if empty
    if not plugin['refs']:
        del plugin['refs']

    plugin["updated_at"] = now_iso8601()
    registry.save()
    print(colors.green(f"Removed ref: {args.ref_name}"))


def cmd_plugin_ref_list(args: argparse.Namespace) -> None:
    """List refs for plugin."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)

    refs = plugin.get('refs', [])
    if not refs:
        print(f"No refs defined (using default: {DEFAULT_REF})")
        return

    for ref in refs:
        parts = [ref['name']]
        if 'description' in ref:
            parts.append(f"- {ref['description']}")
        if 'min_api_version' in ref or 'max_api_version' in ref:
            min_v = ref.get('min_api_version', '')
            max_v = ref.get('max_api_version', '')
            if min_v and max_v:
                parts.append(f"(API {min_v}-{max_v})")
            elif min_v:
                parts.append(f"(API {min_v}+)")
            elif max_v:
                parts.append(f"(API <={max_v})")
        print(' '.join(parts))


def cmd_plugin_edit(args: argparse.Namespace) -> None:
    """Edit plugin in registry."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)

    # Update fields if provided
    if args.trust:
        plugin["trust_level"] = args.trust
    if args.categories:
        plugin["categories"] = args.categories.split(',')
    if args.git_url:
        plugin["git_url"] = args.git_url
    if args.versioning_scheme is not None:
        if args.versioning_scheme:
            plugin["versioning_scheme"] = args.versioning_scheme
        elif "versioning_scheme" in plugin:
            del plugin["versioning_scheme"]
    if args.require_signature is not None:
        # set_require_signature validates that keys exist before enabling and
        # updates the timestamp itself.
        set_require_signature(registry, args.plugin_id, args.require_signature)

    plugin["updated_at"] = now_iso8601()
    registry.save()
    print(colors.green(f"Updated plugin: {plugin['name']} ({plugin['id']})"))


def cmd_plugin_set_keys(args: argparse.Namespace) -> None:
    """Set or clear the trusted signing keys for a plugin."""
    registry = Registry(args.registry)
    keys = None if args.clear else list(args.key or [])
    plugin = set_signing_keys(registry, args.plugin_id, keys)
    registry.save()
    count = len(plugin.get("signing_keys", []))
    if count:
        print(colors.green(f"Set {count} signing key(s) for {plugin['name']} ({plugin['id']})"))
    else:
        print(colors.green(f"Cleared signing keys for {plugin['name']} ({plugin['id']})"))


def cmd_plugin_validate_manifest(args: argparse.Namespace) -> None:
    """Validate a plugin's MANIFEST.toml without adding to registry."""
    manifest = fetch_manifest(args.source, args.ref, allow_local=True)
    validate_manifest(manifest)
    print(colors.green(f"✓ MANIFEST.toml valid: {manifest['name']} ({manifest['uuid']})"))


def cmd_plugin_add(args: argparse.Namespace) -> None:
    """Add plugin to registry."""
    registry = Registry(args.registry)
    categories = args.categories.split(',') if args.categories else None
    plugin = add_plugin(
        registry, args.url, args.trust, categories=categories, refs=args.refs, versioning_scheme=args.versioning_scheme
    )
    registry.save()
    print(colors.green(f"Added plugin: {plugin['name']} ({plugin['id']})"))


def cmd_plugin_update(args: argparse.Namespace) -> None:
    """Update plugin metadata from MANIFEST."""
    registry = Registry(args.registry)
    plugin = update_plugin(registry, args.plugin_id, ref=args.ref)
    registry.save()
    print(colors.green(f"Updated plugin: {plugin['name']} ({plugin['id']})"))


def cmd_plugin_update_all(args: argparse.Namespace) -> None:
    """Update metadata for all plugins from their MANIFESTs."""
    registry = Registry(args.registry)
    results = update_all_plugins(registry)

    updated = [r for r in results if r["status"] == "updated"]
    unchanged = [r for r in results if r["status"] == "unchanged"]
    failed = [r for r in results if r["status"] == "failed"]

    for result in results:
        if result["status"] == "updated":
            print(colors.green(f"✓ Updated: {result['name']} ({result['id']})"))
        elif result["status"] == "unchanged":
            print(colors.dim(f"- Unchanged: {result['name']} ({result['id']})"))
        else:
            print(colors.red(f"✗ Failed: {result['name']} ({result['id']}): {result['error']}"), file=sys.stderr)

    if args.dry_run:
        print()
        print(colors.yellow("Dry run: no changes were saved."))
    elif updated:
        registry.save()

    print()
    print(
        f"Summary: {colors.green(f'{len(updated)} updated')}, "
        f"{len(unchanged)} unchanged, "
        f"{colors.red(f'{len(failed)} failed') if failed else '0 failed'}"
    )

    if failed:
        sys.exit(1)


def cmd_plugin_remove(args: argparse.Namespace) -> None:
    """Remove plugin from registry."""
    registry = Registry(args.registry)
    registry.remove_plugin(args.plugin_id)
    registry.save()
    print(colors.green(f"Removed plugin: {args.plugin_id}"))


def cmd_plugin_list(args: argparse.Namespace) -> None:
    """List plugins in registry."""
    registry = Registry(args.registry)
    plugins = registry.data["plugins"]

    # Filter by trust level
    if args.trust:
        plugins = [p for p in plugins if p.get("trust_level") == args.trust]

    # Filter by category
    if args.category:
        plugins = [p for p in plugins if args.category in p.get("categories", [])]

    # Sort by ID
    plugins = sorted(plugins, key=lambda p: p["id"])

    for i, plugin in enumerate(plugins):
        if args.verbose:
            if i > 0:
                print()  # Blank line between plugins
            _print_plugin_details(plugin)
        else:
            print(f"{colors.cyan(plugin['id'])}: {plugin['name']} ({_format_trust(plugin['trust_level'])})")


def cmd_plugin_show(args: argparse.Namespace) -> None:
    """Show plugin details."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)
    _print_plugin_details(plugin)


def cmd_blacklist_add(args: argparse.Namespace) -> None:
    """Add entry to blacklist."""
    registry = Registry(args.registry)
    add_blacklist(registry, url=args.url, uuid=args.uuid, url_regex=args.url_regex, reason=args.reason)
    registry.save()
    identifier = args.uuid or args.url or args.url_regex
    print(colors.green(f"Blacklisted: {identifier}"))


def cmd_blacklist_remove(args: argparse.Namespace) -> None:
    """Remove entry from blacklist."""
    registry = Registry(args.registry)
    registry.remove_blacklist(url=args.url, uuid=args.uuid)
    registry.save()
    identifier = args.uuid or args.url
    print(colors.green(f"Removed from blacklist: {identifier}"))


def cmd_blacklist_list(args: argparse.Namespace) -> None:
    """List blacklisted entries."""
    registry = Registry(args.registry)
    for entry in registry.data["blacklist"]:
        identifiers = []
        if "uuid" in entry:
            identifiers.append(f"UUID:{entry['uuid']}")
        if "url" in entry:
            identifiers.append(f"URL:{colors.blue(entry['url'])}")
        if "url_regex" in entry:
            identifiers.append(f"REGEX:{entry['url_regex']}")
        identifier_str = ", ".join(identifiers)
        print(f"{identifier_str}: {entry['reason']}")


def cmd_blacklist_show(args: argparse.Namespace) -> None:
    """Show blacklist entry details."""
    registry = Registry(args.registry)

    # Find entry by URL or UUID
    entry = None
    for e in registry.data["blacklist"]:
        if (args.url and e.get("url") == args.url) or (args.uuid and e.get("uuid") == args.uuid):
            entry = e
            break

    if not entry:
        identifier = args.uuid or args.url
        print(f"Error: Blacklist entry {identifier} not found", file=sys.stderr)
        sys.exit(1)

    # Display entry details
    if "uuid" in entry:
        print(f"{colors.dim('UUID:')} {entry['uuid']}")
    if "url" in entry:
        print(f"{colors.dim('URL:')} {colors.blue(entry['url'])}")
    if "url_regex" in entry:
        print(f"{colors.dim('URL Regex:')} {entry['url_regex']}")
    print(f"{colors.dim('Reason:')} {entry['reason']}")
    print(f"{colors.dim('Blacklisted at:')} {entry['blacklisted_at']}")


def main() -> None:
    """Main CLI entry point."""
    # Ensure utf-8 is used for IO encoding on all platforms. Specifically on Windows
    # this fixes encoding issues during console output in certain cases.
    sys.stdout.reconfigure(encoding="utf-8")  # ty: ignore[unresolved-attribute]
    sys.stderr.reconfigure(encoding="utf-8")  # ty: ignore[unresolved-attribute]

    parser = argparse.ArgumentParser(description="Picard plugins registry maintenance tool")
    parser.add_argument("--registry", default="plugins.toml", help="Path to registry file")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Plugin commands
    plugin_parser = subparsers.add_parser("plugin", help="Plugin operations")
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command", required=True)

    # plugin add
    add_parser = plugin_subparsers.add_parser("add", help="Add plugin")
    add_parser.add_argument("url", help="Git repository URL")
    add_parser.add_argument(
        "--trust",
        default=REGISTRY_TRUST_LEVELS[-1],
        choices=REGISTRY_TRUST_LEVELS,
        help=f"Trust level (default: {REGISTRY_TRUST_LEVELS[-1]})",
    )
    add_parser.add_argument("--categories", help="Plugin categories (comma-separated)")
    add_parser.add_argument(
        "--refs",
        help="Git refs (comma-separated, with optional API versions, e.g., 'main:4.0,picard-v3:3.0-3.99'). Default: main",
    )
    add_parser.add_argument(
        "--versioning-scheme",
        dest="versioning_scheme",
        help="Version tagging scheme: 'semver', 'calver', or 'regex:<pattern>'",
    )
    add_parser.set_defaults(func=cmd_plugin_add)

    # plugin update
    update_parser = plugin_subparsers.add_parser("update", help="Update plugin metadata from MANIFEST")
    update_parser.add_argument("plugin_id", help="Plugin ID")
    update_parser.add_argument("--ref", help="Git ref to fetch MANIFEST from (default: first ref or main)")
    update_parser.set_defaults(func=cmd_plugin_update)

    # plugin update-all
    update_all_parser = plugin_subparsers.add_parser(
        "update-all", help="Update metadata for all plugins from their MANIFESTs"
    )
    update_all_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without saving the registry",
    )
    update_all_parser.set_defaults(func=cmd_plugin_update_all)

    # plugin edit
    edit_parser = plugin_subparsers.add_parser("edit", help="Edit plugin")
    edit_parser.add_argument("plugin_id", help="Plugin ID")
    edit_parser.add_argument("--trust", choices=REGISTRY_TRUST_LEVELS, help="Trust level")
    edit_parser.add_argument("--categories", help="Plugin categories (comma-separated)")
    edit_parser.add_argument("--git-url", help="Git repository URL")
    edit_parser.add_argument(
        "--versioning-scheme",
        dest="versioning_scheme",
        help="Version tagging scheme: 'semver', 'calver', 'regex:<pattern>', or empty string to remove",
    )
    edit_parser.add_argument(
        "--require-signature",
        dest="require_signature",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Require a valid signature to install/update (needs signing_keys); --no-require-signature to disable",
    )
    edit_parser.set_defaults(func=cmd_plugin_edit)

    # plugin set-keys
    set_keys_parser = plugin_subparsers.add_parser(
        "set-keys", help="Set or clear the trusted signing keys for a plugin"
    )
    set_keys_parser.add_argument("plugin_id", help="Plugin ID")
    set_keys_parser.add_argument(
        "--key",
        action="append",
        metavar="KEY",
        help="A trusted signing key ('<ssh-type> <base64-body>' or 'openpgp:<fingerprint>'). "
        "Repeat to set multiple keys.",
    )
    set_keys_parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all signing keys (and require_signature) from the plugin",
    )
    set_keys_parser.set_defaults(func=cmd_plugin_set_keys)

    # plugin redirect
    redirect_parser = plugin_subparsers.add_parser("redirect", help="Manage URL redirects for moved plugin")
    redirect_parser.add_argument("plugin_id", help="Plugin ID")
    redirect_parser.add_argument("old_url", nargs="?", help="Old git URL to redirect from")
    redirect_parser.add_argument("--remove", action="store_true", help="Remove redirect instead of adding")
    redirect_parser.add_argument("--list", action="store_true", help="List all redirects")
    redirect_parser.set_defaults(func=cmd_plugin_redirect)

    # plugin remove
    remove_parser = plugin_subparsers.add_parser("remove", help="Remove plugin")
    remove_parser.add_argument("plugin_id", help="Plugin ID")
    remove_parser.set_defaults(func=cmd_plugin_remove)

    # plugin list
    list_parser = plugin_subparsers.add_parser("list", help="List plugins")
    list_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")
    list_parser.add_argument("--trust", choices=REGISTRY_TRUST_LEVELS, help="Filter by trust level")
    list_parser.add_argument("--category", help="Filter by category")
    list_parser.set_defaults(func=cmd_plugin_list)

    # plugin show
    show_parser = plugin_subparsers.add_parser("show", help="Show plugin details")
    show_parser.add_argument("plugin_id", help="Plugin ID")
    show_parser.set_defaults(func=cmd_plugin_show)

    # plugin validate
    vm_parser = plugin_subparsers.add_parser("validate", help="Validate a plugin's MANIFEST.toml")
    vm_parser.add_argument("source", help="Git repository URL or local path")
    vm_parser.add_argument("--ref", default="main", help="Git ref (default: main)")
    vm_parser.set_defaults(func=cmd_plugin_validate_manifest)

    # Ref commands
    ref_parser = subparsers.add_parser("ref", help="Plugin ref operations")
    ref_subparsers = ref_parser.add_subparsers(dest="ref_command", required=True)

    ref_add_parser = ref_subparsers.add_parser("add", help="Add ref to plugin")
    ref_add_parser.add_argument("plugin_id", help="Plugin ID")
    ref_add_parser.add_argument("ref_name", help="Ref name (e.g., main, develop)")
    ref_add_parser.add_argument("--description", help="Ref description")
    ref_add_parser.add_argument("--min-api-version", help="Minimum API version")
    ref_add_parser.add_argument("--max-api-version", help="Maximum API version")
    ref_add_parser.set_defaults(func=cmd_plugin_ref_add)

    ref_edit_parser = ref_subparsers.add_parser("edit", help="Edit plugin ref")
    ref_edit_parser.add_argument("plugin_id", help="Plugin ID")
    ref_edit_parser.add_argument("ref_name", help="Current ref name")
    ref_edit_parser.add_argument("--name", dest="new_name", help="New ref name")
    ref_edit_parser.add_argument("--description", help="Ref description (empty string to remove)")
    ref_edit_parser.add_argument("--min-api-version", help="Minimum API version")
    ref_edit_parser.add_argument("--max-api-version", help="Maximum API version")
    ref_edit_parser.set_defaults(func=cmd_plugin_ref_edit)

    ref_remove_parser = ref_subparsers.add_parser("remove", help="Remove ref from plugin")
    ref_remove_parser.add_argument("plugin_id", help="Plugin ID")
    ref_remove_parser.add_argument("ref_name", help="Ref name")
    ref_remove_parser.set_defaults(func=cmd_plugin_ref_remove)

    ref_list_parser = ref_subparsers.add_parser("list", help="List plugin refs")
    ref_list_parser.add_argument("plugin_id", help="Plugin ID")
    ref_list_parser.set_defaults(func=cmd_plugin_ref_list)

    # Blacklist commands
    blacklist_parser = subparsers.add_parser("blacklist", help="Blacklist operations")
    blacklist_subparsers = blacklist_parser.add_subparsers(dest="blacklist_command", required=True)

    # blacklist add
    bl_add_parser = blacklist_subparsers.add_parser("add", help="Add to blacklist")
    bl_add_parser.add_argument("--url", help="Git URL to blacklist")
    bl_add_parser.add_argument("--uuid", help="Plugin UUID to blacklist")
    bl_add_parser.add_argument("--url-regex", dest="url_regex", help="URL regex pattern to blacklist")
    bl_add_parser.add_argument("--reason", required=True, help="Reason for blacklisting")
    bl_add_parser.set_defaults(func=cmd_blacklist_add)

    # blacklist remove
    bl_remove_parser = blacklist_subparsers.add_parser("remove", help="Remove from blacklist")
    bl_remove_parser.add_argument("--url", help="Git URL to remove")
    bl_remove_parser.add_argument("--uuid", help="Plugin UUID to remove")
    bl_remove_parser.set_defaults(func=cmd_blacklist_remove)

    # blacklist list
    bl_list_parser = blacklist_subparsers.add_parser("list", help="List blacklist")
    bl_list_parser.set_defaults(func=cmd_blacklist_list)

    # blacklist show
    bl_show_parser = blacklist_subparsers.add_parser("show", help="Show blacklist entry details")
    bl_show_parser.add_argument("--url", help="Git URL")
    bl_show_parser.add_argument("--uuid", help="Plugin UUID")
    bl_show_parser.set_defaults(func=cmd_blacklist_show)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate registry")
    validate_parser.set_defaults(func=cmd_validate)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show registry statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # Output command
    output_parser = subparsers.add_parser("output", help="Output registry in specified format")
    output_parser.add_argument(
        "--format", choices=["json", "toml", "human"], default="toml", help="Output format (default: toml)"
    )
    output_parser.set_defaults(func=cmd_output)

    # Display command (shortcut for output --format human)
    display_parser = subparsers.add_parser("display", help="Display registry in human-readable format")
    display_parser.set_defaults(func=cmd_display)

    args = parser.parse_args()
    colors.init(no_color=args.no_color)
    try:
        args.func(args)
    except Exception as e:
        print(colors.red(f"Error: {e}"), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
