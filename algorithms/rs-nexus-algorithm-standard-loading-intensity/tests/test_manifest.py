import json
from pathlib import Path


def test_plugin_manifest_exists() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
    packaged_manifest = json.loads(
        (plugin_root / "src" / "standard_loading_intensity" / "plugin.json").read_text(encoding="utf-8")
    )
    assert packaged_manifest == manifest
    assert manifest["plugin_type"] == "algorithm"
    assert manifest["algorithm_name"] == "standard_loading_intensity"
    assert manifest["entry_point"] == "standard_loading_intensity.core:StandardLoadingIntensityAlgorithm"
    assert (
        manifest["executor_entry_points"]["intermediate"]
        == "standard_loading_intensity.intermediate_executor:LoadingIntensityIntermediateExecutor"
    )
    assert (
        manifest["executor_entry_points"]["consolidation"]
        == "standard_loading_intensity.consolidation_executor:LoadingIntensityConsolidationExecutor"
    )
    assert manifest["supports_intermediate"] is True
    assert manifest["supports_consolidation"] is True
