# Probability Decision Record — CI Diagnosis Agent

## Purpose

This record explains one complete decision made by the CI Diagnosis Agent. It answers the following audit questions:

- What information was visible to the agent?
- Which possible root causes did the agent consider?
- What probability did the agent assign to each root cause?
- Why did the agent choose each diagnostic action?
- What feedback was returned after each action?
- How did each outcome update the agent's belief?
- Why did the agent report a root cause instead of continuing or escalating?

The record can be used to reproduce the decision and investigate an incorrect decision without exposing the correct label to the agent before it finishes.

## Case 1 — Correct automatic diagnosis

This record examines evaluation case **`CI-002`**, the second of the 40 hidden-label cases used in the notebook evaluation.

The agent automatically reported the correct hidden state after three diagnostic actions.

## Information boundaries

The test harness kept the correct label separate from the agent. Before making its terminal decision, the agent received only:

| Agent-visible field | Value |
|---|---|
| Case ID | `CI-002` |
| Normalized failed stage | `Build` |

The raw source step and the correct root-cause label were **not** included in the public case object. The correct label was revealed by the evaluation harness only after the agent had reported or escalated.

## Hidden states

The agent maintained a probability distribution over four mutually exclusive hidden states:

- **Code** — a recent code change caused the failure.
- **Test** — a test or test-related issue caused the failure.
- **Dependency** — a dependency or dependency-related change caused the failure.
- **CI/Config** — a CI workflow, build configuration, permission, runner-resource, or environment configuration issue caused the failure.

The agent did not know which hidden state was correct while making the decision.

## Source prior probabilities

The source workbook contains 375 failed CI jobs. Of these, 309 rows map to the four modeled states and 66 rows remain explicitly out of scope. Laplace smoothing with `alpha = 1.0` was applied to the 309 mapped rows.

| Hidden state | Mapped rows | Smoothed source prior |
|---|---:|---:|
| Code | 54 | 17.57% |
| Test | 120 | 38.66% |
| Dependency | 91 | 29.39% |
| CI/Config | 44 | 14.38% |
| **Total** | **309** | **100.00%** |

These probabilities describe the mapped source population before the failed stage of the current case is considered.

## Stage-conditioned initial belief

The visible `Build` stage was treated as initial evidence. The agent combined the source prior with the smoothed stage likelihood:

\[
P(H\mid \text{Build}) =
\frac{P(\text{Build}\mid H)P(H)}
{\sum_j P(\text{Build}\mid H_j)P(H_j)}.
\]

| Hidden state | Source prior | `P(Build \| state)` | Initial case belief |
|---|---:|---:|---:|
| Code | 17.57% | 50.82% | 24.7149% |
| Test | 38.66% | 28.35% | 30.3284% |
| Dependency | 29.39% | 41.84% | **34.0338%** |
| CI/Config | 14.38% | 27.45% | 10.9228% |
| **Total** | **100.00%** | — | **100.0000%** |

Before any diagnostic test, `Dependency` had the largest probability, but its 34.03% confidence was far below the automatic-reporting threshold.

## Event and decision objective

The event of interest was the root cause of the observed `Build`-stage failure. The agent could:

1. perform another diagnostic test;
2. report one of the four root causes; or
3. send the case to a human reviewer.

The objective was not merely to reduce entropy. The proposed policy selected tests that were expected to reduce the cost of a future wrong report, relative to the effort required to perform the test.

## Candidate diagnostic actions and costs

The stage filter made the following actions eligible for this `Build` case:

| No. | Diagnostic action | Cost units |
|---:|---|---:|
| 1 | Inspect pipeline logs | 1.0 |
| 2 | Inspect failed pipeline stage | 2.0 |
| 3 | Compare with last successful run | 2.0 |
| 4 | Inspect recent code/test changes | 1.0 |
| 5 | Inspect dependency changes | 1.0 |
| 6 | Inspect CI/environment configuration | 2.5 |
| 7 | Search previous incidents/runbooks | 1.0 |
| 8 | Inspect Docker image/cache changes | 1.5 |
| 9 | Inspect server/session state | 1.5 |

`Inspect hosting environment` was not eligible because it is tagged only for the `Deploy / Publish` stage.

The costs are relative diagnostic-effort units. They are not measured minutes or monetary values.

## Terminal decision costs

The notebook used an asymmetric loss model because different wrong diagnoses can have different operational consequences.

| True root cause missed | Miss cost | Wrong-report add-on | Total wrong-report cost |
|---|---:|---:|---:|
| Code | 35 | 5 | 40 |
| Test | 20 | 5 | 25 |
| Dependency | 40 | 5 | 45 |
| CI/Config | 60 | 5 | **65** |

