"""Read-only workbook ingestion, explicit stage parsing and grouped splits."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile,BadZipFile

from .model import STATES, STAGES
from .probability import ValidationError
from .records import PublicCase,identifier

MAPPING = {
    "Software tests fail": "Test",
    "Project compilation fails due to issues in the source code": "Code",
    "Project compilation fails due to dependency conflicts": "Dependency",
    "Project compilation fails due to unresolved dependencies": "Dependency",
    "Workflow environment setup fails due to dependency issue": "Dependency",
    "Workflow execution fails due to workflow configuration issues or incorrect instructions": "CI/Config",
    "Project compilation fails due to project configuration mistakes/issues": "CI/Config",
    "Access to third-party services fails due to permission issue": "CI/Config",
    "Workflow build fails due to hardware/resource limitation": "CI/Config",
}


def normalize_stage(step: str | float | None) -> str:
    """Conservative lexical rules, not an empirically validated log parser.

    Multiple semantic stage signals are Ambiguous. Build commands containing
    skipTests do not constitute test execution. Missing input is Unknown.
    """
    if step is None or isinstance(step, float) and math.isnan(step):
        return "Unknown"
    if not isinstance(step, str):
        raise ValidationError("stage description must be text or missing")
    text = step.strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return "Unknown"
    if text in STAGES:
        return text
    lowered = text.lower()
    lowered = re.sub(r"\b(?:skip[-_]?tests?|skip[-_]?itests|maven\.test\.skip)(?:\s*=\s*(?:true|false))?\b", " ", lowered)
    lowered = re.sub(r"\b(?:without|skip|no)\s+tests?\b", " ", lowered)
    rules = {
        "Test": r"\b(?:tests?|testing|junit|pytest|cucumber|surefire)\b",
        "Build": r"\b(?:build|compile|compilation|assemble|javac|ant)\b",
        "Setup / Dependency": r"\b(?:setup|prepare|install|dependencies|dependency|requirements|environment)\b",
        "Quality / Analysis": r"\b(?:lint|sonar|analy[sz]e|analysis|checkstyle|quality|scan|licenses)\b",
        "Deploy / Publish": r"\b(?:deploy|deployment|publish|upload|release)\b",
    }
    found = [z for z, regex in rules.items() if re.search(regex, lowered)]
    return found[0] if len(found) == 1 else "Ambiguous"


@dataclass(frozen=True)
class SourceRow:
    source_id: str
    project: str
    state: str
    stage: str
    step: str

    def __post_init__(self) -> None:
        identifier(self.source_id,"source_id",maximum=128)
        if not isinstance(self.project,str) or not self.project.strip() or len(self.project)>512:
            raise ValidationError("repository identity must be bounded text")
        if self.state not in STATES or self.stage not in STAGES or not isinstance(self.step,str):
            raise ValidationError("invalid source row")

    def public(self) -> PublicCase:
        return PublicCase(self.source_id, self.stage)


def load_workbook(path: str | Path) -> tuple[list[SourceRow],dict[str,Any]]:
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f"workbook not found: {path}")
    if path.stat().st_size>32*1024*1024:
        raise ValidationError("workbook exceeds intake size limit")
    try:
        with ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist())>128*1024*1024:
                raise ValidationError("workbook expanded contents exceed size limit")
    except (BadZipFile,OSError) as exc:
        raise ValidationError("invalid workbook archive") from exc
    try:
        import pandas as pd
        df = pd.read_excel(path, engine="openpyxl")
    except ImportError as exc:
        raise ValidationError("workbook evaluation requires pandas and openpyxl") from exc
    except (ValueError,OSError,KeyError) as exc:
        raise ValidationError("cannot read workbook") from exc
    needed = {"job_id", "project_name", "sub-category", "step"}
    if not needed.issubset(df.columns):
        raise ValidationError(f"missing workbook columns: {sorted(needed - set(df.columns))}")
    if df["job_id"].isna().any() or df["job_id"].astype(str).duplicated().any():
        raise ValidationError("source job IDs must be present and unique")
    if df["project_name"].isna().any():
        raise ValidationError("repository identity is required for grouped validation")
    rows, excluded = [], []
    for item in df.to_dict("records"):
        state = MAPPING.get(str(item["sub-category"]).strip())
        source_id = str(item["job_id"])
        if state is None:
            excluded.append(source_id)
            continue
        step = None if pd.isna(item["step"]) else str(item["step"])
        rows.append(SourceRow(source_id, str(item["project_name"]), state, normalize_stage(step), step or ""))
    if not rows or any(not any(r.state == s for r in rows) for s in STATES):
        raise ValidationError("mapped workbook must contain all four states")
    return rows, {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "source_count": len(df), "mapped_count": len(rows), "excluded_count": len(excluded),
                  "excluded_ids": excluded, "mapping_version": "notebook-labels/1",
                  "normalizer_version": "conservative-seven-stage/1"}


def grouped_split(rows: list[SourceRow], seed: int=42, *, train_fraction: float=0.6,
                  validation_fraction: float=0.2) -> tuple[list[SourceRow],list[SourceRow],list[SourceRow]]:
    if type(seed) is not int or seed<0 or len({r.source_id for r in rows})!=len(rows):
        raise ValidationError("split requires valid seed and unique source IDs")
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 - train_fraction:
        raise ValidationError("invalid split fractions")
    projects = sorted({r.project for r in rows}, key=lambda p: hashlib.sha256(f"{seed}:{p}".encode()).digest())
    if len(projects) < 3:
        raise ValidationError("at least three repositories required for disjoint splits")
    n_train = min(len(projects) - 2, max(1, int(len(projects) * train_fraction)))
    n_val = min(len(projects) - n_train - 1, max(1, int(len(projects) * validation_fraction)))
    groups = (set(projects[:n_train]), set(projects[n_train:n_train+n_val]), set(projects[n_train+n_val:]))
    parts=[sorted((r for r in rows if r.project in group), key=lambda r: r.source_id) for group in groups]
    return parts[0],parts[1],parts[2]

