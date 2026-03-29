# FDS AI Workflow Audit — Eval Report

**Date:** 2026-03-29
**Tool version:** `claude/great-lovelace`
**Eval runner:** `evals/eval_runner.py`

---

## Summary Scoring Table

| Metric | Target | Actual | Status |
|---|---|---|---|
| True positive rate (Tier 1) | 100% | 5/8 (62%) | FAIL |
| True positive rate (Tier 2) | 90%+ | 2/3 (66%) | FAIL |
| True positive rate (Tier 3) | 90%+ | 2/5 (40%) | FAIL |
| False positive rate (correctly not flagged HIGH) | >90% | 0/3 (0%) | FAIL |
| Risk score accuracy (±0.5 of expected threshold) | 80%+ | 3/4 (75%) | FAIL |
| Cost estimate accuracy (±25%) | 90%+ | N/A — no cost baseline defined | — |
| Checkpoint recommendations match | 90%+ | 1/3 required checkpoints generated | FAIL |

**Overall:** The tool captures the right signal for well-structured failure types (cascading, context degradation, sycophantic confirmation) but has systematic gaps in silent failure detection for data sources, false positive inflation for parallel data lookups, and a hard scoring ceiling that prevents financial-impact steps from registering their true risk.

---

## Tier 1 — CEO Agent

**Workflow:** `evals/workflows/ceo_agent.yml`
**Results:** `evals/results/ceo_agent/`

### True Positive Hits/Misses

| Step | Expected Flag | Failure Type | Result | Detail |
|---|---|---|---|---|
| collect_open_brain | Cold start risk | cascading_failure | **HIT** | Flagged HIGH — 5 downstream steps |
| collect_zoho_mail | Silent failure risk HIGH | silent_failure | **MISS** | Tool does not assess `data_lookup` steps for silent failure |
| write_daily_brief | Data quality risk | sycophantic_confirmation | **HIT** | Flagged MEDIUM — ai_action with upstream lookups |
| format_brief | Context degradation | context_degradation | **HIT** | Flagged HIGH — 11-step workflow, generation step |
| format_brief | Specification drift | specification_drift | **HIT** | Flagged MEDIUM — depth=2, workflow_length>5 |
| send_email | Irreversibility flag | (checkpoint) | **HIT** | `post-action verification` checkpoint generated (recommended) |
| parse_reply | Tool selection risk | tool_selection_error | **MISS** | Step has no `tools:` listed; assessment returns None when n=0 |
| write_decisions | Cascading failure | cascading_failure | **MISS** | Terminal step has 0 descendants; in-workflow cascading check returns None |

**TP Rate: 5/8 = 62.5%**

### False Positive Analysis

The tool flags `cascading_failure HIGH` for every data-collection step because each has 5 downstream nodes. This produces 3 confirmed false positives for steps with proven graceful degradation:

| Step | Tool Verdict | Expected | Why it's a FP |
|---|---|---|---|
| collect_github | cascading_failure HIGH | Should NOT flag HIGH | GitHub failure degrades gracefully (brief runs with remaining sources) |
| collect_pipeline | cascading_failure HIGH | Should NOT flag HIGH | Fallback exists: pipeline reconstructed from client_notes |
| collect_zoho_calendar | cascading_failure HIGH | Should NOT flag HIGH | Low data sensitivity, low blast radius |

**Incorrectly flagged: 3/3 = 100% FP rate** for the explicitly-called-out set. The cascading failure check has no awareness of graceful degradation, fallback paths, or per-step blast radius. It fires for every step with 4+ downstream nodes regardless of actual impact.

Additional noise: `collect_mercury` (critical sensitivity, legitimate concern) also gets only a `cascading_failure HIGH` flag — same flag as the harmless sources — diluting signal.

---

## Tier 2 — Standard Workflows

### 2A: Customer Support Agent

**Workflow:** `evals/workflows/customer_support_agent.yml`
**Results:** `evals/results/customer_support_agent/`

| Step | Expected | Actual | Result |
|---|---|---|---|
| resolve | composite > 4.0 | 4.12 | **PASS** |

