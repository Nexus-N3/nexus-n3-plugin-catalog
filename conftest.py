from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SDK_SRC_DIR = REPO_ROOT / "rs-nexus-plugin-tooling" / "packages" / "sdk" / "src"

if str(SDK_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_SRC_DIR))