Additional rules:

- A correct automatic report has no terminal misclassification cost; diagnostic costs already spent still apply.
- Human review costs 12 units, in addition to diagnostic costs already spent.
- Missing `CI/Config` has the highest cost because a shared workflow or environment fault can repeatedly affect multiple jobs and teams.

## Policy used for this record

This case was processed by the proposed **`RISK_REDUCTION_PER_COST`** policy, not by the EIG/cost comparison policy.

For each available action `a`, the policy computed:

\[
\text{Score}(a)=
\frac{R(b)-\sum_o P(o\mid b,a)R(b_{a,o})}
{C(a)},
\]

where:

- `b` is the current belief distribution;
- `R(b)` is the minimum expected root-cause reporting loss under belief `b`;
- `o` is either `SIGNAL_FOUND` or `SIGNAL_NOT_FOUND`;
- `b_(a,o)` is the posterior after action `a` returns outcome `o`; and
- `C(a)` is the diagnostic-action cost.

The action with the highest expected risk reduction per cost was selected. Ties were resolved by expected risk reduction, then lower cost, then action name.

### Automatic-reporting rule

The agent reported a root cause only when all of the following conditions were satisfied:

1. the highest-probability state and the minimum-risk reporting state agreed;
2. confidence was at least 90%; and
3. expected reporting risk was no more than 8 cost units.

### Escalation rule

The agent sent the case to a human when it could not safely report and no eligible action remained within either limit:

- maximum diagnostic actions: 8;
- maximum diagnostic cost: 11 units.

## Bayesian feedback update

Every diagnostic action returned one binary outcome. For the observed outcome, the agent updated each state using:

\[
P(H_i\mid o,a,E)=
\frac{P(o\mid H_i,a)P(H_i\mid E)}
{\sum_j P(o\mid H_j,a)P(H_j\mid E)}.
\]

The likelihood is `P(outcome | hidden state, action)`. It is not the posterior probability of the hidden state.

The action-outcome likelihoods are transparent modeling assumptions inherited from the supplied project. They were not directly measured in the 375-row dataset.

## Decision trace

### Step 1 — Inspect dependency changes

The initial policy score for `Inspect dependency changes` was **9.484705 expected risk-cost units per diagnostic-cost unit**. It tied numerically with `Inspect recent code/test changes`; the deterministic tie-break selected `Inspect dependency changes` first.

**Observed outcome:** `No dependency-related change` (`SIGNAL_NOT_FOUND`)

| Likelihood for the observed outcome | Code | Test | Dependency | CI/Config |
|---|---:|---:|---:|---:|
| `P(SIGNAL_NOT_FOUND \| state, action)` | 97.80% | 99.10% | 1.20% | 97.20% |

The negative result strongly reduced the probability of a dependency failure.

| Belief | Code | Test | Dependency | CI/Config |
|---|---:|---:|---:|---:|
| Before action | 24.7149% | 30.3284% | **34.0338%** | 10.9228% |
| After action | 37.0428% | **46.0605%** | 0.6259% | 16.2708% |

| Step-1 audit value | Result |
|---|---:|
| Action cost | 1.0 |
| Cumulative diagnostic cost | 1.0 |
| Expected information gain | 0.819587 bits |
| Realized information gain | 0.380653 bits |
| Expected risk reduction | 9.484705 cost units |
| Entropy before → after | 1.898569 → 1.517915 bits |

The agent did not report because confidence was only 46.06%, the top-probability and minimum-risk report states did not agree, and expected report risk remained above the safety cap.

### Step 2 — Inspect recent code/test changes

After the first update, `Inspect recent code/test changes` had the highest score: **9.953883 expected risk-cost units per diagnostic-cost unit**.

**Observed outcome:** `No relevant change found` (`SIGNAL_NOT_FOUND`)

| Likelihood for the observed outcome | Code | Test | Dependency | CI/Config |
|---|---:|---:|---:|---:|
| `P(SIGNAL_NOT_FOUND \| state, action)` | 2.20% | 0.90% | 98.80% | 97.20% |

The absence of a relevant code or test change sharply reduced the `Code` and `Test` probabilities.

| Belief | Code | Test | Dependency | CI/Config |
|---|---:|---:|---:|---:|
| Before action | 37.0428% | **46.0605%** | 0.6259% | 16.2708% |
| After action | 4.6138% | 2.3470% | 3.5010% | **89.5382%** |

| Step-2 audit value | Result |
|---|---:|
| Action cost | 1.0 |
| Cumulative diagnostic cost | 2.0 |
| Expected information gain | 0.551456 bits |
| Realized information gain | 0.874060 bits |
| Expected risk reduction | 9.953883 cost units |
| Entropy before → after | 1.517915 → 0.643856 bits |
| Expected report risk after action | 4.007713 cost units |

