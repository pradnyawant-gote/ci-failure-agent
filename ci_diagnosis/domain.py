"""Small domain vocabulary and typed boundaries; no I/O or policy decisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

if TYPE_CHECKING:
    from .records import Observation

STATES = ("Code", "Test", "Dependency", "CI/Config")
STAGES = (
    "Build",
    "Test",
    "Setup / Dependency",
    "Quality / Analysis",
    "Deploy / Publish",
    "Ambiguous",
    "Unknown",
)

Belief = Mapping[str, float]
OutcomeModel = Mapping[str, Belief]
JsonObject = dict[str, Any]


class ObservationProvider(Protocol):
    """Providers must bound their own calls and honor the supplied deadline.

    The runner never discovers tools before local eligibility/permission checks.
    Built-ins are local lookups. Arbitrary blocking external adapters remain
    outside the demonstrated execution/deployment contract.
    """

    def available(self, action_id: str) -> bool: ...

    def observe(self, case_id: str, action_id: str, attempt: int, timeout_seconds: float) -> Observation: ...


class RankedAction(TypedDict):
    action_id: str
    name: str
    cost: float
    eig: float
    score: float
    catalogue_order: int
    expected_risk_reduction: float


class LegacyActionSpec(TypedDict):
    name: str
    tags: list[str]
    cost: float
    outcomes: list[str]
