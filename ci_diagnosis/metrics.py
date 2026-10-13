"""Explicit abstention, probability-quality and cost metrics with denominators."""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .decision_cost import DEFAULT_REVIEW_COST as DEFAULT_REVIEW_COST
from .decision_cost import DEFAULT_WRONG_LOSS as DEFAULT_WRONG_LOSS
from .decision_cost import DecisionCosts
from .model import STATES
from .probability import ValidationError, finite_number, validate_vector
from .records import RECORD_VERSION, Diagnosis, fingerprint, plain


def scored_record(
    result: Diagnosis,
    truth: str,
    *,
    wrong_loss: Mapping[str, float] | None = None,
    review_cost: float = DEFAULT_REVIEW_COST,
) -> dict[str, Any]:
    if truth not in STATES:
        raise ValidationError("scoring requires one supported true state")
    losses = dict(DEFAULT_WRONG_LOSS if wrong_loss is None else wrong_loss)
    if set(losses) != set(STATES):
        raise ValidationError("loss states must match model")
    for state, loss in losses.items():
        finite_number(loss, state + " loss", minimum=0)
    finite_number(review_cost, "review cost", minimum=0)
    record: dict[str, Any] = plain(result)
    correct = record["decision"] == "REPORT" and record["prediction"] == truth
    terminal_loss = 0.0 if correct else losses[truth] if record["decision"] == "REPORT" else review_cost
    record.update(
        {
            "true_state": truth,
            "correct": correct,
            "terminal_loss": terminal_loss,
            "total_decision_cost": record["diagnostic_cost"] + terminal_loss,
            "loss_model": {"wrong_loss": losses, "review_cost": review_cost, "version": "declared-loss/1"},
        }
    )
    record["record_hash"] = fingerprint(record)
    validate_scored_record(record)
    return record


def verify_record_hash(record: Mapping[str, Any]) -> bool:
    return record.get("record_hash") == fingerprint({k: v for k, v in record.items() if k != "record_hash"})


def validate_scored_record(record: Mapping[str, Any]) -> None:
    """A checksum proves identity, not semantic correctness or authenticity."""
    required = {
        "record_version",
        "case_id",
        "decision",
        "prediction",
        "true_state",
        "correct",
        "final_belief",
        "confidence",
        "diagnostic_cost",
        "terminal_loss",
        "total_decision_cost",
        "loss_model",
        "actions_taken",
        "record_hash",
    }
    if not required.issubset(record) or record["record_version"] != RECORD_VERSION:
        raise ValidationError("unsupported or incomplete scored record schema")
    if not verify_record_hash(record):
        raise ValidationError("diagnostic record checksum mismatch")
    truth = record["true_state"]
    decision = record["decision"]
    prediction = record["prediction"]
    if truth not in STATES or decision not in {"REPORT", "ESCALATE"}:
        raise ValidationError("invalid truth/disposition")
    if (decision == "REPORT" and prediction not in STATES) or (
        decision == "ESCALATE" and prediction is not None
    ):
        raise ValidationError("prediction disagrees with disposition")
    correct = decision == "REPORT" and prediction == truth
    if type(record["correct"]) is not bool or record["correct"] != correct:
        raise ValidationError("incorrect correctness flag")
    costs = DecisionCosts(record["loss_model"]["wrong_loss"], record["loss_model"]["review_cost"])
    expected_loss = 0.0 if correct else costs.wrong_loss[truth] if decision == "REPORT" else costs.review_cost
    for name in ("diagnostic_cost", "terminal_loss", "total_decision_cost"):
        finite_number(record[name], name, minimum=0)
    if not math.isclose(record["terminal_loss"], expected_loss, abs_tol=1e-9, rel_tol=0):
        raise ValidationError("terminal loss disagrees with declared loss model")
    if not math.isclose(
        record["total_decision_cost"], record["diagnostic_cost"] + expected_loss, abs_tol=1e-9, rel_tol=0
    ):
        raise ValidationError("total decision cost inconsistent")
    belief = validate_vector(record["final_belief"], STATES, normalized=True)
    if not math.isclose(record["confidence"], max(belief.values()), abs_tol=1e-10, rel_tol=0):
        raise ValidationError("terminal confidence inconsistent")
    cumulative = 0.0
    previous: Mapping[str, float] | None = None
    for action in record["actions_taken"]:
        cumulative += finite_number(action["cost"], "action cost", minimum=0)
        if not math.isclose(action["cumulative_cost"], cumulative, abs_tol=1e-9, rel_tol=0):
            raise ValidationError("cumulative action cost inconsistent")
        before = validate_vector(action["posterior_before"], STATES, normalized=True)
        after = validate_vector(action["posterior_after"], STATES, normalized=True)
        if previous is not None and any(abs(before[s] - previous[s]) > 1e-10 for s in STATES):
            raise ValidationError("belief trace is discontinuous")
        if not action["applied"] and any(abs(before[s] - after[s]) > 1e-10 for s in STATES):
            raise ValidationError("unapplied evidence changed belief")
        previous = after
    if not math.isclose(cumulative, record["diagnostic_cost"], abs_tol=1e-9, rel_tol=0):
        raise ValidationError("diagnostic cost inconsistent with actions")
    if previous is not None and any(abs(previous[s] - belief[s]) > 1e-10 for s in STATES):
        raise ValidationError("terminal belief differs from final action")


