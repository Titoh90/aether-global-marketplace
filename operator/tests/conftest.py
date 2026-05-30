from __future__ import annotations

import sys
from pathlib import Path


OPERATOR_ROOT = Path(__file__).resolve().parents[1]

if str(OPERATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(OPERATOR_ROOT))