Although expected reporting risk was already below the cap of 8, confidence was **89.5382%**, slightly below the required 90%. The agent therefore performed another test instead of reporting prematurely.

### Step 3 — Inspect CI/environment configuration

`Inspect CI/environment configuration` was the only remaining action with positive expected Bayes-risk reduction at this belief. Its policy score was **0.070134 expected risk-cost units per diagnostic-cost unit**.

**Observed outcome:** `Configuration/environment issue found` (`SIGNAL_FOUND`)

| Likelihood for the observed outcome | Code | Test | Dependency | CI/Config |
|---|---:|---:|---:|---:|
| `P(SIGNAL_FOUND \| state, action)` | 2.20% | 0.90% | 16.90% | 97.20% |

| Belief | Code | Test | Dependency | CI/Config |
|---|---:|---:|---:|---:|
| Before action | 4.6138% | 2.3470% | 3.5010% | **89.5382%** |
| After action | 0.1157% | 0.0241% | 0.6743% | **99.1859%** |

| Step-3 audit value | Result |
|---|---:|
| Action cost | 2.5 |
| Cumulative diagnostic cost | 4.5 |
| Expected information gain | 0.339928 bits |
| Realized information gain | 0.569347 bits |
| Expected risk reduction | 0.175335 cost units |
| Entropy before → after | 0.643856 → 0.074508 bits |
| Expected report risk after action | 0.355724 cost units |

## Posterior summary

| Decision point | Code | Test | Dependency | CI/Config | Agent action |
|---|---:|---:|---:|---:|---|
| After observing `Build` | 24.7149% | 30.3284% | **34.0338%** | 10.9228% | Continue diagnosis |
| After Action 1 | 37.0428% | **46.0605%** | 0.6259% | 16.2708% | Continue diagnosis |
| After Action 2 | 4.6138% | 2.3470% | 3.5010% | **89.5382%** | Continue: below 90% |
| After Action 3 | 0.1157% | 0.0241% | 0.6743% | **99.1859%** | Report `CI/Config` |

## Final decision

After the third diagnostic action:

- the highest-probability state was `CI/Config`;
- the minimum-risk reporting state was also `CI/Config`;
- confidence was **99.1859%**, above the 90% threshold; and
- expected reporting risk was **0.355724**, below the maximum of 8.

The agent therefore performed the terminal action:

**`REPORT_ROOT_CAUSE: CI/Config`**

Only after this terminal action did the evaluation harness reveal that the correct label was `CI/Config`. The automatic report was therefore correct.

The final diagnostic cost was **4.5 units**. Because the report was correct, no wrong-report or human-review cost was added.

## Why this decision is auditable

The final conclusion can be traced to five recorded elements:

1. the source prior and visible `Build`-stage evidence;
2. the policy score used to select each action;
3. the binary outcome returned by each action;
4. the likelihood applied to every hidden state; and
5. the normalized posterior and stopping-rule checks after every update.

The record does not claim that the diagnostic likelihoods were observed in the source dataset. They are declared assumptions, and the evaluation uses a separately perturbed hidden simulator so that the agent is not tested against an exact copy of its own model.

## Audit metadata

| Field | Value |
|---|---|
| Record generated | August 26, 2026, 12:45 AM IST |
| Evaluation case | `CI-002` |
| Source dataset | `zhengly1/workflow_failure/replication-labeling.xlsx` |
| Source records | 375 |
| Four-state mapped records | 309 |
| Out-of-scope source records | 66 |
| Agent version | Robust V2 |
| Policy version | `RISK_REDUCTION_PER_COST` |
| Comparison policies | `EIG_PER_COST`, `LOWEST_COST` |
| Baseline | `STAGE_MAP_BASELINE` |
| Confidence threshold | 0.90 |
| Automatic report-risk cap | 8.0 |
| Maximum action count | 8 |
| Maximum diagnostic budget | 11.0 |
| Random seed | `20260825` |
| Evaluation design | 40 hidden-label cases; 10 per hidden state |

## Reproduction

Run the project notebook from a fresh kernel. The notebook validates the 375-row source workbook, recreates the 40 paired evaluation cases, and saves the following audit files:



Filter the action log and case-results files using:

- `case_id == "CI-002"`; and
- `policy == "RISK_REDUCTION_PER_COST"`.

The reproduced terminal result should be `REPORT_ROOT_CAUSE`, prediction `CI/Config`, confidence approximately `0.9919`, three diagnostic actions, and total diagnostic cost `4.5`.
