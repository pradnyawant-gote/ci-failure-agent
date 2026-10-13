"""Real temporary-file tests of atomic publication and data-only reading."""

import unittest
from pathlib import Path

try:
    import pytest
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("pytest is required for persistence fixtures") from exc

from ci_diagnosis.artifacts import ArtifactLimits, read_python_artifact, write_python_artifact
from ci_diagnosis.probability import ValidationError


def test_data_reader_never_executes_extra_source(tmp_path: Path) -> None:
    path = tmp_path / "record.py"
    write_python_artifact(path, {"value": 1})
    path.write_text(
        path.read_text(encoding="utf-8") + "\nraise RuntimeError('MUST_NOT_EXECUTE')\n", encoding="utf-8"
    )
    assert read_python_artifact(path) == {"value": 1}


def test_atomic_replace_failure_preserves_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "record.py"
    write_python_artifact(path, {"value": 1})
    before = path.read_bytes()

    def fail(*args: object) -> None:
        raise OSError("synthetic write failure")

    monkeypatch.setattr("ci_diagnosis.artifacts.os.replace", fail)
    with pytest.raises(ValidationError):
        write_python_artifact(path, {"value": 2})
    assert path.read_bytes() == before
    assert list(tmp_path.glob(".*.py")) == []


def test_source_overwrite_refused(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        write_python_artifact(source, {"value": 2})
    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_corrupt_and_oversized_artifact_refused(tmp_path: Path) -> None:
    path = tmp_path / "record.py"
    write_python_artifact(path, {"blob": "x" * 1000})
    with pytest.raises(ValidationError):
        read_python_artifact(path, ArtifactLimits(payload_bytes=10))
    with pytest.raises(ValidationError):
        read_python_artifact(path, ArtifactLimits(source_bytes=10))
    text = path.read_text(encoding="utf-8")
    start = text.index("PAYLOAD_SHA256 = ") + len("PAYLOAD_SHA256 = ")
    text = text[:start] + repr("0" * 64) + text[start + 66 :]
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError):
        read_python_artifact(path)


def test_truncated_source_refused(tmp_path: Path) -> None:
    path = tmp_path / "record.py"
    path.write_text("PAYLOAD_SHA256 = 'incomplete'\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        read_python_artifact(path)
