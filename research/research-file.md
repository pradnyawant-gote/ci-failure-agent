# CI Diagnosis Agent 




## 1. Problem statement

The project investigates a CI diagnosis agent that attempts to identify the labelled cause of a failed Continuous Integration pipeline when the available evidence is incomplete.

The agent:

1. starts with prior probabilities over four possible causes;
2. updates those probabilities using the failed pipeline stage;
3. selects a diagnostic action;
4. receives an action outcome;
5. updates its probabilities again;
6. reports a cause when confidence reaches 90%; and
7. escalates to a human when no diagnostic actions remain.

The agent selects only from a predefined action catalogue. It does not discover unrestricted evidence sources and it does not repair the CI pipeline.

## 2. Project objective

The objective of this notebook is to compare three decision policies on the same 40 balanced CI-failure cases:

- an Expected Information Gain per cost policy;
- a lowest-cost-first policy; and
- a fixed baseline that always predicts `Test`.

The comparison measures correct automatic reports, macro precision, macro recall, human-review rate, diagnostic cost, number of actions, and precision among reported cases.

The notebook is a controlled simulation. It does not establish production accuracy, causal root-cause identification, or real operational cost savings.



## 3. Technical terms

| Term | Meaning in this project |
| --- | --- |
| **CI/CD** | Continuous Integration and Continuous Delivery or Deployment |
| **Hidden state** | The labelled failure category that the agent attempts to infer |
| **Prior** | The starting probability assigned to each hidden state |
| **Likelihood** | Probability of evidence or an action outcome under a hidden state |
| **Posterior** | Updated probability distribution after incorporating evidence |
| **Bayesian update** | Normalized multiplication of current belief and likelihood |
| **Entropy** | A numerical measure of uncertainty in a probability distribution |
| **Expected Information Gain (EIG)** | Expected decrease in entropy after an action |
| **Diagnostic action** | A predefined investigation selected by the policy |
| **Policy** | Rule for choosing the next action or terminal decision |
| **Confidence threshold** | Minimum largest posterior probability required for reporting |
| **Escalation** | Sending an unresolved case to a human after actions are exhausted |
| **Automatic coverage** | Fraction of cases receiving an automatic report |
| **Report precision** | Fraction of reported cases that are correct |
| **Macro precision** | Mean of class-wise precision across the four states |
| **Macro recall** | Mean of class-wise recall across the four states |


## 4. Hidden states

| Hidden state |  Mapping | Important limitation |
| --- | --- | --- |
| **Code** | Project compilation fails due to issues in the source code | Does not locate a particular file, line, or commit |
| **Test** | Software tests fail | Does not distinguish a defective test from a test exposing defective code |
| **Dependency** | Dependency conflicts, unresolved dependencies, or dependency-related environment setup failure | Can overlap conceptually with configuration failures |
| **CI/Config** | Workflow/configuration errors, project configuration errors, permission failures, or workflow hardware/resource limitations | Combines several distinct mechanisms into one label |

Infrastructure and external-service failures are not separate states in this notebook.


## 7. Priors

The hard-codes the following values:

| State | Prior |
| --- | ---: |
| Code | 17.70% |
| Test | 39.34% |
| Dependency | 29.84% |
| CI/Config | 13.11% |

The rounded values sum to 99.99%. The posterior calculation normalizes them, so the case-specific posterior still sums to 1.

This simulation code does not contain code that recomputes these priors from `replication-labeling.xlsx`. Their provenance therefore cannot be verified from this notebook alone.


## 8. Failed-stage likelihood model

The notebook hard-codes the following likelihoods:

| Hidden state | Build | Test | Setup / Dependency | Quality / Analysis | Deploy / Publish | Ambiguous | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Code | 0.574 | 0.185 | 0.074 | 0.019 | 0.000 | 0.074 | 0.074 |
| Test | 0.358 | 0.533 | 0.000 | 0.058 | 0.000 | 0.033 | 0.017 |
| Dependency | 0.429 | 0.132 | 0.176 | 0.055 | 0.033 | 0.077 | 0.099 |
| CI/Config | 0.275 | 0.100 | 0.125 | 0.050 | 0.050 | 0.150 | 0.250 |

