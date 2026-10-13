"""Declared reporting losses and hand-checkable one-step Bayes risk.

These relative loss/effort units come from the newer preprint assumptions.
They are not measured money, durations or validated human-review performance.
Positive risk reduction/cost is not net utility or optimal multistep planning.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass,field

from .domain import Belief,OutcomeModel,STATES
from .probability import ValidationError,ImpossibleEvidence,finite_number,validate_vector,validate_outcome_model,update_belief
from .records import freeze

DEFAULT_WRONG_LOSS = {"Code":40.0,"Test":25.0,"Dependency":45.0,"CI/Config":65.0}
DEFAULT_REVIEW_COST = 12.0


@dataclass(frozen=True)
class DecisionCosts:
    wrong_loss: Mapping[str,float] = field(default_factory=lambda:dict(DEFAULT_WRONG_LOSS))
    review_cost: float = DEFAULT_REVIEW_COST
    version: str = "preprint-declared-loss/1"

    def __post_init__(self) -> None:
        if set(self.wrong_loss)!=set(STATES):
            raise ValidationError("loss states must match model")
        for s,value in self.wrong_loss.items():
            finite_number(value,s+" loss",minimum=0)
        finite_number(self.review_cost,"review cost",minimum=0)
        object.__setattr__(self,"wrong_loss",freeze(dict(self.wrong_loss)))

    def report_risk(self, belief: Belief, prediction: str) -> float:
        validate_vector(belief,STATES,normalized=True)
        if prediction not in STATES:
            raise ValidationError("unknown report label")
        return math.fsum(belief[s]*self.wrong_loss[s] for s in STATES if s!=prediction)

    def minimum_report_risk(self, belief: Belief) -> float:
        return min(self.report_risk(belief,p) for p in STATES)

    def expected_reduction(self, belief: Belief, outcomes: OutcomeModel) -> float:
        outcomes=validate_outcome_model(outcomes,STATES)
        expected=0.0
        for likelihood in outcomes.values():
            try:
                posterior,log_q=update_belief(belief,likelihood)
            except ImpossibleEvidence:
                continue
            expected+=math.exp(log_q)*self.minimum_report_risk(posterior)
        delta=self.minimum_report_risk(belief)-expected
        if delta < -1e-10:
            raise ValidationError("expected Bayes risk increased beyond numerical tolerance")
        return max(0.0,delta)