Resolve step breakdown: `blast=5, rev=5, freq=5, ver=3, casc=5 → (10+10+5+3+5)/8 = 4.12`

Design requirements to achieve this: regulated environment, 100k req/day base volume, resolve at depth 3, 6 downstream steps, `customer_facing=true`, `data_sensitivity=critical`, `reversible=false`.

### 2B: Internal Q&A Bot

**Workflow:** `evals/workflows/internal_qa_bot.yml`
**Results:** `evals/results/internal_qa_bot/`

| Criterion | Expected | Actual | Result |
|---|---|---|---|
| Max composite across all steps | ≤ 3.0 | 1.88 | **PASS** |

All 4 steps comfortably under 3.0. High-water mark is `retrieve_docs` and `generate_answer` both at 1.88. The non-customer-facing, standard-env, reversible design keeps scores low as expected.

### 2C: Expense Processor

**Workflow:** `evals/workflows/expense_processor.yml`
**Results:** `evals/results/expense_processor/`

| Step | Expected | Actual | Result |
|---|---|---|---|
| payment | composite > 4.5 | 4.12 | **FAIL — scoring ceiling** |

The payment step hit the **maximum achievable composite score of 4.12** (blast=5, rev=5, freq=5, ver=3, casc=5). The target of 4.5 is unreachable under the current formula. See tuning recommendations below.

---

## Tier 3 — Adversarial Workflows

### 3A: Hidden Write

**Workflow:** `evals/workflows/hidden_write.yml`
**Results:** `evals/results/hidden_write/`

| Step | Expected | Actual | Result |
|---|---|---|---|
| enrich_and_update | composite > 3.0 | **1.25** (checkpoint_level=none) | **FAIL — complete miss** |

The `enrich_and_update` step is declared as `type: data_lookup, reversible: true` in the YAML despite its description revealing it mutates 8,000 CRM records. The tool scores it entirely on declared metadata:

- `blast_radius=2.0` (data_lookup, no customer_facing, no error_consequence)
- `reversibility=1.0` (reversible=true, no tools → lowest possible)
- `verifiability=1.0` (data_lookup type → lowest possible)
- **Result: composite=1.25, no checkpoint, no failure flags**

**Root cause:** The tool trusts declared `type` and `reversible` fields unconditionally. Description text is never parsed for semantic signals. A dishonest or misconfigured YAML fully defeats the assessment.

### 3B: Frequency Bomb

**Workflow:** `evals/workflows/frequency_bomb.yml`
**Results:** `evals/results/frequency_bomb/`

| Step | Expected | Actual | Result |
|---|---|---|---|
| batch_processor | frequency ≥ 4.0 (reflecting 10k effective calls/day) | **1.0** | **FAIL — complete miss** |

The workflow declares `requests_per_day: 10` but `batch_processor` iterates 1,000 records per invocation. Effective AI calls = 10,000/day. The tool sees `10 req/day × 0.8^1 = 8 effective/day → freq=1.0` (lowest tier).

**Root cause:** `VolumeProfile` has no `iterations_per_request` or `records_per_batch` field. The frequency scoring function only uses `requests_per_day` scaled by workflow depth. A single batch step processing thousands of records is indistinguishable from a single API call.

Practical impact: a step that actually triggers 10,000+ AI calls/day is underpriced (reported as $0.91/month instead of ~$910/month), under-rate-limited, and under-checkpointed.

### 3C: Cascading Chain

**Workflow:** `evals/workflows/cascading_chain.yml`
**Results:** `evals/results/cascading_chain/`

| Check | Expected | Actual | Result |
|---|---|---|---|
| step_01 cascading_failure HIGH | cascading_failure HIGH (9 desc) | flagged HIGH | **HIT** |
| step_06 context_degradation | context_degradation ≥ MEDIUM | flagged HIGH | **HIT** |
| step_10 checkpoint_level required/recommended | composite ≥ 3.5 | composite=3.25 | **MISS** |
| Compound error rate (0.85^10 ≈ 20%) | Flagged explicitly | Not computed | **MISS** |

