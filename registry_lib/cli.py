"""Command-line interface."""

import argparse
from datetime import datetime, timezone
import sys

from registry_lib.blacklist import add_blacklist
from registry_lib.plugin import add_plugin, update_plugin
from registry_lib.registry import Registry


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


def cmd_plugin_redirect(args):
    """Add redirect for plugin that moved URLs."""
    registry = Registry(args.registry)
    plugin = registry.find_plugin(args.plugin_id)
    if not plugin:
        print(f"Error: Plugin {args.plugin_id} not found", file=sys.stderr)
        sys.exit(1)

    # Initialize redirect_from if not present
    if 'redirect_from' not in plugin:
        plugin['redirect_from'] = []

    # Add old URL to redirect_from
    if args.old_url not in plugin['redirect_from']:
        plugin['redirect_from'].append(args.old_url)

    plugin["updated_at"] = datetime.now(timezone.utc).isoformat()
    registry.save()
    print(f"Added redirect: {args.old_url} -> {plugin['git_url']}")


def cmd_plugin_edit(args):
    """Edit plugin in registry."""
    registry = Registry(args.registry)
    plugin = registry.find_plugin(args.plugin_id)
    if not plugin:
        print(f"Error: Plugin {args.plugin_id} not found", file=sys.stderr)
        sys.exit(1)

    # Update fields if provided
    if args.trust:
        plugin["trust_level"] = args.trust
    if args.categories:
        plugin["categories"] = args.categories.split(',')

    plugin["updated_at"] = datetime.now(timezone.utc).isoformat()
    registry.save()
    print(f"Updated plugin: {plugin['name']} ({plugin['id']})")


def cmd_plugin_add(args):
    """Add plugin to registry."""
    registry = Registry(args.registry)
    categories = args.categories.split(',') if args.categories else None
    plugin = add_plugin(registry, args.url, args.trust, categories=categories, ref=args.ref)
    registry.save()
    print(f"Added plugin: {plugin['name']} ({plugin['id']})")


def cmd_plugin_update(args):
    """Update plugin metadata from MANIFEST."""
    registry = Registry(args.registry)
    plugin = update_plugin(registry, args.plugin_id)
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
    for plugin in registry.data["plugins"]:
        print(f"{plugin['id']}: {plugin['name']} ({plugin['trust_level']})")


def cmd_plugin_show(args):
    """Show plugin details."""
    registry = Registry(args.registry)
    plugin = registry.find_plugin(args.plugin_id)
    if not plugin:
        print(f"Error: Plugin {args.plugin_id} not found", file=sys.stderr)
        sys.exit(1)

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


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Picard plugins registry maintenance tool")
    parser.add_argument("--registry", default="plugins.json", help="Path to registry file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Plugin commands
    plugin_parser = subparsers.add_parser("plugin", help="Plugin operations")
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command", required=True)

    # plugin add
    add_parser = plugin_subparsers.add_parser("add", help="Add plugin")
    add_parser.add_argument("url", help="Git repository URL")
    add_parser.add_argument("--trust", required=True, choices=["official", "trusted", "community"], help="Trust level")
    add_parser.add_argument("--categories", help="Plugin categories (comma-separated)")
    add_parser.add_argument("--ref", default="main", help="Git ref (default: main)")
    add_parser.set_defaults(func=cmd_plugin_add)

    # plugin update
    update_parser = plugin_subparsers.add_parser("update", help="Update plugin metadata from MANIFEST")
    update_parser.add_argument("plugin_id", help="Plugin ID")
    update_parser.set_defaults(func=cmd_plugin_update)

    # plugin edit
    edit_parser = plugin_subparsers.add_parser("edit", help="Edit plugin")
    edit_parser.add_argument("plugin_id", help="Plugin ID")
    edit_parser.add_argument("--trust", choices=["official", "trusted", "community"], help="Trust level")
    edit_parser.add_argument("--categories", help="Plugin categories (comma-separated)")
    edit_parser.set_defaults(func=cmd_plugin_edit)

    # plugin redirect
    redirect_parser = plugin_subparsers.add_parser("redirect", help="Add URL redirect for moved plugin")
    redirect_parser.add_argument("plugin_id", help="Plugin ID")
    redirect_parser.add_argument("old_url", help="Old git URL to redirect from")
    redirect_parser.set_defaults(func=cmd_plugin_redirect)

    # plugin remove
    remove_parser = plugin_subparsers.add_parser("remove", help="Remove plugin")
    remove_parser.add_argument("plugin_id", help="Plugin ID")
    remove_parser.set_defaults(func=cmd_plugin_remove)

    # plugin list
    list_parser = plugin_subparsers.add_parser("list", help="List plugins")
    list_parser.set_defaults(func=cmd_plugin_list)

    # plugin show
    show_parser = plugin_subparsers.add_parser("show", help="Show plugin details")
    show_parser.add_argument("plugin_id", help="Plugin ID")
    show_parser.set_defaults(func=cmd_plugin_show)

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

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate registry")
    validate_parser.set_defaults(func=cmd_validate)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show registry statistics")
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
