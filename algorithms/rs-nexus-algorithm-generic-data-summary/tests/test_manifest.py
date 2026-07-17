import json
from pathlib import Path


def test_plugin_manifest_exists() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    root_manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
    packaged_manifest = json.loads((plugin_root / "src" / "generic_data_summary" / "plugin.json").read_text(encoding="utf-8"))
    assert packaged_manifest == root_manifest
    assert root_manifest["plugin_type"] == "algorithm"
    assert root_manifest["algorithm_name"] == "generic_data_summary"
