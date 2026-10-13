"""Same-workload local benchmark with explicit instrumentation and limits.

This measures Python CPU work and traced allocations, not live diagnostic time,
process RSS, throughput of a deployed service or statistically general speedup.
"""

from __future__ import annotations

import cProfile
import io
import pstats
import time
import tracemalloc
from typing import Any

from .data import grouped_split, load_workbook
from .evaluation import DEFAULT_WORKBOOK, cohort_run
from .model import fit_stage_model
from .probability import ValidationError
from .simulation import Scenario

BENCHMARK_POLICIES = ("eig_per_cost", "lowest_cost", "fixed_test", "stage_map", "prior_map")
BASELINE_SECONDS = 6.413127899999381
BASELINE_PEAK_BYTES = 3550898


def benchmark_workload(repetitions: int = 2) -> dict[str, Any]:
    if type(repetitions) is not int or not 1 <= repetitions <= 10:
        raise ValidationError("benchmark requires 1..10 repetitions")
    rows, _ = load_workbook(DEFAULT_WORKBOOK)
    train, _, test = grouped_split(rows)
    model = fit_stage_model(train)
    runs = []
    profile_text = ""
    for _ in range(repetitions):
        profile = cProfile.Profile()
        tracemalloc.start()
        started = time.perf_counter()
        profile.enable()
        try:
            result = cohort_run(test, model, Scenario(), 42, policies=BENCHMARK_POLICIES)
        finally:
            profile.disable()
            seconds = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        buffer = io.StringIO()
        pstats.Stats(profile, stream=buffer).sort_stats("cumulative").print_stats(10)
        profile_text = buffer.getvalue()
        count = sum(len(records) for records in result["records"].values())
        if count != 335:
            raise AssertionError("benchmark workload changed")
        runs.append({"seconds": seconds, "peak_traced_bytes": peak, "terminal_records": count})
    return {
        "workload": "67 test cases, five original policy families, seed 42, same profiler/tracemalloc setup",
        "runs": runs,
        "baseline_seconds": BASELINE_SECONDS,
        "baseline_peak_traced_bytes": BASELINE_PEAK_BYTES,
        "runtime_gate": "each measured run <= 1.5 times baseline on this host",
        "memory_gate": "each run <= 16 MiB peak traced allocation",
        "passed": all(
            r["seconds"] <= BASELINE_SECONDS * 1.5 and r["peak_traced_bytes"] <= 16 * 1024 * 1024
            for r in runs
        ),
        "profile": profile_text,
        "limitations": "host-dependent instrumented measurements; no general speedup/significance claim",
    }
