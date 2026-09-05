# CI Failure Diagnosis Agent

## Upload summary

This upload adds the CI diagnosis agent, the supporting build/evaluation outputs, and the report summarizing the results.

## Project objective

The objective is to build and study a **transparent Bayesian CI diagnosis agent** that chooses its next investigation using expected information gain per cost. Through a controlled simulation, the project examines the relationship between diagnostic correctness, investigation effort, and the need for human review.

Specifically, the project aims to:

1. **Represent uncertainty clearly** by maintaining probabilities for `Code`, `Test`, `Dependency`, and `CI/Config` failures.
2. **Choose and learn from diagnostic checks** by ranking eligible actions and updating beliefs after each modeled outcome.
3. **Make explicit stopping decisions** by reporting at the 90% confidence threshold or escalating when eligible checks are exhausted.
4. **Compare decision strategies** by evaluating EIG per cost, cost-only, and the fixed `Test` baseline on the same 40 balanced cases.
5. **Make decisions inspectable** through records of selected actions, observed outcomes, belief changes, and final decisions, so failure patterns can guide improvements.


## Problem statement

When a Continuous Integration (CI) pipeline fails, the available evidence can be incomplete or ambiguous. A failed step may point toward several possible causes, and checking logs, recent changes, dependencies, or configuration takes effort. The challenge is deciding **what to investigate next** and **when there is enough evidence to report a likely cause**.

This project treats diagnosis as a sequence of decisions under uncertainty. It explores whether an agent can choose informative checks from its current beliefs, revise those beliefs as evidence arrives, and request human review when the available checks do not resolve the uncertainty.

## What the agent investigates

The notebook represents a failure using one of four hidden states:

| Possible cause | What the label covers |
| --- | --- |
| **Code** | Compilation failures attributed to source-code issues. |
| **Test** | Failures labeled as software-test failures. |
| **Dependency** | Dependency conflicts, unresolved dependencies, and dependency-related setup failures. |
| **CI/Config** | Workflow instructions, project configuration, permissions, and hardware or resource limitations. |

These are broad failure categories. In particular, a failing test can expose a code defect, which makes the boundary between **Code** and **Test** an interesting challenge for this model.

## How the investigation works

1. **Start with the available context.** The evaluation reads the failed step and maps it to a `Build` or `Test` stage using keyword matching.
2. **Form an initial belief.** Prior probabilities and stage likelihoods produce a probability distribution over the four causes.
3. **Choose a useful check.** The EIG policy ranks eligible actions by expected information gain divided by cost.
4. **Learn from the outcome.** A binary diagnostic outcome updates the probabilities using Bayes' rule. The selected action is removed from the remaining catalogue.
5. **Decide whether to stop.** The policy reports when the highest probability reaches **90%**. If confidence remains below that threshold and no eligible action remains, it escalates to human review.

The Bayesian update can be read as:

```text
Updated belief = Current belief × Outcome likelihood
                 then normalize across all four causes
```

For action selection, the notebook uses entropy to measure uncertainty:

```text
EIG(action) = Current uncertainty - Expected uncertainty after the action

Score(action) = EIG(action) / Cost(action)
```

An action is attractive when it is expected to clarify the diagnosis at a reasonable cost. This is a one-step decision rule; its score does not guarantee the best complete sequence of investigations.

### Available diagnostic checks

| Action | Relative cost |
| --- | ---: |
| Inspect pipeline logs | 1.0 |
| Inspect failed pipeline stage | 2.0 |
| Compare with last successful run | 2.0 |
| Inspect recent code/test changes | 1.0 |
| Inspect dependency changes | 1.0 |
| Inspect CI/environment configuration | 2.5 |
| Search previous incidents/runbooks | 1.0 |
| Inspect Docker image/cache changes | 1.5 |
| Inspect hosting environment | 2.0 |
| Inspect server/session state | 1.5 |

Stage tags control which checks are eligible. Costs are declared effort units. The notebook represents these investigations through outcome-likelihood tables; connecting the checks to live CI tools is future work.

## Explore it locally

The saved notebook records **Python 3.12.8**. Python 3.12 is a sensible starting environment. The core model requires no LLM API key.

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/pradnyawant-gote/ci-failure-agent.git
cd ci-failure-agent
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on macOS/Linux, or `.venv\Scripts\activate` in Windows Command Prompt. Then install the dependencies and open the notebook:

