# Movella DOT Sensor Plugin

Standalone RS Nexus sensor plugin for `Movella DOT`.

This plugin is the first migration candidate from the built-in
`rs_nexus_sensors.MovellaDot` implementation that currently ships inside
`rs-nexus-os`.

## Development

Install the local SDK and CLI from `rs-nexus-plugin-tooling`, then build the
wheel and Phase 1 plugin bundle:

```bash
python -m build
rsnexus-plugin build --plugin-root . --output-dir build
```

For an offline-complete `.rsnxplugin`, include any dependency wheels that are
not bundled automatically, for example `numpy`.

## Notes

- Generated from `rsnexus-plugin init sensor`, then migrated from the in-tree sensor
- Depends on `rs-nexus-plugin-sdk`
- Intentionally does not modify the current `rs-nexus-os` runtime