def calculate_metrics(records: Sequence[Mapping[str, Any]], *, bins: int = 10) -> dict[str, Any]:
    if type(bins) is not int or bins < 1:
        raise ValidationError("bins must be a positive integer")
    records = list(records)
    ids = [r["case_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValidationError("duplicate case IDs in policy cohort")
    n = len(records)
    confusion = {s: {p: 0 for p in STATES + ("ESCALATE",)} for s in STATES}
    reliability = [
        {"lower": i / bins, "upper": (i + 1) / bins, "count": 0, "confidence_sum": 0.0, "correct_sum": 0}
        for i in range(bins)
    ]
    brier, log_losses = [], []
    top_correct, top_confidence = [], []
    for r in records:
        validate_scored_record(r)
        if "record_hash" in r and not verify_record_hash(r):
            raise ValidationError("diagnostic record checksum mismatch")
        truth = r.get("true_state")
        if truth not in STATES or r.get("decision") not in {"REPORT", "ESCALATE"}:
            raise ValidationError("invalid scored terminal record")
        if r["decision"] == "REPORT" and r.get("prediction") not in STATES:
            raise ValidationError("invalid report prediction")
        if r["decision"] == "ESCALATE" and r.get("prediction") is not None:
            raise ValidationError("referral cannot have an automatic prediction")
        b = validate_vector(r["final_belief"], STATES, normalized=True)
        finite_number(r["diagnostic_cost"], "diagnostic cost", minimum=0)
        finite_number(r["total_decision_cost"], "total decision cost", minimum=0)
        if r.get("correct") != (r["decision"] == "REPORT" and r.get("prediction") == truth):
            raise ValidationError("record correctness disagrees with terminal decision")
        confusion[truth][r["prediction"] if r["decision"] == "REPORT" else "ESCALATE"] += 1
        brier.append(math.fsum((b[s] - int(s == truth)) ** 2 for s in STATES))
        log_losses.append(-math.log(b[truth]) if b[truth] > 0 else math.inf)
        predicted = max(STATES, key=lambda s: b[s])
        confidence, correctness = b[predicted], int(predicted == truth)
        top_confidence.append(confidence)
        top_correct.append(correctness)
        bucket = reliability[min(bins - 1, int(confidence * bins))]
        bucket["count"] += 1
        bucket["confidence_sum"] += confidence
        bucket["correct_sum"] += correctness
    reports = sum(r["decision"] == "REPORT" for r in records)
    correct = sum(r["decision"] == "REPORT" and r["prediction"] == r["true_state"] for r in records)
    support = {s: sum(confusion[s].values()) for s in STATES}
    predicted_support = {s: sum(confusion[t][s] for t in STATES) for s in STATES}
    precision = {s: confusion[s][s] / predicted_support[s] if predicted_support[s] else None for s in STATES}
    recall = {s: confusion[s][s] / support[s] if support[s] else None for s in STATES}
    effort = sorted(r["diagnostic_cost"] for r in records)

    def mean(values: Sequence[float]) -> float | None:
        return math.fsum(v / len(values) for v in values) if values else None

    # For comparability, macro precision convention assigns zero to unpredicted
    # classes; individual undefined precision remains explicitly None.
    ece = sum(abs(b["correct_sum"] - b["confidence_sum"]) for b in reliability) / n if n else None
    supported_recalls = [v for v in recall.values() if v is not None]
    attempts = [a for r in records for a in r["actions_taken"]]
    failed = sum(a["status"] != "signal" for a in attempts)
    classwise_brier = {
        s: mean([(r["final_belief"][s] - int(r["true_state"] == s)) ** 2 for r in records]) for s in STATES
    }
    classwise_ece = {}
    for state in STATES:
        buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
        for r in records:
            p = r["final_belief"][state]
            buckets[min(bins - 1, int(p * bins))].append((p, int(r["true_state"] == state)))
        classwise_ece[state] = (
            sum(abs(sum(correct - p for p, correct in bucket)) for bucket in buckets) / n if n else None
        )
    return {
        "count": n,
        "reports": reports,
        "correct_reports": correct,
        "wrong_reports": reports - correct,
        "coverage": reports / n if n else None,
        "referral_rate": (n - reports) / n if n else None,
        "correct_auto_rate": correct / n if n else None,
        "selective_accuracy": correct / reports if reports else None,
        "selective_risk": (reports - correct) / reports if reports else None,
        "balanced_accuracy": mean(supported_recalls),
        "macro_recall": mean(supported_recalls),
        "macro_precision_zero_undefined": mean([v or 0.0 for v in precision.values()]) if n else None,
        "precision": precision,
        "recall": recall,
        "support": support,
        "confusion": confusion,
        "brier": mean(brier),
        "log_loss": mean(log_losses),
        "zero_true_probability_cases": sum(math.isinf(x) for x in log_losses),
        "ece": ece,
        "reliability_bins": reliability,
        "classwise_brier": classwise_brier,
        "classwise_ece": classwise_ece,
        "average_actions": mean([len(r["actions_taken"]) for r in records]),
        "average_attempts": mean([len(r["actions_taken"]) for r in records]),
        "average_unique_actions": mean([len({a["action_id"] for a in r["actions_taken"]}) for r in records]),
        "failed_attempt_rate": failed / len(attempts) if attempts else None,
        "attempt_status_counts": dict(Counter(a["status"] for a in attempts)),
        "duplicate_evidence_suppressions": sum(
            a["reason"] in {"duplicate_event", "duplicate_evidence"} for a in attempts
        ),
        "average_diagnostic_cost": mean(effort),
        "median_diagnostic_cost": effort[(n - 1) // 2] / 2 + effort[n // 2] / 2 if n else None,
        "p95_diagnostic_cost": effort[min(n - 1, math.ceil(0.95 * n) - 1)] if n else None,
        "average_total_decision_cost": mean([r["total_decision_cost"] for r in records]),
        "referral_reasons": dict(Counter(r["reason"] for r in records if r["decision"] == "ESCALATE")),
        "high_confidence_wrong_reports": sum(
            r["decision"] == "REPORT"
            and r["prediction"] != r["true_state"]
            and max(r["final_belief"].values()) >= 0.90
            for r in records
        ),
        "probability_scoring_scope": "all terminal cases, including referrals",
        "selective_accuracy_status": "defined" if reports else "undefined_no_reports",
        "loss_units": "assumed relative loss/effort units; human outcomes not modeled",
    }


def risk_coverage(
    records: Sequence[Mapping[str, Any]], thresholds: Sequence[float] = (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)
) -> list[dict[str, Any]]:
    """Descriptive re-thresholding of final beliefs, not a rerun of action policies."""
    points = []
    for threshold in thresholds:
        finite_number(threshold, "threshold", minimum=0, maximum=1)
        selected = [r for r in records if max(r["final_belief"].values()) >= threshold]
        correct = sum(max(STATES, key=lambda s: r["final_belief"][s]) == r["true_state"] for r in selected)
        points.append(
            {
                "threshold": threshold,
                "accepted": len(selected),
                "coverage": len(selected) / len(records) if records else None,
                "accuracy": correct / len(selected) if selected else None,
            }
        )
    return points


def paired_difference(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    field: str = "total_decision_cost",
    seed: int = 42,
    repetitions: int = 500,
    clusters: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if type(repetitions) is not int or repetitions < 2:
        raise ValidationError("bootstrap needs at least two repetitions")
    a = {r["case_id"]: r for r in left}
    b = {r["case_id"]: r for r in right}
    if len(a) != len(left) or len(b) != len(right) or set(a) != set(b):
        raise ValidationError("paired policies need unique, identical case IDs")
    if any(a[k]["true_state"] != b[k]["true_state"] for k in a):
        raise ValidationError("paired truth labels disagree")
    if not a:
        return {"mean_difference": None, "interval95": None, "count": 0}
    ids = sorted(a)
    deltas = {k: a[k][field] - b[k][field] for k in ids}
    if clusters is not None and not set(ids).issubset(clusters):
        raise ValidationError("missing repository cluster")
    group_ids: dict[str, list[str]] = {}
    for k in ids:
        group_ids.setdefault(clusters[k] if clusters is not None else k, []).append(k)
    groups = sorted(group_ids)
    rng = random.Random(seed)
    draws = []
    for _ in range(repetitions):
        sampled = [k for group in rng.choices(groups, k=len(groups)) for k in group_ids[group]]
        draws.append(sum(deltas[k] for k in sampled) / len(sampled))
    draws.sort()
    return {
        "mean_difference": sum(deltas.values()) / len(ids),
        "count": len(ids),
        "interval95": [draws[int(0.025 * (repetitions - 1))], draws[int(0.975 * (repetitions - 1))]],
        "bootstrap_seed": seed,
        "bootstrap_repetitions": repetitions,
        "resampling": "repository clusters" if clusters is not None else "paired cases",
        "interpretation": "conditional synthetic-run uncertainty; not production evidence",
    }
