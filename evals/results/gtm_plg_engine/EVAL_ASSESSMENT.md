# GTM PLG Engine — Eval Assessment (Post-PR #2 GTM Fixes)

**Date:** 2026-03-30
**Engine version:** post-PR #2 (`claude/distracted-faraday` — 4 GTM PLG-specific fixes applied)
**Workflow:** `workflows/gtm_plg_engine.yml`
**Prior assessment:** `angry-brattain` worktree (post-PR #1, first GTM PLG run)

---

## Executive Summary

The 4 GTM PLG-specific fixes close all four gaps identified in the prior assessment. The engine now
correctly classifies `generate_pricing` as required-checkpoint via composite score (not just the
rule-based override), adds a required checkpoint to `write_crm` via the cross-workflow dependency
rule, eliminates the `identify_accounts` frequency false positive, and reports accurate Claude API
costs that reflect `iterations_per_request` multipliers.

**Verdict:** All four prior GTM PLG gaps resolved. No regressions on the original 7-workflow eval
suite (100% pass rate maintained). The engine is now calibrated for this workflow class without
known blindspots.

---

## 1. Gap Resolution Status

### Gap 1 (RESOLVED): `generate_pricing` composite below "required" threshold

**Before:** composite = 3.86, checkpoint_level = "recommended" (rule override to required)
**After:** composite = **4.14**, checkpoint_level = **"required"** (by composite score)

Fix: `score_blast_radius` now adds +1.0 when `financial_impact_per_error >= 5000` AND
`data_sensitivity in (high, critical)`. For `generate_pricing`: blast 4.0 → 5.0.

Composite: `(5×2 + 4×2 + 2 + 5 + 4) / 7 = 29/7 = 4.14` → required ✓

The step now correctly reaches "required" from the composite itself, not from a rule override. The
pre-flight review checkpoint is mandatory whether or not the checkpoint_recommender rule fires.

### Gap 2 (RESOLVED): `write_crm` gets no checkpoint despite being the golden record

**Before:** composite = 3.14, 0 checkpoints (none from score, none from rule)
**After:** composite = **3.43**, **2 required checkpoints** (pre-flight review + post-action
verification)

Two fixes combined:
1. Financial impact bonus: blast 3.0 → 4.0 (data_sensitivity=critical, financial_impact=5000).
   Blast ≥ 4 AND reversible=false → Rule 1 fires → **required pre-flight review**.
2. New cross-workflow checkpoint rule: `cross_workflow_dependency=true AND reversible=false AND
   data_sensitivity in (high, critical)` → **required post-action verification** regardless of
   descendant count.

`write_crm` now has the strongest checkpoint coverage in the workflow — matching its risk profile
as the golden record update that feeds downstream reporting pipelines.

### Gap 3 (RESOLVED): `identify_accounts` frequency heuristic false positive

**Before:** freq = 3.0 (heuristic extracted "200" from "Returns batch of 50-200 accounts per
daily run", treating output batch size as call count)
**After:** freq = **1.0**

Fix: `_heuristic_iterations` now checks `model_fields_set` (Pydantic v2). When
`iterations_per_request` is explicitly declared in the YAML (even as 1), the description-based
heuristic is suppressed. The `identify_accounts` step has `iterations_per_request: 1` set
explicitly → heuristic skipped → freq reflects actual call count (1/day).

Steps that genuinely iterate (e.g. `enrich_firmographic` with `iterations_per_request: 100`) are
unaffected — they use the explicit value directly.

Frequency bomb eval not broken: `batch_processor` in `frequency_bomb.yml` has no explicit
`iterations_per_request` field → heuristic still fires → freq = 4.0 ✓

### Gap 4 (RESOLVED): Cost calculator ignores `iterations_per_request`

**Before:** Total Claude API monthly = $2.63 (1× single-request costs)
**After:** Total Claude API monthly = **$88.86** (~34× increase, matching expected true cost)

Fix: `calculate_step_cost` now multiplies `estimated_tokens_in` and `estimated_tokens_out` by
`step.iterations_per_request` before computing cost.

| Step | Monthly Before | Monthly After | Multiplier |
|---|---|---|---|
| enrich_firmographic | $0.048 | $4.80 | 100× |
| score_propensity | $0.405 | $40.50 | 100× |
| generate_deck | $1.17 | $23.40 | 20× |
| generate_pricing | $0.90 | $18.00 | 20× |
| route_to_rep | $0.048 | $0.96 | 20× |
| notify_rep | $0.06 | $1.20 | 20× |
| **Total Claude API** | **$2.63** | **$88.86** | ~34× |

Grand total monthly: $1,488.86 (Claude $88.86 + Snowflake $900 + Clearbit $500). Cost optimization
savings estimate updated accordingly: downgrading `score_propensity` to `claude-haiku-4-5` saves
~$29.70/month (vs $0.30 shown before).

---

## 2. Full Risk Score Table (Post-PR #2)

| Step | Blast | Rev | Freq | Ver | Casc | Composite | Checkpoint Level |
|---|---|---|---|---|---|---|---|
| identify_accounts | 2.0 | 1.0 | **1.0** | 1.0 | 5.0 | **1.86** | none |
| enrich_firmographic | 2.0 | 2.0 | 2.0 | 3.0 | 5.0 | 2.57 | none |
| enrich_usage | **4.0** | 1.0 | 1.0 | 1.0 | 5.0 | 2.43 | none |
| score_propensity | 2.0 | 1.0 | 2.0 | 2.0 | 5.0 | 2.14 | none |
| generate_deck | 3.0 | 1.0 | 2.0 | 5.0 | 4.0 | 2.71 | none |
| generate_pricing | **5.0** | 4.0 | 2.0 | 5.0 | 4.0 | **4.14** | **required** |
| capacity_check | 2.0 | 1.0 | 1.0 | 1.0 | 4.0 | 1.71 | none |
| route_to_rep | **4.0** | 2.0 | 1.0 | 3.0 | 3.0 | 2.71 | none |
| write_crm | **4.0** | 5.0 | 1.0 | 3.0 | 2.0 | **3.43** | none* |
| notify_rep | 3.0 | 4.0 | 1.0 | 5.0 | 2.0 | 3.14 | none |
| log_pipeline_event | 3.0 | 5.0 | 1.0 | 3.0 | 1.0 | 3.00 | none |

*`write_crm` composite=3.43 stays below the "recommended" composite threshold, but receives
**2 required checkpoints** from the checkpoint_recommender rules (pre-flight + post-action).

Blast score increases from prior assessment (financial impact bonus now applies):
- `enrich_usage`: 3.0 → 4.0 (data_sensitivity=high, financial_impact=5000)
- `generate_pricing`: 4.0 → 5.0 (data_sensitivity=critical, financial_impact=5000)
- `route_to_rep`: 3.0 → 4.0 (data_sensitivity=high, financial_impact=5000)
- `write_crm`: 3.0 → 4.0 (data_sensitivity=critical, financial_impact=5000)

---

## 3. Checkpoint Summary (Post-PR #2)

| Step | Type | Priority | Trigger |
|---|---|---|---|
| generate_pricing | pre-flight review | **REQUIRED** | blast≥4 + irreversible (Rule 1) |
| write_crm | pre-flight review | **REQUIRED** | blast≥4 + irreversible (Rule 1) |
| write_crm | post-action verification | **REQUIRED** | cross_workflow_dependency + irreversible + critical (new Rule 6) |
| generate_deck | sampling audit | recommended | customer_facing + verifiability≥4 (Rule 2) |
| generate_pricing | sampling audit | recommended | customer_facing + verifiability≥4 (Rule 2) |
| notify_rep | sampling audit | recommended | customer_facing + verifiability≥4 (Rule 2) |
| notify_rep | post-action verification | recommended | customer_facing + irreversible + blast<4 (Rule 4) |

3 required, 4 recommended. Prior state had 1 required, 4 recommended.

---

## 4. Eval Suite Regression Check

All 7 original eval workflows continue to pass at 100%:

| Metric | Target | Actual |
|---|---|---|
| True positive rate (Tier 1) | 100% | 8/8 (100%) |
| True positive rate (Tier 2) | 90%+ | 3/3 (100%) |
| True positive rate (Tier 3) | 90%+ | 5/5 (100%) |
| False positive rate | >90% | 3/3 (100%) |
| Score threshold accuracy | 80%+ | 4/4 (100%) |

Key regression risks that were checked:
- **Frequency bomb**: `batch_processor` still scores freq=4.0 — heuristic fires correctly because
  `iterations_per_request` is NOT explicitly set in `frequency_bomb.yml` → `model_fields_set` does
  not contain the key → heuristic path taken → extracts 1000 from description → freq=4.0 ✓
- **Internal Q&A Bot**: All steps still score ≤ 3.0 — financial impact bonus does not apply
  (`financial_impact_per_error=5.0`, well below 5000 threshold) ✓
- **Expense Processor**: `payment` composite still 4.71 ✓

---

## 5. Remaining Notes

No blocking gaps remain. Minor observations for future consideration:

- `write_crm` composite (3.43) still sits below the "recommended" threshold from score alone.
  The required checkpoints come from rules, not composite. This is by design — the cross-workflow
  impact is structural, not derivable from in-workflow graph topology.
- `route_to_rep` blast increased to 4.0 (reversible=true, so Rule 1 doesn't fire). The step
  writes to Salesforce ("Write assignment to Salesforce") — the hidden-write detector correctly
  raises `metadata_inconsistency`. No additional checkpoint is triggered, which is appropriate
  given `reversible=true` is plausible for an assignment that can be re-routed.
- `enrich_usage` blast=4.0 (reversible=true) — same pattern. No checkpoint triggered.

*Generated 2026-03-30. Rerun with:*
```
uv run python run_audit.py workflows/gtm_plg_engine.yml --output evals/results/gtm_plg_engine
```
