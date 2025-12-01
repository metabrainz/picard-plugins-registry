"""Registry management."""

import json
from pathlib import Path

from registry_lib.utils import now_iso8601


class Registry:
    """Manages the plugins.json registry file."""

    def __init__(self, path="plugins.json"):
        """Initialize registry.

        Args:
            path: Path to plugins.json file
        """
        self.path = Path(path)
        self.data = self._load()

    def _load(self):
        """Load registry from file or create new."""
        if not self.path.exists():
            return {
                "api_version": "3.0",
                "last_updated": now_iso8601(),
                "plugins": [],
                "blacklist": [],
            }
        try:
            with open(self.path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            # Show context around the error
            with open(self.path) as f:
                lines = f.readlines()

            error_line = e.lineno - 1  # 0-indexed
            start = max(0, error_line - 2)
            end = min(len(lines), error_line + 3)

            context = []
            for i in range(start, end):
                marker = ">>> " if i == error_line else "    "
                context.append(f"{marker}{i + 1}: {lines[i].rstrip()}")

            raise ValueError(
                f"Invalid JSON in {self.path}:\n{e.msg} at line {e.lineno}, column {e.colno}\n\n" + "\n".join(context)
            ) from e

    def save(self):
        """Save registry to file."""
        self.data["last_updated"] = now_iso8601()
        # Sort plugins by ID for consistent ordering
        self.data["plugins"] = sorted(self.data["plugins"], key=lambda p: p["id"])
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def find_plugin(self, plugin_id):
        """Find plugin by ID.

        Args:
            plugin_id: Plugin ID

        Returns:
            dict or None: Plugin entry if found
        """
        for plugin in self.data["plugins"]:
            if plugin["id"] == plugin_id:
                return plugin
        return None

    def add_plugin(self, plugin):
        """Add plugin to registry.

        Args:
            plugin: Plugin dict with all required fields

        Raises:
            ValueError: If plugin already exists
        """
        if self.find_plugin(plugin["id"]):
            raise ValueError(f"Plugin {plugin['id']} already exists")
        self.data["plugins"].append(plugin)

    def remove_plugin(self, plugin_id):
        """Remove plugin from registry.

        Args:
            plugin_id: Plugin ID
        """
        self.data["plugins"] = [p for p in self.data["plugins"] if p["id"] != plugin_id]

    def add_blacklist(self, entry):
        """Add blacklist entry.

        Args:
            entry: Blacklist dict with url and reason
        """
        self.data["blacklist"].append(entry)

    def remove_blacklist(self, url=None, uuid=None):
        """Remove blacklist entry.

        Args:
            url: Git URL to remove (optional)
            uuid: Plugin UUID to remove (optional)
        """
        self.data["blacklist"] = [
            e for e in self.data["blacklist"] if not ((url and e.get("url") == url) or (uuid and e.get("uuid") == uuid))
        ]