The tool correctly identifies early-chain cascading risk and mid-chain context degradation. It does NOT compute compound accuracy degradation across the chain. The final step (`Publish final output`) scores only 3.25 — below the `recommended` threshold of 3.5 — despite being the delivery point of a system with ~20% correct-output rate.

The compound error rate failure is structural: the tool has no multi-step accuracy model. Each step is assessed independently, so the multiplicative degradation of a 10-step 85%-accurate chain is invisible.

---

## Step 10 — Scoring Tuning Recommendations

### Recommendation 1: Fix cascading_failure FP inflation for parallel data collectors

**File:** `engine/failure_mapper.py`, `assess_cascading_failure`
**Problem:** Every step with 4+ downstream nodes gets flagged HIGH regardless of reversibility, blast radius, or documented graceful degradation. In the CEO Agent, 6 parallel data-collection steps all fire HIGH, drowning out legitimate signals (collect_mercury, collect_open_brain).

**Fix:** Gate HIGH cascading on blast_radius AND reversibility jointly. Proposed logic:

```python
# After counting descendants, check per-step blast profile
if n >= 4:
    # Only HIGH if the step itself has high blast (irreversible or high sensitivity)
    if not step.reversible or step.data_sensitivity in (DataSensitivity.high, DataSensitivity.critical):
        risk = RiskLevel.high
    else:
        risk = RiskLevel.medium  # Downgrade if proven graceful degradation is possible
```

Alternatively, add a `has_graceful_fallback: bool` field to `WorkflowStep` and downgrade cascading risk when set.

**Expected improvement:** Reduces CEO Agent false positives from 3→0 for the low-sensitivity collection steps.

---

### Recommendation 2: Add silent_failure assessment for data_lookup steps with high/critical sensitivity

**File:** `engine/failure_mapper.py`, `assess_silent_failure`
**Problem:** `assess_silent_failure` only checks `ai_generation`, `ai_action`, and `ai_classification` (customer-facing). Data lookup steps can fail silently (empty result, stale cache, parameter bug returning zero rows) with no error signal — exactly the Zoho Mail known failure in the CEO Agent.

**Fix:** Add a `data_lookup` branch:

```python
elif step.type == StepType.data_lookup and step.data_sensitivity in (
    DataSensitivity.high, DataSensitivity.critical
):
    risk = RiskLevel.high
    rationale = "High-sensitivity data source may return valid-looking empty or stale data"
    mitigation = "Add non-empty validation gate; alert on unexpectedly low record counts vs. baseline"
```

**Expected improvement:** CEO Agent Tier 1 TP rate 62% → 75% (collect_zoho_mail silent_failure now detected).

---

### Recommendation 3: Flag ai_classification steps with model but no tools as potential tool_selection_error

**File:** `engine/failure_mapper.py`, `assess_tool_selection_error`
**Problem:** `assess_tool_selection_error` returns None when `len(step.tools) == 0`. For `parse_reply` (ai_classification with a model and structured parsing task), tool_selection_error should still be flagged because the model must choose how to structure its output without explicit tool constraints.

**Fix:** Add a low-risk flag for AI steps with a model but no tools, indicating unguided output structuring:

```python
if n == 0 and step.model is not None and step.type in _AI_TYPES:
    risk = RiskLevel.low
    rationale = "AI step has no tool constraints — output format entirely model-guided"
    mitigation = "Define explicit output schema (Pydantic, JSON Schema) and validate against it"
    return FailureMapping(...)
```

**Expected improvement:** CEO Agent parse_reply tool_selection_error now detected at LOW. Tier 1 TP rate 62% → 75%.

---

### Recommendation 4: Fix scoring formula ceiling to allow > 4.5 for financial-impact steps

**File:** `engine/risk_scorer.py`, `compute_composite`
**Problem:** Current formula `(blast×2 + rev×2 + freq + ver + casc) / 8` has a maximum of 4.125 for `ai_action` (ver=3) or `ai_generation` (ver=5 but rev=4). The denominator of 8 was likely chosen for symmetry but creates an artificial ceiling below the 4.5 and 5.0 thresholds commonly used in risk rubrics.

