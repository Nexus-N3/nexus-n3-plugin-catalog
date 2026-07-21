# Movella DOT Sensor Plugin

Standalone Nexus N3 sensor plugin for `Movella DOT`.

This plugin is the first migration candidate from the built-in
`nexus_n3_sensors.MovellaDot` implementation that currently ships inside
`nexus-n3-core`.

## Development

Install the local SDK and CLI from `nexus-n3-plugin-tooling`, then build the
wheel and Phase 1 plugin bundle:

```bash
python -m build
nexus-n3-plugin build --plugin-root . --output-dir build
```

## Notes

- Generated from `nexus-n3-plugin init sensor`, then migrated from the in-tree sensor
- Depends on `nexus-n3-plugin-sdk`
- Intentionally does not modify the current `nexus-n3-core` runtime
