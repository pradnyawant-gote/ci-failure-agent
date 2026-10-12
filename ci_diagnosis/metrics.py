"""Explicit abstention, probability-quality and cost metrics with denominators."""

import math
import random
from collections import Counter

from .model import STATES
from .probability import ValidationError, finite_number, validate_vector

# Declared loss assumptions from the project's newer preprint, not money/time.
DEFAULT_WRONG_LOSS = {"Code": 40.0, "Test": 25.0, "Dependency": 45.0, "CI/Config": 65.0}
DEFAULT_REVIEW_COST = 12.0


def scored_record(result, truth, *, wrong_loss=None, review_cost=DEFAULT_REVIEW_COST):
    if truth not in STATES:
        raise ValidationError("scoring requires one supported true state")
    losses = dict(DEFAULT_WRONG_LOSS if wrong_loss is None else wrong_loss)
    if set(losses) != set(STATES):
        raise ValidationError("loss states must match model")
    for state, loss in losses.items():
        finite_number(loss, state + " loss", minimum=0)
    finite_number(review_cost, "review cost", minimum=0)
    from .records import plain
    record = plain(result)
    correct = record["decision"] == "REPORT" and record["prediction"] == truth
    terminal_loss = 0.0 if correct else losses[truth] if record["decision"] == "REPORT" else review_cost
    record.update({"true_state": truth, "correct": correct, "terminal_loss": terminal_loss,
                   "total_decision_cost": record["diagnostic_cost"] + terminal_loss})
    return record


def calculate_metrics(records, *, bins=10):
    if type(bins) is not int or bins < 1:
        raise ValidationError("bins must be a positive integer")
    records = list(records)
    ids = [r["case_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValidationError("duplicate case IDs in policy cohort")
    n = len(records)
    confusion = {s: {p: 0 for p in STATES + ("ESCALATE",)} for s in STATES}
    reliability = [{"lower": i / bins, "upper": (i + 1) / bins, "count": 0,
                    "confidence_sum": 0.0, "correct_sum": 0} for i in range(bins)]
    brier, log_losses = [], []
    top_correct, top_confidence = [], []
    for r in records:
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
    def mean(values):
        return sum(values) / len(values) if values else None
    # For comparability, macro precision convention assigns zero to unpredicted
    # classes; individual undefined precision remains explicitly None.
    ece = sum(abs(b["correct_sum"] - b["confidence_sum"]) for b in reliability) / n if n else None
    supported_recalls = [v for v in recall.values() if v is not None]
    return {"count": n, "reports": reports, "correct_reports": correct, "wrong_reports": reports-correct,
            "coverage": reports / n if n else None, "referral_rate": (n-reports) / n if n else None,
            "correct_auto_rate": correct / n if n else None,
            "selective_accuracy": correct / reports if reports else None,
            "selective_risk": (reports-correct) / reports if reports else None,
            "balanced_accuracy": mean(supported_recalls), "macro_recall": mean(supported_recalls),
            "macro_precision_zero_undefined": mean([v or 0.0 for v in precision.values()]) if n else None,
            "precision": precision, "recall": recall, "support": support, "confusion": confusion,
            "brier": mean(brier), "log_loss": mean(log_losses), "zero_true_probability_cases": sum(math.isinf(x) for x in log_losses),
            "ece": ece, "reliability_bins": reliability,
            "average_actions": mean([len(r["actions_taken"]) for r in records]),
            "average_diagnostic_cost": mean(effort), "median_diagnostic_cost":
            (effort[(n-1)//2] + effort[n//2]) / 2 if n else None,
            "p95_diagnostic_cost": effort[min(n-1, math.ceil(0.95*n)-1)] if n else None,
            "average_total_decision_cost": mean([r["total_decision_cost"] for r in records]),
            "referral_reasons": dict(Counter(r["reason"] for r in records if r["decision"] == "ESCALATE")),
            "high_confidence_wrong_reports": sum(r["decision"] == "REPORT" and r["prediction"] != r["true_state"]
                                                  and max(r["final_belief"].values()) >= 0.90 for r in records),
            "probability_scoring_scope": "all terminal cases, including referrals",
            "selective_accuracy_status": "defined" if reports else "undefined_no_reports",
            "loss_units": "assumed relative loss/effort units; human outcomes not modeled"}


def risk_coverage(records, thresholds=(0.5, 0.7, 0.8, 0.9, 0.95, 0.99)):
    """Descriptive re-thresholding of final beliefs, not a rerun of action policies."""
    points = []
    for threshold in thresholds:
        selected = [r for r in records if max(r["final_belief"].values()) >= threshold]
        correct = sum(max(STATES, key=lambda s: r["final_belief"][s]) == r["true_state"] for r in selected)
        points.append({"threshold": threshold, "accepted": len(selected),
                       "coverage": len(selected)/len(records) if records else None,
                       "accuracy": correct/len(selected) if selected else None})
    return points


def paired_difference(left, right, *, field="total_decision_cost", seed=42, repetitions=500, clusters=None):
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
    group_ids = {}
    for k in ids:
        group_ids.setdefault(clusters[k] if clusters is not None else k, []).append(k)
    groups = sorted(group_ids)
    rng = random.Random(seed)
    draws = []
    for _ in range(repetitions):
        sampled = [k for group in rng.choices(groups, k=len(groups)) for k in group_ids[group]]
        draws.append(sum(deltas[k] for k in sampled)/len(sampled))
    draws.sort()
    return {"mean_difference": sum(deltas.values()) / len(ids), "count": len(ids),
            "interval95": [draws[int(.025*(repetitions-1))], draws[int(.975*(repetitions-1))]],
            "bootstrap_seed": seed, "bootstrap_repetitions": repetitions,
            "resampling": "repository clusters" if clusters is not None else "paired cases",
            "interpretation": "conditional synthetic-run uncertainty; not production evidence"}