Although seven stages are defined here, the evaluation preprocessing reduces every case to only:

- `Test` when the step contains `test`, `tests`, `junit`, `pytest`, or `cucumber`;
- `Build` for every other step.

Therefore, five likelihood columns are never used in the saved evaluation.

### Initial posteriors used by the evaluation

| Failed stage | Code | Test | Dependency | CI/Config |
| --- | ---: | ---: | ---: | ---: |
| Build | 24.99% | 34.65% | 31.49% | 8.87% |
| Test | 11.10% | 71.10% | 13.36% | 4.45% |

These values are visible repeatedly in the saved case traces.


## 9. Bayesian update

The notebook implements the update in this form:

**Posterior(state) = Current belief(state) × Likelihood(outcome given state) ÷ Total probability of the outcome**

The failed-stage update uses the same pattern:

**Initial posterior(state) = Prior(state) × Likelihood(failed stage given state) ÷ Total probability of the failed stage**

The current source does not show whether the true label was hidden from the missing outcome-simulation and EIG-evaluation functions. Label leakage therefore cannot be ruled out from the attached file alone.


## 10. Candidate actions and costs

| Diagnostic action | Eligible stage(s) | Cost |
| --- | --- | ---: |
| Inspect pipeline logs | All | 1.0 |
| Inspect failed pipeline stage | All | 2.0 |
| Compare with last successful run | All | 2.0 |
| Inspect recent code/test changes | Build, Test, Quality / Analysis | 1.0 |
| Inspect dependency changes | Build, Setup / Dependency | 1.0 |
| Inspect CI/environment configuration | Build, Test, Setup / Dependency, Quality / Analysis, Deploy / Publish | 2.5 |
| Search previous incidents/runbooks | All | 1.0 |
| Inspect Docker image/cache changes | Build, Deploy / Publish | 1.5 |
| Inspect hosting environment | Deploy / Publish | 2.0 |
| Inspect server/session state | Build, Deploy / Publish | 1.5 |

The policy removes an action after selecting it, so an action is not repeated within a case.

Because the evaluation uses only Build and Test stages, `Inspect hosting environment` is never eligible. Docker and server/session checks can be eligible only for Build cases.

The costs are hard-coded normalized values. The notebook does not explain how they were measured.


## 11. Outcome model

Each action has two hard-coded outcome likelihoods. The following table records the positive outcome probability for each state; the second outcome is intended to be its complement.

| Action and positive outcome | Code | Test | Dependency | CI/Config |
| --- | ---: | ---: | ---: | ---: |
| Pipeline logs — relevant failure signal found | 0.174 | 0.036 | 0.024 | 0.056 |
| Failed stage — stage-specific clue found | 0.935 | 0.938 | 0.855 | 0.611 |
| Last successful run — meaningful difference found | 0.022 | 0.009 | 0.012 | 0.056 |
| Recent code/test changes — relevant change found | 0.978 | 0.991 | 0.012 | 0.028 |
| Dependency changes — dependency-related change found | 0.022 | 0.009 | 0.988 | 0.028 |
| CI/environment — configuration/environment issue found | 0.022 | 0.009 | 0.169 | 0.972 |
| Previous incidents — similar incident found | 0.717 | 0.938 | 0.506 | 0.194 |
| Docker/image — image/cache issue found | 0.022 | 0.018 | 0.048 | 0.111 |
| Hosting — environment issue found | 0.022 | 0.018 | 0.169 | 0.111 |
| Server/session — server/session issue found | 0.022 | 0.009 | 0.012 | 0.056 |

These values are not estimated from data in the attached notebook. They are model assumptions.

### Numerical inconsistency

FoTest, two outcome pairs sum to 1.001 instead of 1.000 because the code uses:

- 0.938 and 0.063 for the failed-stage-clue action; and
- 0.938 and 0.063 for the previous-incidents action.

The EIG calculation treats both values as branch probabilities without renormalizing them. This small rounding inconsistency should be corrected before rerunning the experiment.


## 12. EIG policy

The policy first checks whether the largest posterior probability is at least 0.90. If not, it ranks eligible actions.

