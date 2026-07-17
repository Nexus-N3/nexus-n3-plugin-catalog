# nexus-n3-plugin-catalog

User-facing catalog of RS Nexus sensor and algorithm plugins.

This repository is the shared plugin workspace for Nexus N3 systems. It keeps plugin source repositories in one place, alongside optional built `.rsnxplugin` bundles that can be installed into `rs-nexus-os`.

## What This Repository Is For

Use this repository when you want to:

- browse the available Nexus N3 plugins
- develop or update a sensor plugin
- develop or update an algorithm plugin
- build plugin bundles for local testing or deployment
- keep a consistent plugin catalog layout across teams and environments

This repository is not the plugin CLI itself, and it is not the runtime host.

Related repositories:

- `rs-nexus-plugin-tooling`
  Provides the `rsnexus-plugin` CLI, SDK, scaffolding, validation, and bundle build workflow.
- `rs-nexus-os`
  Provides plugin installation, plugin discovery, and runtime execution.

## Repository Layout

The catalog is organized into three top-level areas:

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
  Built `.rsnxplugin` bundles produced from plugin source trees.

## Current Contents

This catalog currently includes example and active plugins such as:

- sensor plugins for `Movesense` and `Movella DOT`
- algorithm plugins including `pass-through`, `standard-loading-intensity`, `generic-data-summary`, and `ecg-rhythm`

The exact contents will evolve as plugins are added, removed, or promoted.

## Typical Workflow

The most common workflow looks like this:

1. Install and activate `rs-nexus-plugin-tooling`
2. Work inside a plugin source tree under `sensors/` or `algorithms/`
3. Build a `.rsnxplugin` bundle into `plugin-builds/`
4. Install that bundle into `rs-nexus-os`
5. Test the plugin in the runtime

In practice:

```text
Edit plugin source here
-> build with rsnexus-plugin
-> bundle appears under plugin-builds/
-> install bundle into rs-nexus-os
-> run and validate
```

## Working With Sensor Plugins

Sensor plugin source repositories live under:

```text
sensors/<plugin-repo>/
```

Example:

```text
sensors/rs-nexus-sensor-movesense/
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
algorithms/rs-nexus-algorithm-standard-loading-intensity/
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
plugin-builds/sensors/rs-nexus-sensor-movesense-0.1.2.rsnxplugin
plugin-builds/algorithms/rs-nexus-algorithm-standard-loading-intensity-0.1.0.rsnxplugin
```

Bundle creation is handled by `rs-nexus-plugin-tooling`, not by this repository directly.

Typical bundle build commands look like:

```bash
rsnexus-plugin build \
  --plugin-root /path/to/nexus-n3-plugin-catalog/sensors/rs-nexus-sensor-movesense \
  --output-dir /path/to/nexus-n3-plugin-catalog/plugin-builds/sensors
```

```bash
rsnexus-plugin build \
  --plugin-root /path/to/nexus-n3-plugin-catalog/algorithms/rs-nexus-algorithm-standard-loading-intensity \
  --output-dir /path/to/nexus-n3-plugin-catalog/plugin-builds/algorithms
```

## Using Bundles With rs-nexus-os

Once a bundle is built, install it into `rs-nexus-os` using the runtime-side plugin installer.

Typical examples:

```bash
python -m rs_nexus_plugins install \
  /path/to/nexus-n3-plugin-catalog/plugin-builds/sensors/your-sensor-plugin.rsnxplugin
```

```bash
python -m rs_nexus_plugins install \
  /path/to/nexus-n3-plugin-catalog/plugin-builds/algorithms/your-algorithm-plugin.rsnxplugin
```

`rs-nexus-os` can also be configured to prepare plugins directly from this catalog during development workflows.

## Creating New Plugins

New plugins are usually scaffolded from `rs-nexus-plugin-tooling`.

Examples:

```bash
rsnexus-plugin init sensor your-sensor-id \
  --output-dir /path/to/nexus-n3-plugin-catalog
```

```bash
rsnexus-plugin init algorithm your-algorithm-id \
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
  rs-nexus-plugin-tooling/
  rs-nexus-os/
  nexus-n3-plugin-catalog/
```

This keeps:

- authoring and build tools in `rs-nexus-plugin-tooling`
- runtime installation and execution in `rs-nexus-os`
- plugin source repositories and bundles in `nexus-n3-plugin-catalog`

## Contributing

When contributing to this repository:

- keep sensor plugins under `sensors/`
- keep algorithm plugins under `algorithms/`
- keep built bundles under `plugin-builds/`
- document each plugin in its own repository README
- avoid committing local virtual environments or build caches

## See Also

- `rs-nexus-plugin-tooling` for scaffolding, validation, and bundle builds
- `rs-nexus-os` for plugin installation and runtime execution
