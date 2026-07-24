from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SENSOR_SRC_ROOT = REPO_ROOT / "sensors"


def test_all_source_sensor_specs_define_non_empty_sensor_name():
    spec_paths = sorted(SENSOR_SRC_ROOT.glob("*/src/*/*Spec.yaml"))
    assert spec_paths, "Expected at least one sensor spec in the plugin catalog"

    missing_names: list[str] = []
    for spec_path in spec_paths:
        payload = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
        sensor_name = ((payload.get("sensor") or {}).get("name") or "").strip()
        if not sensor_name:
            missing_names.append(str(spec_path.relative_to(REPO_ROOT)))

    assert not missing_names, f"Sensor specs missing sensor.name: {missing_names}"