The notebook uses these simple equations:

**EIG(action) = Current entropy − Expected entropy after the action**

**Score(action) = EIG(action) ÷ Cost(action)**

The action with the highest EIG-per-cost score is selected.

If an action has no outcome model, it is placed in an unknown-EIG list and ranked by lowest cost. In the current notebook, all ten defined actions have outcome models, so this fallback is normally unused.

EIG per cost is a one-step heuristic. The notebook does not prove that it minimizes long-term diagnosis cost or error.


## 13. Cost-only policy

The cost-only policy:

1. checks the same 0.90 reporting threshold;
2. chooses the lowest-cost eligible remaining action;
3. updates the posterior after the simulated outcome; and
4. escalates when no actions remain.

Actions with equal cost retain their original catalogue order because Python sorting is stable.


## 14. Baseline

The baseline is:

BASELINE_ROOT_CAUSE = "Test"

It always reports Test, performs no diagnostic action, has zero diagnostic cost, and never escalates.

It is not a stage-conditioned baseline and it is not a Bayesian baseline.


## 15. Stopping and escalation

### Report

The EIG and cost-only policies report when:

**Maximum posterior probability ≥ 0.90**

The reported cause is the state with the largest posterior.

### Escalate

They escalate only when no candidate action remains and the posterior is still below 0.90.

### What is not implemented

- no maximum action count apart from exhaustion of the catalogue;
- no maximum diagnostic budget;
- no minimum expected benefit requirement;
- no human-review cost;
- no state-dependent error cost;
- no Bayes-risk cap; and
- no calibration test for the 0.90 threshold.


## 16. Evaluation dataset preparation

The study attempts to read:

`../data/replication-labeling.xlsx`

It maps selected sub-categories into the four hidden states, then samples 10 cases per state.

### Saved evaluation composition

| Hidden state | Cases |
| --- | ---: |
| Code | 10 |
| Test | 10 |
| Dependency | 10 |
| CI/Config | 10 |
| **Total** | **40** |

### Important limitations

- The notebook does not validate that the workbook exists before reading it.
- It does not verify the expected columns.
- It does not print the source-row count, mapped-row count, excluded-row count, duplicates, or repository distribution.
- It reduces the stage to Build or Test only.
- The same 40 cases are used for final comparison without a separate validation set for selecting the 0.90 threshold.
- The missing simulator code prevents verification of how action outcomes were generated.
- The missing EIG evaluation code prevents verification that the true label remained hidden from the agent.


## 17. Saved evaluation results

The following table is copied from the notebook's saved output.

| Metric | EIG/cost | Cost-only | Baseline |
| --- | ---: | ---: | ---: |
| Accuracy as defined by notebook | 55.00% | 52.50% | 25.00% |
| Macro precision | 65.625% | 65.625% | 6.25% |
| Macro recall | 55.00% | 52.50% | 25.00% |
| Human-review rate | 37.50% | 40.00% | 0.00% |
| Average diagnostic cost | 6.5500 | 7.1625 | 0.0000 |
| Average actions | 4.6500 | 5.3500 | 0.0000 |
| Report precision | 88.00% | 87.50% | 25.00% |

### Correct interpretation

The notebook defines accuracy as:

**Accuracy = Correct automatic reports ÷ All 40 cases**

Escalated cases are counted as not correct. This is more precisely an **overall correct automatic-report rate**, not the final accuracy of a human-agent system.

Report precision is the same idea commonly called selective accuracy:

**Report precision = Correct automatic reports ÷ All automatic reports**

Human-review outcomes are not evaluated.

## 18. Counts derived from the saved case table

| Quantity | EIG/cost | Cost-only | Baseline |
| --- | ---: | ---: | ---: |
| Correct automatic reports | 22 | 21 | 10 |
| Wrong automatic reports | 3 | 3 | 30 |
| Automatic reports | 25 | 24 | 40 |
| Human escalations | 15 | 16 | 0 |
| Total diagnostic actions | 186 | 214 | 0 |
| Total diagnostic cost | 262.0 | 286.5 | 0.0 |

These counts are derived directly from the saved 40-row actual-versus-predicted output and the reported averages.

