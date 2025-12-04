"""Registry management."""

from pathlib import Path

import tomllib


try:
    import tomli_w
except ImportError:
    tomli_w = None


class Registry:
    """Manages the plugins.toml registry file."""

    def __init__(self, path="plugins.toml"):
        """Initialize registry.

        Args:
            path: Path to plugins.toml file
        """
        self.path = Path(path)
        self.data = self._load()

    def _load(self):
        """Load registry from file or create new."""
        if not self.path.exists():
            return {
                "api_version": "3.0",
                "plugins": [],
                "blacklist": [],
            }
        try:
            with open(self.path, "rb") as f:
                data = tomllib.load(f)
                # Ensure blacklist key exists (may be omitted in TOML)
                if "blacklist" not in data:
                    data["blacklist"] = []
                return data
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML in {self.path}: {e}") from e

    def save(self):
        """Save registry to file."""
        if not tomli_w:
            raise RuntimeError("tomli-w is required to save registry")
        # Sort plugins by ID for consistent ordering
        self.data["plugins"] = sorted(self.data["plugins"], key=lambda p: p["id"])

        # Prepare data for saving (remove empty arrays)
        save_data = {"api_version": self.data["api_version"]}
        if self.data.get("plugins"):
            save_data["plugins"] = self.data["plugins"]
        if self.data.get("blacklist"):
            save_data["blacklist"] = self.data["blacklist"]

        with open(self.path, "wb") as f:
            tomli_w.dump(save_data, f, multiline_strings=True, indent=2)

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
        """
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
