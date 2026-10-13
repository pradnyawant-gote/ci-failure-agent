"""Independent small fixtures; not alternate production implementations."""

from ci_diagnosis.model import STAGES, STATES, Action, Model
from ci_diagnosis.records import RECORD_VERSION, ActionRecord, Diagnosis


def two_state_model(count=2, *, positive=(0.8, 0.2, 0.5, 0.5), cost=1.0):
    signal = dict(zip(STATES, positive, strict=False))
    actions = tuple(
        Action(
            f"a{i}",
            f"Check {i}",
            cost,
            ("all",),
            {"signal": signal, "no_signal": {s: 1 - p for s, p in signal.items()}},
            {"signal": "Positive", "no_signal": "Negative"},
            {},
        )
        for i in range(count)
    )
    return Model(
        "test-fixture/1",
        dict(zip(STATES, (0.5, 0.5, 0.0, 0.0), strict=False)),
        {z: dict.fromkeys(STATES, 1 / len(STAGES)) for z in STAGES},
        actions,
        {"status": "synthetic fixture only"},
    )


def terminal(case_id, belief, decision="REPORT", prediction="Code", cost=0.0):
    actions = (
        ()
        if cost == 0
        else (
            ActionRecord(
                "fixture_action",
                "Fixture",
                0,
                "fixture_event",
                None,
                "inconclusive",
                None,
                cost,
                cost,
                0,
                0,
                belief,
                belief,
                None,
                False,
                "fixture",
            ),
        )
    )
    return Diagnosis(
        RECORD_VERSION,
        case_id,
        "Build",
        "test",
        decision,
        "fixture",
        prediction,
        belief,
        max(belief.values()),
        cost,
        actions,
        "fixture/1",
        "modelhash",
        "confighash",
        (),
    )
