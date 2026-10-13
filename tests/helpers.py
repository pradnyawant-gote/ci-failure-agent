"""Independent small fixtures; not alternate production implementations."""

from ci_diagnosis.model import Action, Model, STAGES, STATES
from ci_diagnosis.records import Diagnosis, RECORD_VERSION,ActionRecord


def two_state_model(count=2, *, positive=(.8, .2, .5, .5), cost=1.0):
    signal = dict(zip(STATES, positive))
    actions = tuple(Action(f"a{i}", f"Check {i}", cost, ("all",),
                    {"signal": signal, "no_signal": {s: 1-p for s,p in signal.items()}},
                    {"signal": "Positive", "no_signal": "Negative"}, {}) for i in range(count))
    return Model("test-fixture/1", dict(zip(STATES, (.5, .5, 0., 0.))),
                 {z: dict.fromkeys(STATES, 1/len(STAGES)) for z in STAGES}, actions,
                 {"status": "synthetic fixture only"})


def terminal(case_id, belief, decision="REPORT", prediction="Code", cost=0.0):
    actions=() if cost==0 else (ActionRecord("fixture_action","Fixture",0,"fixture_event",None,
                  "inconclusive",None,cost,cost,0,0,belief,belief,None,False,"fixture"),)
    return Diagnosis(RECORD_VERSION, case_id, "Build", "test", decision, "fixture", prediction,
                     belief, max(belief.values()), cost, actions, "fixture/1", "modelhash", "confighash", ())

