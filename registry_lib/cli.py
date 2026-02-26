"""Command-line interface."""

import argparse
import sys

from registry_lib.blacklist import add_blacklist
from registry_lib.picard.constants import REGISTRY_TRUST_LEVELS
from registry_lib.plugin import DEFAULT_REF, add_plugin, update_plugin
from registry_lib.registry import Registry
from registry_lib.utils import now_iso8601


def get_plugin_or_exit(registry, plugin_id):
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


def cmd_validate(args):
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
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    else:
        print(
            f"✓ Registry valid: {len(registry.data['plugins'])} plugins, {len(registry.data['blacklist'])} blacklist entries"
        )


def cmd_stats(args):
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

    print(f"Total plugins: {len(plugins)}")
    print(f"Blacklist entries: {len(registry.data['blacklist'])}")
    print()
    print("By trust level:")
    for trust, count in sorted(trust_counts.items()):
        print(f"  {trust}: {count}")
    print()
    print("By category:")
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat}: {count}")


def cmd_output(args):
    """Output registry in specified format."""
    import json

    import tomli_w

    registry = Registry(args.registry)

    if args.format == "json":
        print(json.dumps(registry.data, indent=2, ensure_ascii=False))
    elif args.format == "toml":
        print(tomli_w.dumps(registry.data, multiline_strings=True, indent=2))
    elif args.format == "human":
        plugins = registry.data['plugins']
        blacklist = registry.data['blacklist']

        print(f"Registry: {len(plugins)} plugins, {len(blacklist)} blacklist entries\n")
        print("=" * 80)

        for plugin in plugins:
            print(f"\n• {plugin['id']}")
            print(f"  Name: {plugin.get('name', 'N/A')}")
            print(f"  UUID: {plugin['uuid']}")
            print(f"  URL: {plugin['git_url']}")
            print(f"  Trust: {plugin.get('trust_level', 'unknown')}")
            if plugin.get('description'):
                print(f"  Description: {plugin['description']}")
            if plugin.get('categories'):
                print(f"  Categories: {', '.join(plugin['categories'])}")
            if plugin.get('authors'):
                print(f"  Authors: {', '.join(plugin['authors'])}")
            if plugin.get('maintainers'):
                print(f"  Maintainers: {', '.join(plugin['maintainers'])}")
            if plugin.get('license'):
                print(f"  License: {plugin['license']}")
            if plugin.get('redirects'):
                print(f"  Redirects: {', '.join(plugin['redirects'])}")
            if plugin.get('refs'):
                print(f"  Refs ({len(plugin['refs'])}):")
                for ref in plugin['refs']:
                    print(f"    - {ref['ref']}: {ref['commit']}")

        if blacklist:
            print("\n" + "=" * 80)
            print(f"\nBlacklist ({len(blacklist)} entries):\n")
            for entry in blacklist:
                print(f"• {entry.get('git_url', entry.get('uuid', 'Unknown'))}")
                if entry.get('reason'):
                    print(f"  Reason: {entry['reason']}")
                if entry.get('date'):
                    print(f"  Date: {entry['date']}")
                print()
    else:
        print(f"Error: Unknown format '{args.format}'", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_redirect(args):
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
            print(f"Removed redirect: {args.old_url}")
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
        print(f"Added redirect: {args.old_url} -> {plugin['git_url']}")


def cmd_plugin_ref_add(args):
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
    print(f"Added ref: {args.ref_name}")


def cmd_plugin_ref_edit(args):
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
    print(f"Updated ref: {args.new_name if args.new_name else args.ref_name}")


def cmd_plugin_ref_remove(args):
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
    print(f"Removed ref: {args.ref_name}")


def cmd_plugin_ref_list(args):
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


def cmd_plugin_edit(args):
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

    plugin["updated_at"] = now_iso8601()
    registry.save()
    print(f"Updated plugin: {plugin['name']} ({plugin['id']})")


def cmd_plugin_add(args):
    """Add plugin to registry."""
    registry = Registry(args.registry)
    categories = args.categories.split(',') if args.categories else None
    plugin = add_plugin(
        registry, args.url, args.trust, categories=categories, refs=args.refs, versioning_scheme=args.versioning_scheme
    )
    registry.save()
    print(f"Added plugin: {plugin['name']} ({plugin['id']})")


def cmd_plugin_update(args):
    """Update plugin metadata from MANIFEST."""
    registry = Registry(args.registry)
    plugin = update_plugin(registry, args.plugin_id, ref=args.ref)
    registry.save()
    print(f"Updated plugin: {plugin['name']} ({plugin['id']})")


def cmd_plugin_remove(args):
    """Remove plugin from registry."""
    registry = Registry(args.registry)
    registry.remove_plugin(args.plugin_id)
    registry.save()
    print(f"Removed plugin: {args.plugin_id}")


def cmd_plugin_list(args):
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
            print(f"ID: {plugin['id']}")
            print(f"Name: {plugin['name']}")
            print(f"UUID: {plugin['uuid']}")
            print(f"Description: {plugin['description']}")
            print(f"URL: {plugin['git_url']}")
            print(f"Trust Level: {plugin['trust_level']}")
            print(f"Categories: {', '.join(plugin.get('categories', []))}")
            print(f"Authors: {', '.join(plugin.get('authors', []))}")
            if 'maintainers' in plugin:
                print(f"Maintainers: {', '.join(plugin['maintainers'])}")
            if 'versioning_scheme' in plugin:
                print(f"Versioning Scheme: {plugin['versioning_scheme']}")
            if 'redirect_from' in plugin:
                print(f"Redirects from: {', '.join(plugin['redirect_from'])}")
            print(f"Added: {plugin['added_at']}")
            print(f"Updated: {plugin['updated_at']}")
        else:
            print(f"{plugin['id']}: {plugin['name']} ({plugin['trust_level']})")


def cmd_plugin_show(args):
    """Show plugin details."""
    registry = Registry(args.registry)
    plugin = get_plugin_or_exit(registry, args.plugin_id)

    print(f"ID: {plugin['id']}")
    print(f"Name: {plugin['name']}")
    print(f"UUID: {plugin['uuid']}")
    print(f"Description: {plugin['description']}")
    print(f"URL: {plugin['git_url']}")
    print(f"Trust Level: {plugin['trust_level']}")
    print(f"Categories: {', '.join(plugin.get('categories', []))}")
    print(f"Authors: {', '.join(plugin.get('authors', []))}")
    if 'maintainers' in plugin:
        print(f"Maintainers: {', '.join(plugin['maintainers'])}")
    if 'versioning_scheme' in plugin:
        print(f"Versioning Scheme: {plugin['versioning_scheme']}")
    if 'redirect_from' in plugin:
        print(f"Redirects from: {', '.join(plugin['redirect_from'])}")
    print(f"Added: {plugin['added_at']}")
    print(f"Updated: {plugin['updated_at']}")


def cmd_blacklist_add(args):
    """Add entry to blacklist."""
    registry = Registry(args.registry)
    add_blacklist(registry, url=args.url, uuid=args.uuid, url_regex=args.url_regex, reason=args.reason)
    registry.save()
    identifier = args.uuid or args.url or args.url_regex
    print(f"Blacklisted: {identifier}")


def cmd_blacklist_remove(args):
    """Remove entry from blacklist."""
    registry = Registry(args.registry)
    registry.remove_blacklist(url=args.url, uuid=args.uuid)
    registry.save()
    identifier = args.uuid or args.url
    print(f"Removed from blacklist: {identifier}")


def cmd_blacklist_list(args):
    """List blacklisted entries."""
    registry = Registry(args.registry)
    for entry in registry.data["blacklist"]:
        identifiers = []
        if "uuid" in entry:
            identifiers.append(f"UUID:{entry['uuid']}")
        if "url" in entry:
            identifiers.append(f"URL:{entry['url']}")
        if "url_regex" in entry:
            identifiers.append(f"REGEX:{entry['url_regex']}")
        identifier_str = ", ".join(identifiers)
        print(f"{identifier_str}: {entry['reason']}")


def cmd_blacklist_show(args):
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
        print(f"UUID: {entry['uuid']}")
    if "url" in entry:
        print(f"URL: {entry['url']}")
    if "url_regex" in entry:
        print(f"URL Regex: {entry['url_regex']}")
    print(f"Reason: {entry['reason']}")
    print(f"Blacklisted at: {entry['blacklisted_at']}")


def main():
    """Main CLI entry point."""
    # Ensure utf-8 is used for IO encoding on all platforms. Specifically on Windows
    # this fixes encoding issues during console output in certain cases.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Picard plugins registry maintenance tool")
    parser.add_argument("--registry", default="plugins.toml", help="Path to registry file")

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
    edit_parser.set_defaults(func=cmd_plugin_edit)

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

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
