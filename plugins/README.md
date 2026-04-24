# Foxpilot Local Plugins

This folder is reserved for project-local Foxpilot plugins and examples. Use it for plugin development before a workflow becomes a built-in plugin.

## Status

The plugin registry lives in `src/foxpilot/plugins/`, and the CLI exposes it through `foxpilot plugins ...`. YouTube and GitHub are registered as built-in plugins while still reusing the existing `src/foxpilot/sites/` command apps and service modules.

Built-in plugins should live under:

```text
src/foxpilot/plugins/builtin/
```

Project-local plugins should live under this folder:

```text
plugins/
```

The first built-in plugin targets are `youtube` and `github`.

## Example Layout

```text
plugins/
  examples/
    simple_site/
      plugin.py
      README.md
      tests/
        test_simple_site.py
```

A real local plugin can use the same shape:

```text
plugins/
  my_site/
    plugin.py
    README.md
    service.py
    tests/
      test_my_site.py
```

## Contract

Each plugin should expose a `plugin.py` file with a `register()` function:

```python
from foxpilot.plugins import Plugin


def register(context):
    return Plugin(
        name="my_site",
        help="Automate common My Site browser workflows.",
        cli_app=build_cli_app(context),
        mcp_tools=[],
        docs_path="README.md",
    )
```

Keep plugin code small and put reusable behavior in `service.py` so CLI and MCP adapters can share it.

## Authoring Rules

- Use a short lowercase plugin name such as `youtube`, `github`, or `my_site`.
- Keep browser lifecycle in Foxpilot. A plugin should receive a browser factory or command context instead of creating its own global driver.
- Put parsing, URL building, and result shaping in `service.py`.
- Keep CLI functions thin: parse command options, call service functions, print text or JSON.
- Return structured dictionaries/lists for `--json` paths.
- Include authentication notes in the plugin README when the target site needs cookies, login, or `--zen`.
- Include mode notes for `claude`, `--visible`, `--zen`, and `--headless-mode`.
- Fail with a next action, not just an exception message.

## Minimal `plugin.py`

```python
import typer


def build_cli_app(context):
    app = typer.Typer(help="Example local plugin.")

    @app.command(name="help")
    def help_command():
        typer.echo("foxpilot my-site open https://example.com")

    @app.command(name="open")
    def open_page(url: str):
        with context.browser() as browser:
            browser.driver.get(url)
            typer.echo(browser.driver.current_url)

    return app


def register(context):
    from foxpilot.plugins import Plugin

    return Plugin(
        name="my-site",
        help="Example local plugin.",
        cli_app=build_cli_app(context),
        mcp_tools=[],
        docs_path="README.md",
        source="local",
    )
```

This example uses the current lightweight `foxpilot.plugins.Plugin` dataclass shape.

## README Checklist

Each plugin README should include:

- Command examples.
- Authentication requirements.
- Supported modes.
- JSON output examples.
- Failure modes and next actions.
- Whether the plugin is built-in, local, or experimental.

## Load Failures

The registry skips broken local plugins during normal command use and reports details through plugin diagnostics. A broken local plugin should not prevent built-ins such as `youtube` and `github` from loading.

## Source of Truth

The expansion spec is:

```text
docs/specs/2026-04-24-foxpilot-plugin-expansion-spec.md
```

Current command docs:

```text
docs/commands/youtube.md
docs/commands/github.md
docs/commands/plugins.md
```
