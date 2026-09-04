# Research Preparation: An Uncertainty-Aware CI Diagnosis Agent

**Prepared:** 4 September 2026  
**Audience:** Beginner researcher  
**Topic:** An AI agent that investigates a failed Continuous Integration (CI) run when the root cause is not fully observed

## Evidence labels used in this file

- **Verified external fact:** Supported by a linked primary or official source.
- **Current project fact:** Reported by the existing project artifacts, but not independently reproduced while preparing this file.
- **Design proposal:** A reasonable choice to test; it is not a fact about the world.
- **Untested claim:** Requires data, an experiment, or a user study before it can be written as a result.
- **Inference:** A conclusion drawn from sources or the current design; it is labelled as such.

This distinction is important because a research prototype, a mathematical definition, and an experimentally supported result are not the same thing.

---

## 1. Precise research framing

### What is already defined in the current project

The current project can be described as follows:

1. A CI run fails.
2. The actual root cause is treated as hidden.
3. The agent maintains a probability distribution over possible causes.
4. It chooses a diagnostic action, observes the result, and updates its probabilities.
5. It either reports a cause or sends the case to a human.

The beginner-facing explanation currently uses four broad causes:

- `Code`
- `Test`
- `Dependency`
- `CI/Config`

The project currently contains at least two distinct recorded versions:

- `CI_Diagnosis_Agent.ipynb` uses 11 states: ten sufficiently represented dataset subcategories plus `OTHER_RARE_OR_NOVEL`. It reports 44 simulated evaluation cases and compares `EIG_PER_COST`, `EIG_ONLY`, and `FIXED_ORDER_BASELINE`.
- `probability-decision-record.md` labelled **Robust V2** uses four mutually exclusive states, 40 hidden-label evaluation cases, and a `RISK_REDUCTION_PER_COST` policy. It reports that a source workbook contains 375 failed jobs, of which 309 map to its four states and 66 are out of scope.

These are different taxonomies, policies, and evaluations. They must not be combined into one result table. The paper should select and version one experiment, or clearly report them as separate studies.

The 11-state notebook's action interface is:

- `GET_MORE_EVIDENCE(test)`
- `REPORT_ROOT_CAUSE`
- `SEND_TO_HUMAN`

In that notebook, evidence outcomes are binary: `EVIDENCE_FOUND` and `EVIDENCE_NOT_FOUND`. Its policy reports automatically when the largest belief is at least `0.90`; otherwise, it selects the largest `expected information gain / action cost` score and escalates if no usable action or budget remains. These are **version-specific project facts and design choices**, not externally established optimal values.

The executed notebook output reports, for `EIG_PER_COST` on 44 cases, automatic coverage `0.1591`, selective accuracy `0.7143`, human-review rate `0.8409`, mean actions `5.4091`, and mean diagnostic cost `6.4977`. These values were read from the saved notebook output but were not rerun during this review. The notebook itself states that the policy should not be declared the winner without choosing an explicit objective and cost model.

### A defensible one-sentence problem statement

> This research studies whether a cost-aware sequential diagnosis policy can select useful evidence, update calibrated beliefs over CI failure causes, and decide when to diagnose or defer to a human more safely and efficiently than one-shot and fixed-order baselines.

### A beginner-friendly formal model

Let:

- \(H\) be the hidden failure cause;
- \(b_t(h)\) be the agent's belief that \(H=h\) after step \(t\);
- \(a_t\) be the diagnostic action selected at step \(t\);
- \(o_{t+1}\) be the observed result of that action; and
- \(P(o\mid h,a)\) be the observation or likelihood model.

The Bayesian update is:

