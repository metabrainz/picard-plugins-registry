"""Blacklist operations."""

from datetime import datetime, timezone


def add_blacklist(registry, url, reason):
    """Add URL to blacklist.

    Args:
        registry: Registry instance
        url: Git URL or pattern to blacklist
        reason: Reason for blacklisting

    Returns:
        dict: Blacklist entry
    """
    entry = {
        "url": url,
        "reason": reason,
        "blacklisted_at": datetime.now(timezone.utc).isoformat(),
    }
    registry.add_blacklist(entry)
    return entry