**Current max by step type:**

| Step type | Max blast | Max rev | Max freq | Max ver | Max casc | Max composite |
|---|---|---|---|---|---|---|
| ai_action (irreversible) | 5 | 5 | 5 | 3 | 5 | **(10+10+5+3+5)/8 = 4.12** |
| ai_generation (customer-facing, irreversible) | 5 | 4 | 5 | 5 | 5 | **(10+8+5+5+5)/8 = 4.12** |
| ai_classification (irreversible) | 5 | 3 | 5 | 2 | 5 | **(10+6+5+2+5)/8 = 3.50** |

**Fix — Option A (simplest):** Change denominator from 8 to 7:

```python
def compute_composite(...) -> float:
    raw = (blast * 2 + reversibility * 2 + frequency + verifiability + cascading) / 7
    return round(raw, 2)
```

New max for `ai_action`: (10+10+5+3+5)/7 = **33/7 = 4.71** — above 4.5 ✓
New max for `ai_generation`: (10+8+5+5+5)/7 = **33/7 = 4.71** — above 4.5 ✓
New checkpoint threshold `required` of 4.0 still fires at reasonable levels.

**Note:** This changes all existing score values proportionally. Checkpoint thresholds in `classify_checkpoint_level` will need recalibration (e.g., `> 4.5` → required, `> 4.0` → recommended).

**Fix — Option B (preferred, additive):** Add a `financial_impact` dimension scored from `risk.financial_impact_per_error`:

```python
def score_financial_impact(risk_profile: RiskProfile) -> float:
    v = risk_profile.financial_impact_per_error
    if v >= 10000: return 5.0
    if v >= 1000: return 4.0
    if v >= 100: return 3.0
    if v >= 10: return 2.0
    return 1.0

# New composite with 9 denominator
def compute_composite(blast, rev, freq, ver, casc, financial) -> float:
    raw = (blast*2 + rev*2 + freq + ver + casc + financial) / 9
    return round(raw, 2)
```

Max with financial=5: (10+10+5+5+5+5)/9 = **40/9 = 4.44** — close but still under 4.5.
With financial weighted ×2: (10+10+5+5+5+10)/9 = **45/9 = 5.0** — achievable.

Option B is preferred because it encodes domain knowledge (a payment processor should score higher than a chatbot with the same structural properties).

---

### Recommendation 5: Add iterations_per_request field to catch frequency bombs

**File:** `engine/parser.py` (WorkflowStep), `engine/risk_scorer.py` (score_frequency)
**Problem:** A step processing 1,000 records per invocation at 10 invocations/day makes 10,000 AI calls/day but is reported as 10/day volume.

**Fix:** Add optional `iterations_per_request: int = 1` to `WorkflowStep`:

```python
class WorkflowStep(BaseModel):
    ...
    iterations_per_request: int = 1  # for batch/loop steps
```

In `score_frequency`, multiply before thresholding:

```python
effective_volume = base_volume * (0.8**min_depth) * step.iterations_per_request
```

This also affects cost calculation — `calculate_costs` should multiply `tokens_in/out` by `iterations_per_request`.

---

### Recommendation 6: Add cross-workflow dependency flag for terminal steps

**File:** `engine/parser.py` (WorkflowStep), `engine/failure_mapper.py`
**Problem:** `write_decisions` is a terminal step (0 in-workflow descendants) so `assess_cascading_failure` returns None. But write_decisions feeds future CEO Agent runs via the memory system — a cross-workflow dependency the in-workflow graph cannot see.

**Fix:** Add `cross_workflow_dependency: bool = False` to `WorkflowStep`. When True, assess terminal steps as if they had at least 2 downstream nodes for cascading purposes:

```python
def assess_cascading_failure(step, graph):
    n = len(nx.descendants(graph, step.id))
    if n == 0 and not step.cross_workflow_dependency:
        return None
    effective_n = n if n > 0 else 2  # cross-workflow dependency floor
    ...
```