## 19. Class-wise results derived from saved predictions

### EIG/cost policy

| True state | Correct reports | Wrong reports | Escalations | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Code | 0 | 3 | 7 | 0.00% | 0.00% |
| Test | 5 | 0 | 5 | 62.50% | 50.00% |
| Dependency | 9 | 0 | 1 | 100.00% | 90.00% |
| CI/Config | 8 | 0 | 2 | 100.00% | 80.00% |

The Test precision is 62.50% because the policy reports `Test` eight times: five true Test cases and three Code cases.

### Cost-only policy

| True state | Correct reports | Wrong reports | Escalations | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Code | 0 | 3 | 7 | 0.00% | 0.00% |
| Test | 5 | 0 | 5 | 62.50% | 50.00% |
| Dependency | 8 | 0 | 2 | 100.00% | 80.00% |
| CI/Config | 8 | 0 | 2 | 100.00% | 80.00% |

Both diagnostic policies have 0% Code recall in the saved run. Neither policy correctly reports a Code case, and both wrongly report Test for Code cases 14, 15, and 16.


## 20. What the saved comparison supports

Within the stored 40-case output:

- EIG/cost has one more correct automatic report than cost-only: 22 versus 21.
- EIG/cost escalates one fewer case: 15 versus 16.
- EIG/cost uses 28 fewer actions in total: 186 versus 214.
- EIG/cost has 24.5 lower total diagnostic cost units: 262.0 versus 286.5.
- Both policies make three wrong automatic reports.
- Both policies fail to correctly report any Code case.
- The fixed baseline's 25% result is expected for a balanced four-state set because it always predicts one class.

The output suggests a small advantage for EIG/cost over cost-only on this stored run. It does not establish that EIG/cost is generally superior because:

- the simulator definition is missing;
- the run cannot currently be reproduced;
- the evaluation contains only 40 balanced cases;
- uncertainty intervals are absent; and
- no repeated-seed or repository-held-out evaluation is provided.


## 21. Observed failure patterns

The notebook does not include a formal error-audit section. The following patterns are derived from its saved case table.

### Pattern 1: Code cases are never correctly reported

For Code cases 11–20:

- cases 14, 15, and 16 are wrongly reported as Test;
- the remaining seven cases are escalated.

This produces 0% Code recall for both diagnostic policies.

### Pattern 2: High confidence can follow overlapping evidence

The likelihood values for Code and Test are very similar for several actions, especially recent code/test changes and previous incidents. This can push a Code case toward Test when the Test prior is already larger.

### Pattern 3: EIG and cost-only behave almost identically

They differ in the final prediction table only for Dependency case 26:

- EIG/cost reports Dependency;
- cost-only escalates.

This single case produces the 2.5-percentage-point difference in the notebook's accuracy metric.

### Pattern 4: Escalation is treated as incorrect

The metric function counts an escalated case in the denominator but not as a correct outcome. The performance of the human after escalation remains unknown.


## 22. Research questions

### Hidden states

1. Are Code and Test mutually exclusive in the label guide?
2. Should CI/Config be divided into configuration, permissions, resource, and environment states?
3. How should multiple simultaneous causes be represented?
4. How should unknown or unmapped causes be handled?
5. What evidence establishes the ground-truth cause?

### Evidence

1. What does each positive or negative action outcome mean operationally?
2. How should missing, failed, and inconclusive actions be represented?
3. Can action likelihoods be learned from real CI investigation traces?
4. Which observations are correlated and may be double-counted?
5. Can structured logs provide richer evidence than a binary outcome?

### Actions

1. Which actions can be executed through the selected CI platform?
2. Which actions only observe the system and which can change it?
3. How should time, compute, API calls, and engineer effort be measured?
4. When should the agent stop before exhausting all actions?
5. Would value of information or risk reduction be more appropriate than entropy reduction?

### Errors

1. Why do both policies have 0% Code recall?
2. Why are Code cases 14–16 classified as Test?
3. How sensitive are results to the hard-coded likelihoods?
4. How much does case 26 affect the policy comparison?
5. How should escalations be scored after human outcomes become available?




