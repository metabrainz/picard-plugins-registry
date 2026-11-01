# Picard Plugins Registry

Official registry and maintenance tools for MusicBrainz Picard plugins (v3).

> **Plugin developers:** Want to submit your plugin? See the **[Plugin Submission Guide](PLUGIN_SUBMISSION.md)**.

> [!NOTE]
> This registry is for Picard v3 plugins only. Legacy v2 plugins are managed through the [old plugin repository](https://github.com/metabrainz/picard-plugins).

## Overview

This repository contains:
- `plugins.toml` - The official plugin registry (DO NOT EDIT MANUALLY)
- `registry` - CLI tool for maintaining the registry (USE THIS)
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

### Git Requirements

For fetching manifests from well-known hosts (GitHub, GitLab, Sourcehut, Codeberg, Bitbucket), no extra dependencies are needed — files are fetched via HTTP.

For other git hosts, one of the following is required:

- **pygit2** (recommended): `uv pip install pygit2` — pure Python, no external tools needed
- **git CLI**: must be available in `PATH`

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

# With semantic versioning (auto-discovers version tags)
registry plugin add https://github.com/user/plugin-name \
    --trust community \
    --versioning-scheme semver

# With custom version pattern
registry plugin add https://github.com/user/plugin-name \
    --trust community \
    --versioning-scheme 'regex:^version\d+\.\d+\.\d+$'
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

### Update All Plugins

Refresh metadata for every registered plugin from their MANIFEST.toml files.
This is useful for catching changes (translations, descriptions, authors, etc.)
that plugin authors forgot to submit. Each plugin is refreshed from its own
default ref (first ref or `main`):

```bash
# Update all plugins (saves only if something changed)
registry plugin update-all

# Preview what would change without saving
registry plugin update-all --dry-run
```

Each plugin is processed independently: a failure on one plugin does not abort
the run. A summary of updated / unchanged / failed plugins is printed at the end,
and the command exits non-zero if any plugin failed. Review the changes with
`git diff plugins.toml` before committing.

### Validate Plugin Manifest

Validate a plugin's MANIFEST.toml without adding it to the registry.
Accepts a remote git URL or a local path (directory or file):

```bash
# Validate from a remote repository (default ref: main)
registry plugin validate https://github.com/user/plugin-name

# Validate from a specific ref
registry plugin validate https://github.com/user/plugin-name --ref develop

# Validate from a local directory (reads MANIFEST.toml from it)
registry plugin validate /path/to/plugin

# Validate a local MANIFEST.toml file directly
registry plugin validate /path/to/MANIFEST.toml
```

### Edit a Plugin

```bash
# Change trust level
registry plugin edit plugin-id --trust official

# Change categories
registry plugin edit plugin-id --categories metadata,ui

# Change git URL (when plugin permanently moves)
registry plugin edit plugin-id --git-url https://github.com/newuser/new-repo

# Add or change versioning scheme
registry plugin edit plugin-id --versioning-scheme semver

# Remove versioning scheme
registry plugin edit plugin-id --versioning-scheme ""

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

# Filter by trust level
registry plugin list --trust official

# Filter by category
registry plugin list --category metadata

# Combine filters
registry plugin list --trust community --category coverart --verbose
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

### Show Blacklist Entry

```bash
# Show details by URL
registry blacklist show --url https://github.com/bad/plugin

# Show details by UUID
registry blacklist show --uuid 12345678-1234-4234-8234-123456789abc
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

### Audit Plugin API Usage

The `audit-api` command answers two different questions, depending on the mode:

- **Conformance (default)** — "Does the plugin obey the documented plugin API?"
  A Picard v3 plugin should import Picard code only from `picard.plugin3.api`;
  importing anything else (`picard.ui.*`, `picard.metadata`,
  `picard.webservice`, …) reaches into Picard internals that may change between
  releases. This mode reports **every** out-of-API import with a severity and a
  suggested API replacement.
- **Breakage (`--check-breakage`)** — "Will the plugin still import on *this*
  Picard branch?" This clones the Picard source at `--picard-ref` and reports
  only the out-of-API imports that **no longer resolve** there. It is the right
  check when validating a Picard refactor (e.g. one that relocates internals)
  against the existing plugin ecosystem: internals that merely *could* break are
  ignored; only imports that actually stopped resolving are flagged. Imports
  inside a `try` / `except ImportError` fallback are treated as intentionally
  optional and never counted as breakage.

The audit clones each plugin, parses its Python with the `ast` module (so
comments, strings, multi-line and `TYPE_CHECKING` imports are handled
correctly).

```bash
# Conformance: audit all plugins against the current Picard API (latest master)
registry audit-api

# Audit a single plugin
registry audit-api additional-artists-details

# Audit against a specific released/tagged Picard version
registry audit-api --picard-ref release-3.0.3

# Breakage: check all plugins against a Picard branch on a fork
registry audit-api --check-breakage \
    --picard-repo myfork/picard --picard-ref my-refactor-branch

# Target a different Picard GitHub repo (owner/repo); default is metabrainz/picard
registry audit-api --picard-repo myfork/picard --picard-ref my-branch

# Override the plugin ref to check out (default: the plugin's declared ref)
registry audit-api my-plugin --ref develop

# Audit a local plugin directory directly, without the registry (during development)
registry audit-api --path ./my-plugin
registry audit-api --path ./my-plugin --check-breakage \
    --picard-repo myfork/picard --picard-ref my-refactor-branch

# Reuse clones between runs (faster for repeated local runs)
registry audit-api --cache-dir ~/.cache/picard-plugin-audit

# Machine-readable report (for CI or further processing)
registry audit-api --json
```

In conformance mode the API surface (the names `picard.plugin3.api` exports) is
fetched from Picard's source for the chosen `--picard-repo` / `--picard-ref`, so
the audit always checks against the real API of that version. In breakage mode
the whole Picard source tree at that ref is cloned and each import is resolved
against it. Both modes exit non-zero when any findings are reported — or when a
plugin file cannot be parsed, since an unanalyzable file is treated as a problem
rather than a silent pass — so they can gate CI.

By default each repository is cloned to a temporary directory and removed after.
Pass `--cache-dir PATH` to keep persistent shallow clones (plugins and, in
breakage mode, the Picard source) and refresh them on reuse, which speeds up
repeated local runs.

To audit a plugin that is not in the registry yet — e.g. while developing it —
pass `--path DIR` to audit a local working directory in place. This skips the
registry and the clone step entirely; `--path` cannot be combined with a plugin
id. Both audit modes work with `--path`, so you can check a work-in-progress
plugin against a specific Picard branch before publishing.

Severities: **high** (`picard.ui.*` and other deep internals), **medium**
(common cases with a documented API replacement, e.g. `picard.webservice` →
`api.web_service`), **low** (other internal imports).

In addition to plain imports, the audit flags **literal dynamic imports**
(`importlib.import_module("picard.x")` / `__import__("picard.x")`), and in
breakage mode it also checks a plugin's **direct calls** of imported Picard
functions against the target signature, reporting a call that passes an unknown
keyword argument or too many positional arguments.

#### Limitations

This is an import/resolution checker, not a full compatibility checker. It is
deliberately conservative — it prefers missing a problem to raising a false
alarm — so a clean breakage report means *"no plugin imports or calls anything
we removed, relocated, or changed the arity of"*, **not** *"no plugin will
break"*. It cannot detect:

- **Type/value changes** of a name that still exists (e.g. a module-level list
  becoming a dict, or a constant changing value) — the import still resolves.
- **Behavioral changes** behind an unchanged signature (different return value,
  a new exception, in-place vs. copy, changed ordering or units).
- **Class member changes** — renamed/removed methods or attributes of a class a
  plugin uses or subclasses; only the top-level class name is tracked.
- **Method-call compatibility** — only direct function calls of an imported
  name are signature-checked, not method calls on instances. Signature checks
  cover only unknown keyword and too-many-positional; "missing required
  argument" is not reported.
- **Non-literal dynamic access** — `importlib.import_module(name)` with a
  computed name, `getattr` on a module, and similar runtime indirection.
- **Non-Python breakage** — manifest/API-version mismatch, resource layout, Qt
  `.ui` changes, config option keys, removed signals/slots.

For behavioral and type-level compatibility, run the plugin's own tests against
the target Picard build.

### Output Registry

Output the registry in a specific format (useful for conversion or piping):

```bash
# Output as TOML (default)
registry output

# Output as JSON
registry output --format json

# Output in human-readable format
registry output --format human

# Convert TOML to JSON
registry output --format json > plugins.json
```

### Display Registry

Shortcut for `registry output --format human` with colorized output:

```bash
registry display
```

### Global Options

```bash
# Disable colored output
registry --no-color <command>
```

Colors are automatically disabled when output is piped or redirected,
or when the `NO_COLOR` environment variable is set.

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

# Type check
uv run ty check

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
- `plugins.toml` - The registry file

## Contributing

For **registry development** (code changes, bug fixes):

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `uv run pytest` to verify
5. Submit a pull request

All commits must pass pre-commit hooks (ruff format, ruff check, ty check, pytest).

For **plugin developers** (submitting, updating, or moving a plugin), see [PLUGIN_SUBMISSION.md](PLUGIN_SUBMISSION.md).

## License

GPL-2.0-or-later
