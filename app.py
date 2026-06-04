from __future__ import annotations

import runpy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

runpy.run_module("app.main", run_name="__main__")