```bash
python -m pip install jupyterlab pandas openpyxl
cd experiments
python -m jupyterlab agent_simulation.ipynb
```

Starting from `experiments/` preserves the notebook's existing `../data/replication-labeling.xlsx` path.

### Try the first recommendation

Run notebook sections **1–4** to load the model, action catalogue, policy functions, and existing unit checks. In a new cell immediately afterward, try:

```python
posterior = calculate_posterior("Build")
candidates = get_candidate_actions("Build", actions)

decision = decide_next_step(
    posterior,
    candidates,
    outcome_models,
)

print(decision["decision"])
print(decision["action"]["name"])
```



### Full evaluation status

The committed notebook contains saved evaluation outputs, but a fresh **Run All** currently encounters missing code: the EIG evaluation reads `results` without creating it, and the cost-only evaluator calls an undefined `simulate_action_outcome(...)`. The EIG trace-printing cell also reuses the global name `likelihoods`, which would overwrite the stage model needed later.

Those issues need to be resolved before reproducing the complete policy comparison. The core example above runs independently of those evaluation cells.

## Where the data comes from

The included [replication-labeling.xlsx](data/replication-labeling.xlsx) comes from the [Workflow Failure replication package](https://github.com/zhengly1/workflow_failure), associated with **“Why Do GitHub Actions Workflows Fail? An Empirical Study.”** The upstream package describes manually investigated GitHub Actions failures, including failed steps, root causes, and failure subcategories.

The workbook included here matches the [upstream workbook](https://github.com/zhengly1/workflow_failure/blob/main/replication-labeling.xlsx). The notebook maps selected subcategories to its four states and samples **10 cases per state**, giving **40 evaluation cases**, with `random_state=42`.

The failure labels come from that source data. Priors, stage likelihoods, diagnostic outcome likelihoods, and action costs are hard-coded in the current notebook; it does not estimate them from the workbook. Real investigation outcomes and measured operational costs remain a research gap.

## What the saved experiment shows

The notebook compares three policies:

| Policy | Decision strategy |
| --- | --- |
| **EIG per cost** | Choose the eligible check with the highest expected information gain per cost. |
| **Cost-only** | Choose the cheapest eligible check and update beliefs after its outcome. |
| **Fixed baseline** | Always report Test, with no diagnostic actions. |

The following values are taken from the notebook's **saved 40-case output**. The full experiment has not been reproduced from the current source.

| Metric | EIG per cost | Cost-only | Fixed baseline |
| --- | ---: | ---: | ---: |
| Correct automatic reports / all cases | 55.00% | 52.50% | 25.00% |
| Macro precision | 65.625% | 65.625% | 6.25% |
| Macro recall | 55.00% | 52.50% | 25.00% |
| Human-review rate | 37.50% | 40.00% | 0.00% |
| Average diagnostic cost | 6.5500 | 7.1625 | 0.0000 |
| Average actions | 4.6500 | 5.3500 | 0.0000 |
| Precision among automatic reports | 88.00% | 87.50% | 25.00% |

The notebook calls the first metric “Accuracy.” It counts correct automatic reports across all 40 cases, including escalations in the denominator. Report precision measures correctness only among automatically reported cases. Human-review outcomes are not evaluated.

In this saved run, EIG per cost produces **22 correct automatic reports**, compared with **21** for cost-only, while using fewer actions. Both policies make three incorrect reports, and both have **0% recall for Code**. That failure pattern is a useful direction for improving the evidence model.

This small, balanced simulation is an exploratory comparison. The 90% reporting threshold has not been calibrated against real CI investigations, and these results do not establish production performance.


## Useful next steps

- Restore a complete evaluation that runs from a fresh kernel.
- Improve evidence that distinguishes code defects from test-related failures.
- Estimate outcome likelihoods and action costs from real investigations.
- Test confidence calibration, repeated simulation seeds, and performance on unseen repositories.
- Connect diagnostic actions to CI logs and tools, then evaluate the full workflow.

If you are exploring Bayesian reasoning, CI reliability, or agents that choose what to investigate next, there is plenty here to experiment with. Practical feedback is especially welcome on which checks help engineers most, how much they cost, and when human review is the right next step.
