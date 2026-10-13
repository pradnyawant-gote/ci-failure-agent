"""Explicit synthetic scenarios, distinct from the missing historical generator.

The default environment uses normalized notebook likelihoods. Noise/reliability
parameters are scenario assumptions, not empirical measurements. A SHA-256 key
makes each case/action/attempt observation independent of policy execution order.
Correlated and multi-fault stress scenarios are deliberately labeled synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Iterable
from types import MappingProxyType
from typing import Any

from .model import STATES,Model
from .probability import ValidationError, finite_number
from .records import Observation, fingerprint, plain,identifier

SIMULATOR_VERSION = "keyed-synthetic-environment/1"


def keyed_uniform(seed: int, *parts: object) -> float:
    key = fingerprint([SIMULATOR_VERSION, seed, *parts])
    # 53 bits maps exactly to a standard double fraction in [0,1).
    return (int(key[:16], 16) >> 11) / (1 << 53)


@dataclass(frozen=True)
class Scenario:
    name: str = "model_matched_assumptions"
    noise: float = 0.0
    missing_rate: float = 0.0
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    inconclusive_rate: float = 0.0
    correlation: float = 0.0
    signal_bias: float = 0.0

    def __post_init__(self) -> None:
        for field in ("noise", "missing_rate", "error_rate", "timeout_rate", "inconclusive_rate", "correlation"):
            finite_number(getattr(self, field), field, minimum=0, maximum=1)
        finite_number(self.signal_bias, "signal_bias", minimum=-1, maximum=1)
        if sum((self.missing_rate, self.error_rate, self.timeout_rate, self.inconclusive_rate)) > 1:
            raise ValidationError("non-signal event rates must sum to at most one")
        if not isinstance(self.name, str) or not self.name or len(self.name)>128:
            raise ValidationError("scenario name is required")


class OutcomeBank:
    """Harness-owned truth; policy receives only available()/observe().

    Static checks reuse the same outcome on retries: retrying an unchanged
    artifact is not independent diagnostic evidence. Error status can recover
    per attempt; the evidence_id is unchanged. Banks can be materialized/hashed.
    """

    def __init__(self, model: Model, truths: Mapping[str,str | tuple[str,...]], seed: int=42,
                 scenario: Scenario | None=None, unavailable: Iterable[str]=()) -> None:
        if type(seed) is not int or seed<0:
            raise ValidationError("seed must be a nonnegative integer")
        if not isinstance(truths, Mapping):
            raise ValidationError("truth store must be a mapping")
        checked = {}
        for case_id, truth in truths.items():
            identifier(case_id,"case_id",maximum=128)
            if not isinstance(truth,(str,tuple,list)):
                raise ValidationError("truth must be a state or distinct cause sequence")
            causes = (truth,) if isinstance(truth, str) else tuple(truth)
            if not causes or any(not isinstance(s,str) or s not in STATES for s in causes) or len(set(causes))!=len(causes):
                raise ValidationError("unsupported synthetic truth")
            checked[case_id] = causes
        self._truths = MappingProxyType(checked)
        self._actions = MappingProxyType({a.action_id: a for a in model.actions})
        if any(set(a.outcomes) != {"signal","no_signal"} for a in model.actions):
            raise ValidationError("synthetic bank supports binary actions only; use a replay provider for richer models")
        self._seed = seed
        self._scenario = scenario or Scenario()
        if not isinstance(self._scenario,Scenario):
            raise ValidationError("scenario must be validated Scenario")
        self._unavailable = frozenset(unavailable)
        if not self._unavailable.issubset(self._actions):
            raise ValidationError("unknown unavailable action")
        self._model_hash = model.model_hash

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def scenario(self) -> Scenario:
        return self._scenario

    @property
    def model_hash(self) -> str:
        return self._model_hash

    def available(self, action_id: str) -> bool:
        return action_id in self._actions and action_id not in self._unavailable

    def observe(self, case_id: str, action_id: str, attempt: int=0, timeout_seconds: float=30) -> Observation:
        if type(attempt) is not int or attempt<0:
            raise ValidationError("attempt must be a nonnegative integer")
        finite_number(timeout_seconds,"timeout_seconds",minimum=0)
        if case_id not in self._truths or action_id not in self._actions:
            raise ValidationError("unknown case/action in outcome bank")
        action = self._actions[action_id]
        evidence_id = fingerprint([SIMULATOR_VERSION, self.seed, self.scenario, case_id, action_id])
        event_id = fingerprint([evidence_id, attempt])
        if not self.available(action_id):
            return Observation(action_id, event_id, "unavailable", cost=0)
        if timeout_seconds <= 0:
            return Observation(action_id, event_id, "timeout", cost=0)
        u = keyed_uniform(self.seed, self.scenario, case_id, action_id, attempt, "status")
        cutoff = 0.0
        for status, rate in (("missing", self.scenario.missing_rate), ("tool_error", self.scenario.error_rate),
                             ("timeout", self.scenario.timeout_rate), ("inconclusive", self.scenario.inconclusive_rate)):
            cutoff += rate
            if u < cutoff:
                return Observation(action_id, event_id, status, cost=action.cost,
                                   detail="synthetic reliability event; not a negative diagnostic signal")
        # Binary signal propensity for multi-fault stress is noisy-OR. This is
        # a declared environment assumption, not agent multi-label support.
        no_signal = 1.0
        for state in self._truths[case_id]:
            no_signal *= 1 - action.outcomes["signal"][state]
        p = (1 - self.scenario.noise) * (1 - no_signal) + self.scenario.noise * 0.5
        p = min(1.0, max(0.0, p + self.scenario.signal_bias))
        shared = keyed_uniform(self.seed, self.scenario, case_id, "shared_latent")
        independent = keyed_uniform(self.seed, self.scenario, case_id, action_id, "signal")
        use_shared = keyed_uniform(self.seed, self.scenario, case_id, action_id, "correlation") < self.scenario.correlation
        outcome = "signal" if (shared if use_shared else independent) < p else "no_signal"
        return Observation(action_id, event_id, "signal", outcome, evidence_id, action.cost)

    def materialize(self, max_attempts: int=1) -> dict[str,Any]:
        if type(max_attempts) is not int or not 1<=max_attempts<=100:
            raise ValidationError("materialization requires 1..100 attempts")
        return {f"{case_id}:{action_id}:{attempt}": plain(self.observe(case_id, action_id, attempt))
                for case_id in sorted(self._truths) for action_id in sorted(self._actions)
                for attempt in range(max_attempts)}

    def manifest(self, max_attempts: int=1) -> dict[str,Any]:
        return {"version": SIMULATOR_VERSION, "seed": self.seed, "scenario": plain(self.scenario),
                "agent_model_hash": self.model_hash, "truth_hash": fingerprint(self._truths),
                "bank_hash": fingerprint(self.materialize(max_attempts)),
                "unavailable": sorted(self._unavailable),
                "status": "synthetic assumptions; no observed CI diagnostic outcomes"}


class SequenceProvider:
    """Manual replay: each item is a typed Observation or (action_id, outcome).

    Bare strings are accepted only by the legacy notebook compatibility layer.
    A missing sequence item produces missing evidence rather than a false signal.
    """

    def __init__(self, observations: Iterable[Observation | tuple[str,str]], action_ids: Iterable[str]) -> None:
        self._items = iter(observations)
        self._available = frozenset(action_ids)

    def available(self, action_id: str) -> bool:
        return action_id in self._available

    def observe(self, case_id: str, action_id: str, attempt: int=0, timeout_seconds: float=30) -> Observation:
        try:
            item = next(self._items)
        except StopIteration:
            return Observation(action_id, f"missing:{case_id}:{action_id}:{attempt}", "missing", cost=0,
                               detail="manual replay sequence exhausted")
        if isinstance(item, Observation):
            return item
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValidationError("manual replay requires (action_id, canonical outcome)")
        item_action, outcome = item
        return Observation(item_action, f"replay:{case_id}:{action_id}:{attempt}", "signal", outcome,
                           f"replay:{case_id}:{action_id}:{attempt}")

