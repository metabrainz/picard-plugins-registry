# Contribution Guidelines for MusicBrainz Picard Plugins

Picard and associated plugins and documentation has been a collaborative effort by volunteer contributors from the very start, and contributions continue to be welcome from anyone in the community.

> [!NOTE]
> The below guidelines and best practices are primarily intended for contributing to plugins maintained officially by the MusicBrainz Picard team. Third-party plugins might follow different guidelines.\
> However, if you are developing a plugin, feel free to follow these guidelines and link to them from your plugin's documentation.

## Contributing

You can help with the development of MusicBrainz Picard plugins by:

- Providing code improvements or bug fixes (e.g. as pull requests on the plugin's GitHub repository).
- Reporting issues or feature requests on the plugin's issue tracker. For official plugins, use the [Picard issue tracker](https://tickets.metabrainz.org/projects/PICARD).
- Help translating the plugins into other languages. If the plugin is listed on [Weblate](https://translations.metabrainz.org/engage/picard-plugins/), you can help translate it there. Otherwise, see the plugin's documentation for instructions on how to translate it.

Please also read the [MetaBrainz Contribution Guidelines](https://github.com/metabrainz/guidelines/blob/master/README.md), specifically the "AI use policy" section, and the [MetaBrainz Code of Conduct](https://metabrainz.org/code-of-conduct) before contributing.

## Technical setup

For local development you first need to clone the plugin's git repository into a local directory. See the plugin's repository page for instructions and the clone URL to use.

> [!NOTE]
> You should not clone the repository directly into Picard's plugin install directory. The plugin directory is managed by Picard. Instead, clone it into a separate development directory and install the plugin as described below.

It is recommended to set up a virtual Python environment for the development of the plugin, e.g. by using [venv](https://docs.python.org/3/library/venv.html).

Inside the plugin directory, create the virtual environment:

```bash
python -m venv .venv
```

To activate the virtual environment, run:

```bash
source .venv/bin/activate
```

On Windows, the virtual environment activation command is slightly different:

```pwsh
.venv\Scripts\activate
```

To install a plugin for development inside Picard, you can install the plugin without git support. This allows testing any code changes directly without the need to commit and push changes. Disabling and enabling the plugin within Picard is enough to have Picard load the changed code again.

Installing the plugin can be done using the `picard-cli` command line tool. From inside the plugin directory, run:

```bash
picard-cli plugins install --no-git .
```

You can also install it from the Picard GUI by navigating to Options → Plugins → Install Plugin… → Local, selecting the plugin directory, activating the "Load in-place (ignore git)" option, and clicking "Install…".

## Code style and formatting

The plugin uses ruff for linting and formatting, and the project provides pre-commit hooks to run these tools automatically before committing changes. To set up the pre-commit hooks, run the following command inside the active virtual environment:

```bash
pip install pre-commit
pre-commit install
```

## Plugin API auto-completion and type checking

Plugins use the MusicBrainz Picard v3 plugin API. Most code editors offer auto-completion and type checking for Python. In order to make use of this for the development of this plugin, install the `picard` package in your virtual environment:

```bash
pip install --pre picard
```
