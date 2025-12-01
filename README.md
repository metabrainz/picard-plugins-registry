# Picard Plugins Registry

Official registry and maintenance tools for MusicBrainz Picard plugins.

## Overview

This repository contains:
- `plugins.json` - The official plugin registry
- `registry` - CLI tool for maintaining the registry
- Validation and testing infrastructure

## Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/metabrainz/picard-plugins-registry.git
cd picard-plugins-registry
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Activate virtual environment
source .venv/bin/activate
```

**Note:** After activating the virtual environment with `source .venv/bin/activate`, you can run `registry` commands directly. All examples below assume the virtual environment is activated. If not activated, prefix commands with `uv run` (e.g., `uv run registry plugin list`).

## Usage

### Add a Plugin

```bash
registry plugin add https://github.com/user/plugin-name \
    --trust community \
    --categories metadata,coverart

# With custom git ref
registry plugin add https://github.com/user/plugin-name \
    --trust community \
    --refs develop

# With multiple refs for different Picard versions
registry plugin add https://github.com/user/plugin-name \
    --trust community \
    --refs 'main:4.0,picard-v3:3.0-3.99'
```

### Update Plugin Metadata

Refresh plugin metadata from MANIFEST.toml:

```bash
# Update from default ref (first ref or main)
registry plugin update plugin-id

# Update from specific ref
registry plugin update plugin-id --ref develop
```

**Note:** The UUID in MANIFEST.toml must match the registry. If it has changed, the update will fail with an error.

### Edit a Plugin

```bash
# Change trust level
registry plugin edit plugin-id --trust official

# Change categories
registry plugin edit plugin-id --categories metadata,ui

# Change git URL (when plugin permanently moves)
registry plugin edit plugin-id --git-url https://github.com/newuser/new-repo

# Change multiple fields
registry plugin edit plugin-id --trust trusted --categories metadata
```

### Add URL Redirect

When a plugin moves to a new repository URL, add a redirect so users with the old URL can still get updates:

```bash
# Add redirect
registry plugin redirect plugin-id https://github.com/olduser/old-repo

# List redirects
registry plugin redirect plugin-id --list

# Remove redirect
registry plugin redirect plugin-id https://github.com/olduser/old-repo --remove
```

### Manage Plugin Refs

Refs allow plugins to support multiple git branches for different Picard versions:

```bash
# Add a ref
registry ref add plugin-id develop \
    --description "Development branch" \
    --min-api-version "4.0"

# Add ref with version range
registry ref add plugin-id picard-v3 \
    --description "Picard 3.x compatible" \
    --min-api-version "3.0" \
    --max-api-version "3.99"

# Edit ref (update description, API versions, or rename)
registry ref edit plugin-id develop --max-api-version "4.99"
registry ref edit plugin-id develop --name beta

# List refs for a plugin
registry ref list plugin-id

# Remove a ref
registry ref remove plugin-id develop
```

### List Plugins

```bash
# Compact list
registry plugin list

# Detailed list (shows all plugin information)
registry plugin list --verbose
```

### Show Plugin Details

```bash
registry plugin show plugin-id
```

### Remove a Plugin

```bash
registry plugin remove plugin-id
```

### Blacklist a Plugin

```bash
# Blacklist by URL
registry blacklist add --url https://github.com/bad/plugin \
    --reason "Contains malicious code"

# Blacklist by UUID (recommended - blocks plugin at all URLs)
registry blacklist add --uuid 12345678-1234-4234-8234-123456789abc \
    --reason "Malicious plugin"

# Blacklist by URL regex (entire organization)
registry blacklist add --url-regex "^https://github\\.com/badorg/.*" \
    --reason "Compromised account"

# Blacklist specific fork (UUID + URL combination)
registry blacklist add \
    --uuid 12345678-1234-4234-8234-123456789abc \
    --url https://github.com/badactor/fork \
    --reason "Malicious fork of legitimate plugin"
```

### Remove from Blacklist

```bash
# Remove by URL
registry blacklist remove --url https://github.com/bad/plugin

# Remove by UUID
registry blacklist remove --uuid 12345678-1234-4234-8234-123456789abc
```

### List Blacklist

```bash
registry blacklist list
```

### Validate Registry

Check registry integrity (duplicate IDs, UUIDs, URLs):

```bash
registry validate
```

### Show Statistics

Display registry statistics by trust level and category:

```bash
registry stats
```

## Trust Levels

- **official** - Maintained by MusicBrainz Picard team
- **trusted** - Well-known authors with established reputation
- **community** - Other plugins (default for new submissions)

## Development

### Run Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=registry_lib

# Specific test file
uv run pytest tests/test_registry.py -v
```

### Code Quality

```bash
# Run ruff checks
uv run ruff check .

# Format code
uv run ruff format .

# Run pre-commit on all files
uv run pre-commit run --all-files
```

## Architecture

- `registry_lib/` - Main package
  - `cli.py` - Command-line interface
  - `registry.py` - Registry file management
  - `plugin.py` - Plugin operations
  - `blacklist.py` - Blacklist operations
  - `manifest.py` - MANIFEST.toml fetching/validation
  - `utils.py` - Utility functions
  - `picard/` - Files copied from Picard (validator, constants)
- `tests/` - Unit tests
- `plugins.json` - The registry file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `uv run pytest` to verify
5. Submit a pull request

All commits must pass pre-commit hooks (ruff format, ruff check, pytest).

## Submitting Your Plugin

Plugin developers can submit their plugins to the registry by creating a pull request:

### Prerequisites

- Your plugin must have a valid `MANIFEST.toml` file in the repository root
- The plugin must be hosted on GitHub (other platforms may be supported in the future)
- Your plugin should follow the [Picard plugin guidelines](https://picard-docs.musicbrainz.org/)

### Submission Process

1. **Fork this repository on GitHub:**
   - Go to https://github.com/metabrainz/picard-plugins-registry
   - Click "Fork" button

2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR-USERNAME/picard-plugins-registry.git
   cd picard-plugins-registry
   ```

3. **Set up the environment:**
   ```bash
   uv sync
   source .venv/bin/activate
   ```

4. **Add your plugin:**
   ```bash
   registry plugin add https://github.com/YOUR-USERNAME/your-plugin \
       --trust community \
       --categories metadata
   ```

   Available categories: `metadata`, `coverart`, `ui`, `scripting`, `formats`, `other`

5. **Validate the registry:**
   ```bash
   registry validate
   ```

6. **Commit and push:**
   ```bash
   git add plugins.json
   git commit -m "Add plugin: Your Plugin Name"
   git push origin main
   ```

7. **Create a pull request:**
   - Go to https://github.com/metabrainz/picard-plugins-registry
   - Click "New Pull Request"
   - Select your fork and branch
   - Describe your plugin in the PR description

7. **Wait for review:**
   - The Picard team will review your submission
   - CI will automatically validate the registry
   - Once approved, your plugin will be available to all Picard users

### Trust Levels

New plugins are added with `community` trust level. After establishing a good track record, plugins may be promoted to `trusted` or `official` status by the Picard team.

## License

GPL-2.0-or-later
