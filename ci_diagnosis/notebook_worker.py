"""Pinned notebook execution in a bounded child process, never in caller state."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .probability import ValidationError, finite_number


def execute_worker(path: Path, mode: str, timeout: float = 60.0) -> dict[str, Any]:
    from .legacy import NOTEBOOK_SHA256, read_notebook

    if mode not in {"unit", "compatibility"}:
        raise ValidationError("unknown notebook worker mode")
    finite_number(timeout, "worker timeout", minimum=0)
    if timeout <= 0 or read_notebook(path)[1] != NOTEBOOK_SHA256:
        raise ValidationError("notebook content is not the pinned original")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    command = [
        sys.executable,
        "-B",
        "-m",
        "ci_diagnosis.notebook_worker",
        "--path",
        str(path.resolve()),
        "--mode",
        mode,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationError("notebook worker timed out and was terminated") from exc
    if completed.returncode != 0:
        raise ValidationError("isolated notebook validation failed")
    if len(completed.stdout) > 1024 * 1024:
        raise ValidationError("worker output exceeds contract")
    result = json.loads(completed.stdout)
    if not isinstance(result, dict):
        raise ValidationError("invalid worker result")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--mode", choices=("unit", "compatibility"), required=True)
    args = parser.parse_args(argv)
    from .compatibility import _compatibility_inprocess
    from .legacy import NOTEBOOK_SHA256, _unit_checks_inprocess, read_notebook

    if read_notebook(args.path)[1] != NOTEBOOK_SHA256:
        print("untrusted notebook content", file=sys.stderr)
        return 2
    result = _unit_checks_inprocess(args.path) if args.mode == "unit" else _compatibility_inprocess(args.path)
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