\[
b_{t+1}(h)=
\frac{P(o_{t+1}\mid h,a_t)b_t(h)}
{\sum_{h'}P(o_{t+1}\mid h',a_t)b_t(h')}.
\]

One possible one-step information score is:

\[
\operatorname{EIG}(a)=
\mathcal{H}(b_t)-
\mathbb{E}_{o\sim P(o\mid b_t,a)}
[\mathcal{H}(b_{t+1})],
\]

where \(\mathcal{H}\) is entropy. A policy may use `EIG(a) / cost(a)` as a **myopic heuristic**. It chooses the action expected to reduce uncertainty most per unit of modeled cost at the next step. This ratio is not automatically the globally optimal policy.

### Is this a POMDP?

Possibly, but the term must be used carefully. A Partially Observable Markov Decision Process (POMDP) is a standard framework for selecting actions when the true state is not directly observed; the agent instead acts on a belief state. See [Kaelbling, Littman, and Cassandra (1998)](https://doi.org/10.1016/S0004-3702(98)00023-X).

- If the root cause remains fixed and actions only reveal information, **Bayesian sequential diagnosis**, **active diagnosis**, or **active hypothesis testing** is the cleaner description.
- If actions can change the system, or the system state changes during diagnosis, a **POMDP** becomes a more natural model.
- Selecting only the next action using `EIG / cost` does not by itself mean that a complete POMDP has been solved.

---

## 2. Technical terms for this problem

| Technical term | Beginner-friendly meaning | How it applies here | Important caution |
| --- | --- | --- | --- |
| **CI/CD failure diagnosis** | Determining why an automated build, test, or delivery workflow failed | The overall application domain | Prediction that a run will fail is different from diagnosing why it failed |
| **Root-cause analysis (RCA)** | Finding the underlying reason for an observed failure | The intended final output | A correlated signal is not automatically a causal root cause |
| **Root-cause localization** | Narrowing the failure to a component, change, dependency, test, or environment | Useful when an exact cause cannot yet be named | Localization can be evaluated at several levels, such as category, file, component, or commit |
| **Fault detection, isolation, and identification** | Detecting a failure, separating candidate causes, and identifying its type | CI already detects the failure; the agent focuses mainly on isolation and identification | These stages should not be merged into one accuracy value without explanation |
| **Hidden state / latent state / hypothesis** | The unknown condition the agent is trying to infer | A candidate CI root cause | The states must be defined, labelled, and tested for overlap |
| **Observation / evidence / telemetry** | Information visible to the agent | Logs, failed step, stack trace, diff, prior runs, dependency status, runner status, or a rerun result | Missing evidence and negative evidence are not the same thing |
| **Belief state** | A probability distribution over the hidden states | The agent's current uncertainty over causes | A normalized distribution is not necessarily calibrated |
| **Prior probability** | Belief before the new diagnostic result | May come from historical cause frequencies conditioned on stage, repository, or environment | Historical frequency can drift and may not transfer to another repository |
| **Likelihood or observation model** | The probability of an observation under a cause and selected action | \(P(o\mid H,a)\) drives each update | It must be estimated without using the test case's hidden label during diagnosis |
| **Posterior probability** | Updated belief after observing new evidence | The result of the Bayesian update | Do not use an earlier posterior as if it were a likelihood |
| **Bayesian sequential diagnosis** | Repeatedly update beliefs while gathering evidence | A precise description if the cause remains fixed | Requires a credible observation model |
| **Active diagnosis** | Choose tests or probes specifically to separate possible causes | The agent selects what to inspect next | The available action set limits what the agent can discover |
| **Active information acquisition / controlled sensing** | Choose which information source to query | Reading more logs, comparing a last-green run, or rerunning a test | Information access can have cost, delay, permission, and side-effect constraints |
| **Expected information gain (EIG)** | Expected reduction in uncertainty from an action | Can rank candidate diagnostic actions | High information gain does not always minimize operational harm |
| **Value of information (VoI)** | Expected improvement in the final decision from obtaining information | Better suited than entropy alone when errors have unequal costs | VoI requires a utility or loss model that must be justified |
| **Entropy** | A numerical summary of uncertainty in a probability distribution | Used in an EIG calculation | Lower entropy does not guarantee that the most likely diagnosis is correct |
| **Bayesian decision theory / Bayes risk** | Select an action by considering probabilities and consequences | Can compare diagnosing, gathering evidence, and escalating | Error costs must be measured or explicitly labelled as assumptions |
| **Cost-sensitive decision-making** | Different actions and errors have different costs | Rerunning a pipeline, human review, delay, and a wrong report may differ | Arbitrary cost units cannot be presented as real economic cost |
| **Optimal stopping** | Decide when more evidence is no longer worth its cost | Governs report versus continue versus escalate | A fixed 90% threshold is a policy choice until validated |
| **Selective prediction / abstention / reject option** | Predict on some cases and defer uncertain cases | `SEND_TO_HUMAN` is the reject option | Accuracy should be reported together with coverage or escalation rate |
| **Human-in-the-loop escalation** | A person handles cases outside the agent's safe operating region | Used when budget is exhausted or confidence is insufficient | Human decisions also have delay, cost, and error |
| **Confidence calibration** | A stated probability should match the observed correctness frequency | A 0.90 belief should be correct about 90% of the relevant reported cases if calibrated | Classification accuracy alone cannot establish calibration |
| **Brier score / log loss / ECE** | Metrics for probability quality | Evaluate beliefs, not only final labels | ECE depends on binning; use more than one calibration view |
| **Risk-coverage curve** | Error rate as the agent handles more cases instead of escalating | Evaluates the report threshold | Comparing accuracy alone can reward excessive escalation |
| **Open-set recognition / out-of-distribution (OOD) detection** | Recognize that a case may not belong to any known class | Relevant to `OTHER_RARE_OR_NOVEL` | An `OTHER` label does not prove that unseen causes will be detected |
| **Flaky test / nondeterministic test** | A test can pass and fail without a relevant code change | Rerun outcomes may provide evidence about test-related causes | A pass on retry is evidence, not proof, of flakiness |
| **Fault localization** | Rank program elements that may be responsible for a failure | Useful if the target becomes a file, line, or change rather than a broad class | This is a different output granularity from four-way classification |
| **Causal diagnosis** | Determine which factor produced the failure | The strongest interpretation of “root cause” | Observational correlations alone normally support weaker language |
| **Data leakage / label leakage** | Information unavailable at decision time enters training or evaluation | The true root-cause label must remain hidden until reporting or escalation | Random splits can also leak repository or time-specific patterns |
| **Temporal drift / concept drift** | Failure patterns change over time | Dependencies, runners, workflows, and tools evolve | Priors and likelihoods require monitoring and re-estimation |
| **Policy** | A rule mapping the current belief and context to an action | For example, threshold plus EIG/cost selection | A heuristic policy should be called a heuristic unless optimality is proven |
| **Trajectory / decision trace** | The complete sequence of beliefs, actions, observations, and costs | Supports transparent evaluation and debugging | A readable trace is evidence of auditability, not necessarily human understanding |

Foundational sources for the uncertainty terms include [Lindley (1956) on information from experiments](https://doi.org/10.1214/aoms/1177728069), [Guo et al. (2017) on confidence calibration](https://proceedings.mlr.press/v70/guo17a.html), and [Geifman and El-Yaniv (2017) on selective classification](https://papers.nips.cc/paper/7073-selective-classification-for-deep-neural-networks).

---

## 3. Useful search queries

### A. Core CI diagnosis literature

Copy these into Google Scholar, ACM Digital Library, IEEE Xplore, Scopus, or Web of Science:

1. `("continuous integration" OR "CI pipeline") AND ("failure diagnosis" OR "root cause analysis" OR "failure classification")`
2. `("build failure" OR "pipeline failure") AND (diagnosis OR localization OR taxonomy) AND software`
3. `"continuous integration" AND "build log" AND (classification OR diagnosis)`
4. `"CI failure" AND ("root cause" OR "failure cause") AND empirical`
5. `"automated debugging" AND "continuous integration"`
6. `"root cause localization" AND software AND logs`
7. `"failure diagnosis" AND "GitHub Actions"`
8. `"pipeline failure" AND (Jenkins OR GitLab OR "Azure Pipelines") AND diagnosis`

Add `-manufacturing -medical -electrical` in a general search engine if “CI” or “fault diagnosis” produces unrelated engineering results.

### B. Decision-making under incomplete information

1. `"Bayesian sequential diagnosis" software failures`
2. `"active diagnosis" AND software systems`
3. `"active hypothesis testing" AND fault diagnosis`
4. `POMDP AND (debugging OR "fault diagnosis")`
5. `"expected information gain" AND diagnostic test selection`
6. `"value of information" AND software diagnosis`
7. `"controlled sensing" AND fault isolation`
8. `"optimal stopping" AND diagnostic decisions`
9. `"cost-sensitive" AND sequential diagnosis`
10. `"Bayesian experimental design" AND software testing`

### C. Uncertainty, abstention, and unknown causes

1. `"confidence calibration" AND software engineering`
2. `"selective prediction" AND software defects`
3. `(abstention OR "reject option") AND root cause classification`
4. `"risk coverage" AND failure diagnosis`
5. `("open set" OR "out of distribution") AND software failure classification`
6. `"unknown root cause" AND anomaly diagnosis`
7. `"probability calibration" AND imbalanced multiclass classification`

### D. Evidence quality and causality

1. `"causal root cause analysis" AND distributed systems`
2. `"log-based root cause analysis" AND causal`
3. `"negative evidence" AND Bayesian diagnosis`
4. `"conditionally dependent evidence" AND Bayesian diagnosis`
5. `"data leakage" AND software defect prediction`
6. `"temporal validation" AND software engineering machine learning`
7. `"repository-level split" AND software defect prediction`

### E. Flaky tests and reruns

1. `"flaky test" AND "continuous integration" AND root cause`
2. `"passed on retry" AND flaky test`
3. `"root causing flaky tests" industrial`
4. `"International Dataset of Flaky Tests" OR IDoFT`
5. `"flaky test" AND (rerun OR nondeterminism) AND dataset`

### F. Datasets and reproducibility

1. `TravisTorrent continuous integration dataset`
2. `BugSwarm reproducible CI failures fixes`
3. `GitBug-Actions reproducible GitHub Actions bug-fix benchmark`
4. `Defects4J reproducible software faults`
5. `IDoFT flaky tests dataset`
6. `"CI build" dataset root cause labels`
7. `"build failure taxonomy" dataset`

Useful starting points are [TravisTorrent](https://doi.org/10.1109/MSR.2017.24), [BugSwarm](https://doi.org/10.1109/ICSE.2019.00048), [GitBug-Actions](https://doi.org/10.1145/3639478.3640023), [Defects4J](https://github.com/rjust/defects4j), and [IDoFT](https://github.com/TestingResearchIllinois/idoft). These resources do not necessarily contain the exact hidden-state labels required by this project; their schemas and ground-truth procedures must be audited before use.

### G. Recent adjacent agentic-CI work

1. `"On the Reliability of Agentic AI in Continuous Integration Pipelines"`
2. `"Reliability of AI Bots Footprints in GitHub Actions CI/CD Workflows"`
3. `agentic AI AND continuous integration AND reliability`
4. `coding agents AND CI failures AND empirical study`

The 2026 paper [*On the Reliability of Agentic AI in Continuous Integration Pipelines*](https://2026.msrconf.org/details/msr-2026-mining-challenge/25/On-the-Reliability-of-Agentic-AI-in-Continuous-Integration-Pipelines) studies CI outcomes associated with agent-authored pull requests. It is relevant adjacent work, but it does **not** by itself validate a sequential CI diagnosis agent.

### H. Practitioner searches

1. `site:reddit.com/r/cicd "failed build" diagnosis`
2. `site:reddit.com/r/devops "CI failure" "what do you check first"`
3. `site:reddit.com/r/sre "root cause" uncertainty escalation`
4. `site:reddit.com/r/jenkinsci build failed logs`
5. `site:reddit.com/r/softwaretesting flaky test rerun CI`
6. `site:x.com (CI OR DevOps) (diagnosis OR observability OR debugging)`

---

## 4. Relevant Reddit communities

**Verification note:** The communities and cited example discussions were resolvable on 4 September 2026. Relevance is an assessment based on their stated scope or representative discussions. Reddit responses are anecdotal practitioner input; they can generate requirements and hypotheses, but they should not be used alone to claim prevalence, causality, or model effectiveness.

| Community | Why it is relevant | Best use for this project | Boundary or caution |
| --- | --- | --- | --- |
| [r/cicd](https://www.reddit.com/r/cicd/) | It is directly focused on software delivery and CI/CD. A discussion there identifies failed-step logs, the triggering diff, and recent test/job history as useful diagnostic signals, while warning that a successful rerun does not prove flakiness. [Example](https://www.reddit.com/r/cicd/comments/1vsaivn/if_you_could_keep_only_three_signals_for/) | Validate the evidence list, action ordering, and cost model | Avoid presenting the tool as finished; ask one narrow workflow question at a time |
| [r/devops](https://www.reddit.com/r/devops/) | Practitioners discuss real build-failure workflows, ownership, CI tools, and operational trade-offs. A directly relevant thread asks how engineers choose the next investigation when CI evidence is incomplete. [Example](https://www.reddit.com/r/devops/comments/1vojtkx/how_do_you_actually_diagnose_a_ci_integrationtest/) | Learn actual investigation sequences and what “useful evidence” means in practice | DevOps responsibilities vary across organizations; do not generalize one response to all teams |
| [r/sre](https://www.reddit.com/r/sre/) | SRE discussions cover incident diagnosis, escalation, observability, and human coordination. [Example on RCA ownership](https://www.reddit.com/r/sre/comments/1hyxanf/sre_and_incident_response/) | Refine abstention, escalation, audit trails, and high-cost error definitions | Production incident response is broader than CI diagnosis; keep the boundary explicit |
| [r/jenkinsci](https://www.reddit.com/r/jenkinsci/) | Jenkins users discuss long console logs, plugin effects, runner failures, and ambiguous build outcomes. [Example](https://www.reddit.com/r/jenkinsci/comments/1twm10f/jenkins_console_output_is_the_worst_documentation/) | Obtain tool-specific evidence and action examples if Jenkins is in scope | Findings may not transfer to GitHub Actions, GitLab, or other CI systems |
| [r/GithubActions](https://www.reddit.com/r/GithubActions/) | The community discusses workflow triggers, job/step behavior, reruns, and workflow statistics. [Example](https://www.reddit.com/r/GithubActions/comments/12paeec/workflow_statistics/) | Define a concrete first platform and map each action to an API or log source | Only include it as empirical evidence if GitHub Actions is actually evaluated |
| [r/gitlab](https://www.reddit.com/r/gitlab/) | GitLab users discuss pipelines, jobs, runners, schedules, retries, and configuration failures. [Example](https://www.reddit.com/r/gitlab/comments/1rkhcwr/cicd_pipelines_not_triggering_automatically/) | Test whether the taxonomy and actions transfer to GitLab | Platform-specific runner and permission behavior can change the observation model |
| [r/azuredevops](https://www.reddit.com/r/azuredevops/) | Discussions include Azure Pipelines, hosted/self-hosted agents, authentication, service connections, and failure traces. [Example](https://www.reddit.com/r/azuredevops/comments/1d8d0i9/azure_devops_error_message_bash_exited_with_code/) | Collect examples of infrastructure and authentication failure evidence | Do not mix Azure Data Factory and Azure Pipelines cases without separate labels |
| [r/softwaretesting](https://www.reddit.com/r/softwaretesting/) | Test engineers discuss flaky automation, CI-only failures, rerun behavior, test data, and environmental causes. [Example](https://www.reddit.com/r/softwaretesting/comments/1fnogrv/stability_issues_with_automated_tests_in_ci/) | Improve the `Test` state and model the meaning of rerun evidence | A test failure can originate in code or infrastructure; avoid assuming “failed test = test defect” |
| [r/mlops](https://www.reddit.com/r/mlops/) | The community discusses model monitoring, calibration, agent evaluation, pipelines, leakage, and deployment. A directly related CI diagnosis-agent discussion is visible there. [Example](https://www.reddit.com/r/mlops/comments/1w2fuwp/im_building_a_cicd_diagnosis_agent_that_needs_to/) | Ask about probability calibration, evaluation design, drift, and agent observability | It is less suitable than CI practitioner communities for establishing operational ground truth |
| [r/learnmachinelearning](https://www.reddit.com/r/learnmachinelearning/) | It is beginner-oriented and suitable for questions about Bayesian updates, calibration, metrics, and experimental design | Obtain understandable feedback on the probability model and presentation | It is not the strongest source for real CI workflows. Your supplied post is [here](https://www.reddit.com/r/learnmachinelearning/comments/1w7a83i/can_an_ai_agent_decide_what_evidence_it_needs/); its engagement was not independently verified in this review |

### Better questions to post on Reddit

Avoid asking, “Is my agent good?” Ask questions that produce observable requirements:

1. “After a failed CI step, which three signals do you inspect first, and what would make you change that order?”
2. “When a failed test passes on rerun, what additional evidence do you require before calling it flaky?”
3. “What diagnostic action is expensive enough that you avoid it unless another signal is present?”
4. “At what point do you stop investigating and ask the code owner, test owner, or platform team?”
5. “Can one CI failure have multiple root causes in your postmortem process? How do you record them?”
6. “What information is available at failure time but should not be visible to an automated diagnosis tool?”

---

## 5. Relevant researchers and engineers on X

**Verification note:** The linked X profiles and public areas of work were verified from profile pages or official biographies on 4 September 2026. This list does not claim that every person studies Bayesian CI diagnosis specifically, endorses this project, or posts frequently on X.

| Person and X account | Relevant public work | What to learn from them | Supporting source |
| --- | --- | --- | --- |
| [Nicole Forsgren — @nicolefv](https://x.com/nicolefv) | Empirical DevOps and software-delivery research | Measurement quality, valid organizational metrics, survey/observational evidence, and avoiding unsupported productivity claims | [Official biography](https://nicolefv.com/about) and [DORA research program](https://dora.dev/) |
| [Jez Humble — @jezhumble](https://x.com/jezhumble) | Continuous delivery, deployment pipelines, and DevOps | Correct CI/CD terminology, delivery-system boundaries, and useful outcome measures | [Continuous Delivery biography](https://continuousdelivery.com/about/) |
| [Charity Majors — @mipsytipsy](https://x.com/mipsytipsy) | Observability and operating distributed systems | Designing evidence that supports new diagnostic questions rather than relying only on fixed dashboards | [Public biography](https://www.honeycomb.io/author/charity) |
| [Cindy Sridharan — @copyconstruct](https://x.com/copyconstruct) | Distributed systems, observability, and testing | Differences among monitoring, observability, evidence quality, and partial system failures | [Distributed Systems Observability](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/) |
| [John Allspaw — @allspaw](https://x.com/allspaw) | Incident analysis, resilience engineering, and human factors | How engineers reason under ambiguity and why a single simplistic “root cause” can misrepresent complex failures | [USENIX SREcon 2026 biography](https://www.usenix.org/conference/srecon26emea/presentation/allspaw) |
| [Brendan Gregg — @brendangregg](https://x.com/brendangregg) | Systems performance analysis and evidence-driven diagnosis | Practical diagnostic methods for CPU, memory, I/O, latency, and infrastructure-related states | [Official website](https://www.brendangregg.com/) |
| [Andreas Zeller — @AndreasZeller](https://x.com/AndreasZeller) | Automated debugging, software testing, and mining software archives | Automated cause isolation, experimental debugging, and the difference between locating and repairing a fault | [CISPA profile](https://cispa.de/en/people/zeller) |
| [Martin Fowler — @martinfowler](https://x.com/martinfowler) | Continuous Integration, refactoring, and software-delivery practices | Precise definitions of CI and the role of automated builds and tests | [Continuous Integration article](https://martinfowler.com/articles/continuousIntegration.html) |

When contacting or tagging people, first read their published work and ask one answerable question. Do not send a generic request to “review my project.”

---

## 6. Research questions about hidden states, evidence, actions, and errors

### A. Hidden-state questions

1. What exactly is one hidden state: a broad category, a failed component, a faulty change, or the human-confirmed root cause?
2. Is the unit of diagnosis a pipeline run, job, step, test, commit, or incident?
3. Are the four broad states or the 11 implementation states the official research taxonomy?
4. Are the states mutually exclusive, or can `Code` and `Dependency` both be causal?
5. Are the states collectively exhaustive? What happens when none fits?
6. Does `OTHER_RARE_OR_NOVEL` mean “rare known cause,” “unseen cause,” “unmapped cause,” or all three?
7. Does the hidden state remain fixed during investigation, or can a rerun, dependency update, or service recovery change it?
8. Who assigns the ground-truth state, using which evidence and annotation guide?
9. How are disagreements between annotators resolved?
10. Should the taxonomy be hierarchical, such as `Dependency → unavailable repository` and `Dependency → incompatible version`?
11. Should priors depend on failed stage, repository, language, workflow, runner, or recent history?
12. How will the system handle a cause that appears in a new repository but was absent during training?

### B. Evidence questions

1. Which observations are available immediately at failure time?
2. Which observations require a new action, permission, API call, rerun, or human response?
3. What does `EVIDENCE_FOUND` mean for each action? It may require a different definition for every test.
4. Is `EVIDENCE_NOT_FOUND` genuine negative evidence, an inconclusive result, or missing data?
5. What is the false-positive and false-negative rate of each diagnostic test?
6. How will \(P(o\mid H,a)\) be estimated, smoothed, and validated?
7. Are evidence items conditionally dependent? For example, a stack trace and a failed-step log may repeat the same signal.
8. Does a successful rerun increase the probability of flakiness without forcing the posterior to `Test`?
9. Can a test outcome be contaminated by a changing external service or runner image?
10. Is the last-green comparison always available and truly comparable?
11. Could the agent see the final fix, issue label, human RCA, or another field that leaks the answer?
12. How will secrets, personal data, tokens, and proprietary code be removed from logs?
13. How old can historical evidence be before it is considered stale?
14. How are contradictory observations represented?

GitHub's official documentation confirms that workflow-run logs expose job and step status and that users can rerun workflows or jobs; it also documents additional runner diagnostic logging. See [workflow history](https://docs.github.com/actions/managing-workflow-runs/viewing-workflow-run-history), [workflow logs](https://docs.github.com/actions/managing-workflow-runs/using-workflow-run-logs), and [debug logging](https://docs.github.com/actions/managing-workflow-runs/enabling-debug-logging). This verifies availability for GitHub Actions, not for every CI platform.

### C. Action questions

1. What is the complete action set for version 1?
2. Which actions only observe the system, and which actions intervene in it?
3. Can an action change the evidence available to later actions?
4. Can an action change or mask the original failure?
5. Is every action available in every repository and CI platform?
6. What are all possible outcomes of each action, including timeout, permission denied, missing artifact, and inconclusive?
7. What unit defines action cost: seconds, compute minutes, API calls, money, cognitive effort, or a normalized research score?
8. Are costs fixed, or do they depend on repository size and queue delay?
9. Is `EIG / cost` compared with expected error reduction, value of information, random order, fixed order, and an oracle?
10. May the agent repeat an action? If so, when does repetition add new evidence?
11. What is the maximum action budget?
12. When should the agent report, continue, or escalate?
13. What information is included in a human escalation packet?
14. Is the agent allowed only to diagnose, or also to recommend or execute a fix?

### D. Error questions

1. What counts as a wrong diagnosis when several causes contributed?
2. Which is more harmful: a wrong automatic report or an unnecessary human escalation?
3. What is the cost of stopping too early?
4. What is the cost of continuing after enough evidence is available?
5. What is the cost of selecting an uninformative action?
6. How is an unknown cause forced into a known class detected and counted?
7. How will overconfidence be distinguished from ordinary classification error?
8. How will label noise or an incorrect human RCA affect training and evaluation?
9. How will confirmation bias be detected if the policy repeatedly chooses evidence that supports its current top state?
10. Does a balanced evaluation set hide performance under the natural deployment distribution?
11. Are errors reported per state, repository, platform, and action depth?
12. Will confidence intervals be reported for every small-sample metric?
13. Can the agent fail safely when a tool call times out or returns malformed evidence?
14. Will a security error, leaked secret, or unauthorized log access be treated as an agent failure?

---

## 7. Claim register: what needs a source or a test

This register covers claims visible in the current problem statement and reported prototype. It should be extended whenever the paper adds a new factual, comparative, causal, performance, safety, or generalization statement.

| ID | Potential claim | Current status | Required source or test | Safe wording before validation |
| --- | --- | --- | --- | --- |
| C1 | CI failures can be represented by `Code`, `Test`, `Dependency`, and `CI/Config` | Design proposal | Published taxonomy plus an audit of labelled cases; report overlap and unmapped cases | “We define four broad illustrative categories.” |
| C2 | The 11 implemented states cover the intended diagnosis domain | Untested claim | Label guide, frequency table, inter-annotator agreement, and out-of-scope analysis | “The prototype uses ten represented subcategories plus an `OTHER` state.” |
| C3 | One CI case has one true root cause | Modeling assumption | Multi-label audit and annotation policy | “Version 1 assumes one primary labelled cause.” |
| C4 | The root cause stays fixed during diagnosis | Modeling assumption | Define the diagnostic window and test cases where reruns or external recovery alter state | “The current model treats the cause as static during one trajectory.” |
| C5 | Failure information is incomplete | Empirical domain claim | Field schema showing what is available at each decision time; practitioner interviews or logs | “The study evaluates cases where the selected initial fields do not uniquely identify the labelled cause.” |
| C6 | Logs, job status, reruns, and diagnostic logs are available evidence | Verified only for specified platforms | Cite platform documentation and record permissions/version | “GitHub Actions exposes these items under documented conditions.” |
| C7 | Historical frequencies are valid priors | Untested claim | Training-only estimation, smoothing, time/repository stratification, and drift analysis | “Priors are estimated from the designated training data.” |
| C8 | A version's reported prior percentages are genuine dataset frequencies | Version-specific project fact | Reproduce counts from that version's source workbook and mapping code | “This version reports these priors; they require a reproducible count audit.” |
| C9 | \(P(o\mid H,a)\) values reflect real diagnostic behavior | Untested claim unless estimated | Estimate on training data; report counts and uncertainty; test on held-out data | “The prototype uses an assumed or estimated observation model”; state which one |
| C10 | Binary evidence outcomes are sufficient | Untested claim | Compare binary outcomes with richer categorical or continuous observations | “Version 1 deliberately simplifies outcomes to binary values.” |
| C11 | Evidence items are independent after conditioning on the state | Modeling assumption | Dependence analysis or a model that represents shared causes | “The update makes the following conditional-independence assumptions…” |
| C12 | Bayesian updating improves diagnosis | Untested comparative claim | Compare against no-update and one-shot baselines on the same held-out cases | “The agent performs Bayesian updates; benefit is evaluated separately.” |
| C13 | The posterior probabilities are trustworthy | Untested calibration claim | Reliability diagrams, Brier score, log loss, ECE, and calibration on held-out data | “Values are model beliefs, not guaranteed correctness probabilities.” |
| C14 | EIG selects the best next diagnostic action | Overbroad claim | Define “best”; compare with oracle, random, fixed-order, cost-only, and value-based policies | “The heuristic selects the highest modeled one-step information gain.” |
| C15 | `EIG / action cost` is optimal | Unsupported unless proven | Formal optimality proof or replace “optimal” with “heuristic”; evaluate long-horizon regret | “The policy uses a myopic cost-normalized heuristic.” |
| C16 | A 0.90 threshold is safe or appropriate | Design choice | Tune only on validation data; report risk-coverage curves and state-specific errors | “The prototype uses a provisional 0.90 threshold.” |
| C17 | Sending uncertain cases to humans improves safety | Untested system claim | Measure human accuracy, turnaround time, and combined human-agent outcomes | “The design includes escalation as a safety mechanism to be evaluated.” |
| C18 | Human review costs 12 units | Current project assumption | Explain the unit and derivation; conduct time/cost study or sensitivity analysis | “Human review is assigned 12 normalized cost units in the simulation.” |
| C19 | Wrong-report costs represent operational harm | Current project assumption | Stakeholder elicitation, measured incident data, or sensitivity analysis | “Wrong-report costs are experimental assumptions, not dataset facts.” |
| C20 | The source contains 375 jobs, 309 four-state mappings, and 66 out-of-scope cases | Robust V2 record fact | Publish source provenance, inclusion rules, mapping script, checksum, and exact experiment version | “The Robust V2 decision record reports these counts.” |
| C21 | The 40 Robust V2 cases are independent and representative | Unclear | Sampling protocol, deduplication, natural prevalence comparison, and power/uncertainty analysis | “Robust V2 records a 40-case preliminary evaluation.” |
| C22 | The 11-state notebook evaluates 44 simulated cases | Saved-notebook fact | Rerun from a clean environment; publish generator, seed, case file, and checksum | “The saved notebook output contains 44 simulated cases.” |
| C23 | On those 44 cases, `EIG_PER_COST` has 15.91% automatic coverage, 71.43% selective accuracy, 84.09% human review, 5.4091 mean actions, and 6.4977 mean diagnostic cost | Saved-notebook output, not rerun here | Reproduce trajectories; define every denominator and cost unit; add confidence intervals | “The saved 11-state notebook run reports these preliminary values.” |
| C24 | `EIG_PER_COST` is the best policy | Not supported by the current notebook | Choose a primary objective; use paired comparisons, uncertainty intervals, and sensitivity analysis | “No single policy is declared best; rankings change with the selected metric and cost model.” |
| C25 | The 40-case Robust V2 and 44-case EIG results describe one experiment | Version conflict | Reconcile filenames, commit/version IDs, taxonomies, policies, seeds, and case sets | “The project currently contains two distinct recorded experiments.” |
| C26 | The agent decides what evidence it “needs” | Potential overclaim | Demonstrate that action selection improves a defined utility; compare with alternatives | “The agent selects the next action from a predefined catalog using its current model.” |
| C27 | The agent diagnoses a causal root cause | Untested causal claim | Reliable human RCA, fix-validation evidence, intervention, or a clearly weaker target definition | “The agent predicts the dataset's labelled cause category.” |
| C28 | `OTHER_RARE_OR_NOVEL` handles unseen causes | Untested open-set claim | Hold out entire cause types; test unknown detection and false-unknown rate | “The label reserves capacity for unmapped cases; novel-cause detection remains to be tested.” |
| C29 | The agent is transparent or explainable | Requires an operational definition | Test trace completeness, reproducibility, expert comprehension, and error localization | “The system records an inspectable probability-decision trace.” |
| C30 | The agent reduces diagnosis time or cost | Untested operational claim | Shadow deployment or controlled human comparison using measured time and compute | “The simulation evaluates normalized diagnostic cost.” |
| C31 | The results generalize to new repositories, languages, or CI platforms | Untested generalization claim | Leave-one-repository-out, temporal, and cross-platform evaluation | “Results apply only to the evaluated cases and platform representation.” |
| C32 | The agent is production-safe | Unsupported at prototype stage | Security/privacy review, permission boundaries, failure injection, audit, and human oversight study | “The prototype is research software and does not establish production safety.” |
| C33 | Recent agentic-CI studies validate this diagnosis design | Incorrect inference | Compare task definitions; cite as related work only | “Recent studies of agent-authored PRs and CI outcomes are adjacent, not direct validation.” |

### Claims that normally require citations

Cite a credible source for:

- definitions of CI, POMDPs, calibration, selective prediction, active diagnosis, and flaky tests;
- statements about what a CI platform exposes or permits;
- descriptions, sizes, labels, and limitations of public datasets;
- claims about what prior studies found; and
- claims about how practitioners usually behave.

### Claims that normally require your own test

Test rather than merely cite:

- accuracy, precision, calibration, cost, action count, and escalation rate of your agent;
- whether one policy outperforms another;
- whether a threshold is safe;
- whether the hidden-state taxonomy covers the target domain;
- whether probabilities generalize across time and repositories;
- whether humans find the trace understandable; and
- whether the system reduces real diagnosis time.

---

## 8. Parts of the problem that are not yet clear

| Unclear part | What currently appears clear | What must be decided | Why it matters |
| --- | --- | --- | --- |
| **CI diagnosis versus production incident response** | The current request and prototype concern CI failure diagnosis | Remove or isolate earlier “incident agent” terminology | Incident states, evidence, actions, and costs are different from CI diagnosis |
| **Official hidden-state taxonomy** | Four broad states are used for explanation; 11 are used in implementation | Choose the paper's target taxonomy and publish the mapping | Metrics and likelihoods are meaningless if labels change between sections |
| **Unit of analysis** | A failed CI case is the input | Specify run, job, step, test, or commit | Determines features, labels, independence, and sample size |
| **Target platform** | The design is currently presented generically | Select one first platform or define a tested abstraction across platforms | Available logs, reruns, permissions, and costs differ by platform |
| **Target ecosystem** | A previous example involved an Ant/Ivy build step | State supported languages, build systems, and repositories | Cause distributions and diagnostic actions may be ecosystem-specific |
| **Single versus multiple causes** | The probability model appears single-label | Define primary-cause rules or use a multi-label/causal graph model | Real failures may involve interacting code, dependency, and environment factors |
| **Ground truth** | A correct label exists in evaluation artifacts | Explain who created it and what evidence confirms it | Evaluation cannot be trusted without defensible labels |
| **Initial evidence** | Failed stage is at least one input | List every field visible before action 1 | Prevents leakage and makes cases reproducible |
| **Action catalog** | Generic evidence-gathering is implemented | Define each real action, prerequisites, outputs, timeout, and side effects | EIG can only rank actions represented in the observation model |
| **Observation semantics** | Outcomes are binary | Define “found,” “not found,” “missing,” “failed,” and “inconclusive” per action | Treating missing as negative evidence can produce false confidence |
| **Likelihood estimation** | Bayesian updates use \(P(o\mid H,a)\) | State whether values are empirical, expert-elicited, synthetic, or hybrid | Posterior quality depends directly on these values |
| **Conditional dependence** | Not yet specified | Model dependence or justify an approximation | Repeated versions of the same log signal can be double-counted |
| **Cost definition** | Actions and errors have numeric costs | Define units, source, uncertainty, and sensitivity range | Cost-based conclusions otherwise remain arbitrary |
| **Stopping rule** | A 0.90 threshold and budget are reported | Define how selected, whether state-specific, and how recalibrated | A threshold is only meaningful when probabilities are calibrated |
| **Meaning of escalation** | A human receives uncertain cases | Define the packet, human role, response, and final label | Needed to evaluate total system performance rather than agent-only accuracy |
| **Role of an LLM** | The decision logic is probability-based | State whether an LLM parses logs, proposes actions, explains results, or is absent | “AI agent” can otherwise conceal which component caused an error |
| **Novel causes** | An `OTHER_RARE_OR_NOVEL` state exists | Separate known rare, unmapped, and truly unseen cases | These require different evaluation protocols |
| **Dataset provenance** | Current artifacts report workbook and case counts | Publish source, license, mapping, exclusions, and versions | Required for reproducibility and ethical data use |
| **Evaluation split and version** | Robust V2 reports 40 cases; the 11-state notebook reports 44 simulated cases | Select one version or document both separately; define train/validation/test isolation and repository/time grouping | Mixing versions or repeatedly reusing cases can invalidate comparisons |
| **Deployment authority** | The current agent appears to diagnose rather than fix | State explicitly whether it may only report, recommend, or execute | Risk changes sharply when the agent can mutate code or CI configuration |
| **Security and privacy** | Not yet specified | Define secret scrubbing, least privilege, retention, and audit | CI logs and artifacts can contain credentials or proprietary information |

---

## 9. Recommended beginner research design

### Primary research question

> Compared with one-shot, fixed-order, random, and cost-only baselines, does a calibrated cost-aware sequential policy improve the trade-off among diagnosis error, evidence-gathering cost, and human escalation on held-out CI failures?

### Suggested subquestions

- **RQ1 — Beliefs:** Are the probabilities calibrated after each evidence update?
- **RQ2 — Actions:** Does the selected diagnostic action reduce uncertainty or final decision loss more than baselines?
- **RQ3 — Stopping:** What report threshold provides an acceptable risk-coverage trade-off?
- **RQ4 — Robustness:** What happens on a new repository, later time period, missing evidence, or unseen cause?
- **RQ5 — Auditability:** Can an engineer reconstruct why the agent selected each action and identify where a wrong trajectory began?

### Minimum evaluation plan

1. **Freeze the scope.** Start with diagnosis only, one CI platform, one unit of analysis, and no automatic fixes.
2. **Write the label guide.** Define every state, positive/negative examples, multi-cause policy, and `OTHER` policy.
3. **Write the action specification.** For each action, record prerequisites, outcomes, errors, permissions, latency, and cost.
4. **Split data before estimation.** Prefer temporal and repository-aware separation. Estimate priors and likelihoods only from training data; tune thresholds only on validation data.
5. **Keep final test cases untouched.** Do not use their labels to choose evidence, parameters, thresholds, or future hypotheses.
6. **Compare baselines on identical cases.** Include one-shot maximum-prior, fixed order, random action, cost-only, EIG, and an oracle upper bound if possible.
7. **Evaluate probabilities and decisions.** Report macro-F1, per-state recall, report precision, coverage/escalation, Brier score, log loss, reliability diagrams, risk-coverage curves, average actions, elapsed time, and cost.
8. **Report uncertainty.** Publish raw counts and bootstrap confidence intervals. Forty cases can support a pilot, but strong comparative claims require more diverse cases.
9. **Test difficult conditions.** Remove evidence, corrupt evidence, delay actions, hold out a cause type, and evaluate new repositories or later time periods.
10. **Run in shadow mode first.** Let the agent recommend without changing code or blocking pipelines; compare its trajectory with human diagnosis.
11. **Preserve every decision trace.** Record timestamp, evidence available, belief vector, selected action, expected score, observed outcome, cost, stop reason, and final ground truth.

### Important metrics and what they answer

| Metric | Research question answered |
| --- | --- |
| Diagnostic accuracy and macro-F1 | Does the final category match the labelled cause, including minority states? |
| Per-state precision and recall | Which causes are confused or missed? |
| Report precision | How often is an automatic report correct? |
| Coverage / escalation rate | How often does the agent decide rather than defer? |
| Risk-coverage curve | How does error change as the agent handles more cases? |
| Brier score and log loss | Are the full probability distributions useful? |
| Reliability diagram and ECE | Do confidence values align with observed correctness? |
| Average actions, time, and measured cost | How much investigation is required? |
| Cost-sensitive loss | What happens when wrong reports and delays have different consequences? |
| Unknown-cause detection metrics | Can the system avoid forcing novel cases into known states? |
| Paired bootstrap interval | Is an observed policy difference stable across sampled cases? |

---

## 10. Starter source list

These are starting points, not proof that the proposed agent works:

1. Leslie Pack Kaelbling, Michael Littman, and Anthony Cassandra, [“Planning and Acting in Partially Observable Stochastic Domains”](https://doi.org/10.1016/S0004-3702(98)00023-X), 1998 — belief-state decision-making under partial observability.
2. Dennis Lindley, [“On a Measure of the Information Provided by an Experiment”](https://doi.org/10.1214/aoms/1177728069), 1956 — a foundation for expected information gain.
3. Chuan Guo et al., [“On Calibration of Modern Neural Networks”](https://proceedings.mlr.press/v70/guo17a.html), 2017 — confidence calibration and calibration evaluation.
4. Yonatan Geifman and Ran El-Yaniv, [“Selective Classification for Deep Neural Networks”](https://papers.nips.cc/paper/7073-selective-classification-for-deep-neural-networks), 2017 — prediction with rejection/abstention.
5. Moritz Beller, Georgios Gousios, and Andy Zaidman, [“TravisTorrent”](https://doi.org/10.1109/MSR.2017.24), 2017 — a CI research dataset joining Travis CI and GitHub data.
6. David Tomassi et al., [“BugSwarm”](https://doi.org/10.1109/ICSE.2019.00048), 2019 — reproducible CI failures and fixes.
7. Saavedra et al., [“GitBug-Actions”](https://doi.org/10.1145/3639478.3640023), 2024 — reproducible bug-fix benchmarks using GitHub Actions.
8. [Defects4J](https://github.com/rjust/defects4j) — reproducible real faults and supporting research infrastructure.
9. [International Dataset of Flaky Tests (IDoFT)](https://github.com/TestingResearchIllinois/idoft) — flaky-test data for Java and Python projects.
10. Moataz Chouchen et al., [“On the Reliability of Agentic AI in Continuous Integration Pipelines”](https://2026.msrconf.org/details/msr-2026-mining-challenge/25/On-the-Reliability-of-Agentic-AI-in-Continuous-Integration-Pipelines), 2026 — adjacent evidence about agent-authored pull requests and CI outcomes, not direct validation of sequential diagnosis.
11. [GitHub Actions workflow-run documentation](https://docs.github.com/actions/managing-workflow-runs/viewing-workflow-run-history) — official evidence and action availability for one concrete CI platform.
12. [OpenTelemetry logging specification](https://opentelemetry.io/docs/specs/otel/logs/) — structured logs and correlation using execution context.

---

## Final research-positioning advice

The strongest honest contribution is not “the agent thinks like a human” or “the agent finds the true root cause.” A defensible contribution would be:

> We formalize CI diagnosis as a transparent sequential decision problem, implement a reproducible belief-update and evidence-selection policy, and evaluate its accuracy-cost-escalation trade-off under explicit assumptions.

Until broader evaluation is complete, describe current performance percentages as **preliminary results from the exact named and versioned evaluation set**. Describe the 0.90 threshold, action costs, likelihoods, and label taxonomy as **design choices or estimated model inputs**. Describe the agent as selecting among **predefined diagnostic actions**, not as independently discovering any evidence source it could possibly need.
