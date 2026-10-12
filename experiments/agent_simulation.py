"""Python entry point alongside the preserved agent_simulation.ipynb.

From any directory:
    python -B experiments/agent_simulation.py --output experiments/evaluation_results.py
From project root:
    python -B -m ci_diagnosis.evaluation
Tests:
    python -B -m unittest discover -s tests -v

Dependencies: Python >=3.10; core is standard library; workbook evaluation needs
pandas and openpyxl. The exact runtime is saved with each generated experiment.
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci_diagnosis.evaluation import main

if __name__ == "__main__":
    raise SystemExit(main())

