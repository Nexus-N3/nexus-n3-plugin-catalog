# nexus-n3-plugin-catalog

User-facing catalog of Nexus N3 sensor and algorithm plugins.

This repository is the shared plugin workspace for Nexus N3 systems. It keeps plugin source repositories in one place, alongside optional built `.rsnxplugin` bundles created locally during development and release workflows.

## What This Repository Is For

Use this repository when you want to:

- browse the available Nexus N3 plugins
- develop or update a sensor plugin
- develop or update an algorithm plugin
- build plugin bundles for local testing or deployment
- keep a consistent plugin catalog layout across teams and environments

This repository is not the plugin CLI itself, and it is not the runtime host.

Nexus N3 plugins can be developed, tested, and bundled publicly from this repository together with `nexus-n3-plugin-tooling`.

Deployment and runtime installation are currently provided separately.

Related repositories:

- `nexus-n3-plugin-tooling`
  Provides the `nexus-n3-plugin` CLI, SDK, scaffolding, validation, and bundle build workflow.
- `nexus-n3-core`
  Provides separately managed runtime installation, plugin discovery, and runtime execution.

## Repository Layout

The catalog is organized around source areas for plugins, plus an optional local build output area:

```text
nexus-n3-plugin-catalog/
  sensors/
  algorithms/
  plugin-builds/
    sensors/
    algorithms/
```

Meaning:

- `sensors/`
  Source repositories for sensor plugins.
- `algorithms/`
  Source repositories for algorithm plugins.
- `plugin-builds/`
  Local build output for `.rsnxplugin` bundles produced from plugin source trees. This directory is typically created during development and is usually not committed.

## Current Contents

This catalog currently includes example and active plugins such as:

- sensor plugins for `Movesense` and `Movella DOT`
- algorithm plugins including `pass-through`, `standard-loading-intensity`, `generic-data-summary`, and `ecg-rhythm`

The exact contents will evolve as plugins are added, removed, or promoted.

## Typical Workflow

The most common workflow looks like this:

1. Install and activate `nexus-n3-plugin-tooling`
2. Work inside a plugin source tree under `sensors/` or `algorithms/`
3. Build a `.rsnxplugin` bundle into `plugin-builds/`
4. Install that bundle into the runtime environment
5. Test the plugin in the runtime

In practice:

```text
Edit plugin source here
-> build with nexus-n3-plugin
-> bundle appears under plugin-builds/
-> install bundle into the runtime
-> run and validate
```

## Working With Sensor Plugins

Sensor plugin source repositories live under:

```text
sensors/<plugin-repo>/
```

Example:

```text
sensors/nexus-n3-sensor-movesense/
```

A sensor plugin repository typically contains:

- `plugin.json`
- `pyproject.toml`
- `README.md`
- `src/`
- `tests/`

## Working With Algorithm Plugins

Algorithm plugin source repositories live under:

```text
algorithms/<plugin-repo>/
```

Example:

```text
algorithms/nexus-n3-algorithm-standard-loading-intensity/
```

An algorithm plugin repository typically contains:

- `plugin.json`
- `pyproject.toml`
- `README.md`
- `src/`
- `tests/`

## Building Plugin Bundles

Built bundles are typically written to:

```text
plugin-builds/sensors/
plugin-builds/algorithms/
```

Examples:

```text
plugin-builds/sensors/nexus-n3-sensor-movesense-0.1.2.rsnxplugin
plugin-builds/algorithms/nexus-n3-algorithm-standard-loading-intensity-0.1.0.rsnxplugin
```

Bundle creation is handled by `nexus-n3-plugin-tooling`, not by this repository directly.

Typical bundle build commands look like:

```bash
nexus-n3-plugin build \
  --plugin-root /path/to/nexus-n3-plugin-catalog/sensors/nexus-n3-sensor-movesense \
  --output-dir /path/to/nexus-n3-plugin-catalog/plugin-builds/sensors
```

```bash
nexus-n3-plugin build \
  --plugin-root /path/to/nexus-n3-plugin-catalog/algorithms/nexus-n3-algorithm-standard-loading-intensity \
  --output-dir /path/to/nexus-n3-plugin-catalog/plugin-builds/algorithms
```

## Using Bundles With The Runtime

Once a bundle is built, install it into the runtime environment using the runtime-side plugin installer.

Today that runtime integration is provided separately through `nexus-n3-core`.

Typical examples:

```bash
python -m nexus_n3.plugins install \
  /path/to/nexus-n3-plugin-catalog/plugin-builds/sensors/your-sensor-plugin.rsnxplugin
```

```bash
python -m nexus_n3.plugins install \
  /path/to/nexus-n3-plugin-catalog/plugin-builds/algorithms/your-algorithm-plugin.rsnxplugin
```

`nexus-n3-core` can also be configured separately to prepare plugins directly from this catalog during development workflows.

## Creating New Plugins

New plugins are usually scaffolded from `nexus-n3-plugin-tooling`.

Examples:

```bash
nexus-n3-plugin init sensor your-sensor-id \
  --output-dir /path/to/nexus-n3-plugin-catalog
```

```bash
nexus-n3-plugin init algorithm your-algorithm-id \
  --output-dir /path/to/nexus-n3-plugin-catalog
```

When `--output-dir` points at this catalog repository:

- sensor plugins are created under `sensors/`
- algorithm plugins are created under `algorithms/`

## Development Notes

This repository is a catalog workspace, so plugin repositories may create local development artifacts such as:

- `.venv/`
- `build/`
- `dist/`
- `.pytest_cache/`
- temporary test output

Those are intentionally ignored by the repository `.gitignore`.

The source of truth for each plugin should remain:

- source code
- manifest and metadata files
- tests
- user-facing plugin documentation

## Recommended Companion Setup

Recommended local workspace:

```text
<workspace>/
  nexus-n3-plugin-tooling/
  nexus-n3-plugin-catalog/
```

This keeps:

- authoring and build tools in `nexus-n3-plugin-tooling`
- plugin source repositories and bundles in `nexus-n3-plugin-catalog`

If you also work with the separately provided runtime, a larger internal workspace may additionally include `nexus-n3-core`.

## Contributing

When contributing to this repository:

- keep sensor plugins under `sensors/`
- keep algorithm plugins under `algorithms/`
- keep built bundles under `plugin-builds/`
- document each plugin in its own repository README
- avoid committing local virtual environments or build caches

## See Also

- `nexus-n3-plugin-tooling` for scaffolding, validation, and bundle builds
- `nexus-n3-core` for separately provided runtime installation and execution