---

### Recommendation 7: Add description-text consistency check for hidden writes

**File:** `engine/failure_mapper.py` (new assessment)
**Problem:** The hidden_write adversarial test scores enrich_and_update at 1.25 despite its description containing explicit mutation language. The tool has no semantic parsing of description text.

**Fix:** Add a `assess_metadata_inconsistency` function that flags when description keywords contradict declared type or reversibility:

```python
_WRITE_KEYWORDS = {"update", "write", "insert", "mutate", "modify", "patch", "delete", "upsert"}

def assess_metadata_inconsistency(step: WorkflowStep) -> FailureMapping | None:
    desc_lower = step.description.lower()
    has_write_signal = any(kw in desc_lower for kw in _WRITE_KEYWORDS)
    if has_write_signal and step.type == StepType.data_lookup:
        return FailureMapping(
            step_id=step.id,
            step_name=step.name,
            failure_type=FailureType.specification_drift,  # repurpose or add new type
            risk_level=RiskLevel.high,
            rationale="Description contains write/mutation keywords but step type is data_lookup — possible hidden write",
            mitigation="Audit step implementation; reclassify as ai_action if state-mutating",
        )
    ...
```

This is a heuristic but catches the most common misconfiguration pattern.

---

## Appendix: Full Workflow Risk Score Snapshots

### CEO Agent Risk Scores

| Step | Blast | Rev | Freq | Ver | Casc | Composite | Checkpoint |
|---|---|---|---|---|---|---|---|
| collect_open_brain | 2.0 | 1.0 | 1.0 | 1.0 | 4.0 | 1.50 | none |
| collect_github | 2.0 | 1.0 | 1.0 | 1.0 | 4.0 | 1.50 | none |
| collect_mercury | 3.0 | 1.0 | 1.0 | 1.0 | 4.0 | 1.75 | none |
| collect_zoho_mail | 3.0 | 1.0 | 1.0 | 1.0 | 4.0 | 1.75 | none |
| collect_zoho_calendar | 2.0 | 1.0 | 1.0 | 1.0 | 4.0 | 1.50 | none |
| collect_pipeline | 2.0 | 1.0 | 1.0 | 1.0 | 4.0 | 1.50 | none |
| write_daily_brief | 2.0 | 1.0 | 1.0 | 3.0 | 3.0 | 1.62 | none |
| format_brief | 2.0 | 2.0 | 1.0 | 4.0 | 3.0 | 1.88 | none |
| send_email | 3.0 | 5.0 | 1.0 | 3.0 | 3.0 | **2.88** | none |
| parse_reply | 3.0 | 1.0 | 1.0 | 2.0 | 2.0 | 1.50 | none |
| write_decisions | 2.0 | 1.0 | 1.0 | 3.0 | 1.0 | 1.25 | none |

**Observation:** No CEO Agent step triggers a required checkpoint; send_email (2.88) is the only step above 2.5. The 1 req/day volume suppresses frequency scores to 1.0 across the board, dramatically reducing composite scores for a workflow that handles PII, financial data, and irreversible email sends. Frequency scoring should consider peak_multiplier or a floor for critical steps.

### Expense Processor — Payment Step

| Dimension | Score | Rationale |
|---|---|---|
| blast_radius | 5.0 | customer_facing + critical + error_consequence + regulated env |
| reversibility | 5.0 | reversible=false, type=ai_action |
| frequency | 5.0 | 50k/day × 0.8^4 = 20,480 ≥ 10k |
| verifiability | 3.0 | ai_action (cannot be 5 without ai_generation type) |
| cascading_risk | 5.0 | >5 downstream steps |
| **composite** | **4.12** | **(10+10+5+3+5)/8 — at formula ceiling** |

The payment step achieves maximum scores in 4 of 5 dimensions. The ceiling is a formula artifact, not a signal gap.

---

*Generated by `evals/eval_runner.py` — rerun with `uv run python evals/eval_runner.py` to refresh.*
