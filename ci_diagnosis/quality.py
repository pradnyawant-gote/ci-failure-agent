"""Configured test, lint, format, type, environment and workload gates.

Usage: python -B -m ci_diagnosis.quality --output experiments/engineering_quality_results.py
Install the constrained workbook and pinned dev extras from pyproject.toml.
Quality output is a Python data artifact, separate from deterministic experiments.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .artifacts import write_python_artifact
from .benchmark import benchmark_workload
from .legacy import DEFAULT_NOTEBOOK, NOTEBOOK_SHA256

ROOT = Path(__file__).resolve().parents[1]
PINNED_TOOLS = {"pytest": "8.4.2", "ruff": "0.13.2", "mypy": "1.18.2"}


def environment_status() -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for package in ("pytest", "ruff", "mypy", "pandas", "openpyxl"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    tools_match = all(versions[k] == v for k, v in PINNED_TOOLS.items())
    py_supported = (3, 10) <= sys.version_info[:2] < (3, 14)
    pandas_version = versions["pandas"]
    openpyxl_version = versions["openpyxl"]
    workbook_dependencies = (
        pandas_version is not None
        and openpyxl_version is not None
        and (2, 2) <= tuple(int(x) for x in pandas_version.split(".")[:2]) < (3, 1)
        and (3, 1) <= tuple(int(x) for x in openpyxl_version.split(".")[:2]) < (3, 2)
    )
    try:
        notebook_preserved = hashlib.sha256(DEFAULT_NOTEBOOK.read_bytes()).hexdigest() == NOTEBOOK_SHA256
    except OSError:
        notebook_preserved = False
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "versions": versions,
        "expected_tool_versions": PINNED_TOOLS,
        "tools_match": tools_match,
        "python_supported": py_supported,
        "workbook_dependencies_supported": workbook_dependencies,
        "notebook_preserved": notebook_preserved,
        "passed": tools_match and py_supported and workbook_dependencies and notebook_preserved,
    }


def run_gate(name: str, arguments: list[str], timeout: float = 180.0) -> dict[str, Any]:
    command = [sys.executable, "-B", "-m", *arguments]
    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"gate": name, "command": command, "passed": False, "reason": "timeout"}
    return {
        "gate": name,
        "command": command,
        "returncode": result.returncode,
        "passed": result.returncode == 0,
        "stdout": result.stdout[-24000:],
        "stderr": result.stderr[-24000:],
    }


def run_quality() -> dict[str, Any]:
    environment = environment_status()
    if not environment["passed"]:
        return {
            "environment": environment,
            "passed": False,
            "gates": [],
            "reason": "environment contract incomplete",
        }
    cache = ROOT / ".qa-cache"
    cache.mkdir(exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="pytest-", dir=cache)).resolve()
    if not temp.is_relative_to(ROOT.resolve()):
        raise AssertionError("pytest cleanup target escaped the workspace")
    targets = [
        "ci_diagnosis",
        "tests",
        "experiments/agent_simulation.py",
        "experiments/implementation_report.py",
        "experiments/engineering_report.py",
    ]
    gates = [
        run_gate("pytest", ["pytest", "-q", "-p", "no:cacheprovider", "--basetemp", str(temp)]),
        run_gate("lint", ["ruff", "check", "--no-cache", *targets]),
        run_gate("format", ["ruff", "format", "--check", *targets]),
        run_gate("types", ["mypy", "--cache-dir", str(cache / "mypy")]),
    ]
    benchmark = (
        benchmark_workload()
        if all(g["passed"] for g in gates)
        else {"passed": False, "reason": "quality gates failed"}
    )
    source_paths = list((ROOT / "ci_diagnosis").glob("*.py")) + list((ROOT / "tests").glob("*.py"))
    return {
        "implementation_version": __version__,
        "environment": environment,
        "gates": gates,
        "benchmark": benchmark,
        "source_hashes": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source_paths)
        },
        "configuration_hash": hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest(),
        "passed": all(g["passed"] for g in gates) and benchmark["passed"],
        "production_readiness": "not demonstrated: empirical diagnostic traces/calibration, real review outcomes and operational adapters incomplete",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = environment_status() if args.doctor else run_quality()
    if args.output:
        write_python_artifact(args.output, result)
    print(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
