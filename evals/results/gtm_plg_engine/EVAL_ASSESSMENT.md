# GTM PLG Engine — Eval Assessment

**Date:** 2026-03-30
**Branch:** `claude/beautiful-almeida`
**Engine version:** Round 2 (4 GTM-specific fixes applied on top of PR #1)

---

## Overview

The GTM PLG Engine audit was introduced in `claude/angry-brattain` as a regression evaluation against the post-PR-#1 engine. That pass identified 4 scoring gaps specific to this workflow. This document records the Round 2 fixes and confirms each gap is closed.

---

## Round 1 Baseline (post-PR #1, pre-Round-2)

Scored with the PR #1 engine (7 fixes applied). Key gaps identified:

| Gap | Step | Description |
|---|---|---|
| G1 | `generate_pricing` | Composite 3.9 — below required threshold despite high financial risk |
| G2 | `write_crm` | No checkpoint despite cross-workflow golden record risk |
| G3 | `identify_accounts` | Frequency 4.0 false positive — batch heuristic fired despite single-item processing |
| G4 | multiple | Cost calculator ignored `iterations_per_request` multiplier |

---

## Round 2 Fixes Applied

### Fix R2-1: Financial impact blast bonus

**Problem:** `generate_pricing` handles live Salesforce pricing data with `data_sensitivity: high` in a workflow where `financial_impact_per_error: 5000`. Despite significant financial exposure, the blast radius scored 4.0 — one point short of the required-checkpoint threshold.

**Fix:** `score_blast_radius` adds +1 when `risk_profile.financial_impact_per_error >= 5000` AND `step.data_sensitivity in (high, critical)`.

**Result:** `generate_pricing` blast_radius: 4.0 → **5.0**; composite: 3.9 → **4.14** (required checkpoint triggered).

---

### Fix R2-2: Cross-workflow golden record checkpoint

**Problem:** `write_crm` writes the final enriched account record back to Salesforce. This record is consumed by downstream reporting, forecasting, and account-scoring pipelines. Despite `cross_workflow_dependency: true`, `reversible: false`, and `data_sensitivity: critical`, no checkpoint was recommended.

**Fix:** New Rule R2-2 in `recommend_checkpoints`: non-terminal steps with `cross_workflow_dependency=True + reversible=False + data_sensitivity in (high, critical)` receive a **required post-action verification** checkpoint.

Also fixed: `cross_workflow_dependency` field in `evals/workflows/gtm_plg_engine.yml` was set to a descriptive string — corrected to `true` (bool) to match the `WorkflowStep` schema.

**Result:** `write_crm` now produces two required checkpoints: pre-flight review (from Rule 1: blast_radius ≥ 4 + irreversible) and **post-action verification** (from Rule R2-2: cross-workflow golden record).

---

### Fix R2-3: Suppress batch heuristic when iterations_per_request explicitly set

**Problem:** `identify_accounts` processes one account at a time (`iterations_per_request: 1` explicitly in YAML) but its description contains language like "each account" and "batch". The old heuristic ignored the explicit field value and inferred a batch multiplier, inflating frequency to 4.0.

**Fix:** `_heuristic_iterations` now checks `"iterations_per_request" in step.model_fields_set`. If the field was explicitly declared in the YAML, its value is trusted and the batch-keyword heuristic is skipped.

**Result:** `identify_accounts` frequency: 4.0 → **1.0** (false positive eliminated).

---

### Fix R2-4: Cost calculator respects iterations_per_request

**Problem:** `calculate_step_cost` ignored `step.iterations_per_request`, so batch steps like `generate_deck` (20 iterations/request) and `write_crm` (20 iterations/request) reported per-request token cost as if they processed one item.

**Fix:** Token estimates multiplied by `max(step.iterations_per_request, 1)` before cost computation.

**Result:** Monthly cost: ~$370 (pre-fix) → **$1,488.86** (accurate reflection of batch step costs).

---

## Post-Round-2 Audit Results

### Risk Scores

| Step | Blast | Rev | Freq | Ver | Casc | Composite | Checkpoint |
|---|---|---|---|---|---|---|---|
| identify_accounts | 2.0 | 3.0 | 1.0 | 2.0 | 3.0 | 1.86 | none |
| enrich_firmographic | 2.0 | 1.0 | 2.0 | 1.0 | 5.0 | 2.57 | none |
| enrich_usage | 4.0 | 1.0 | 1.0 | 1.0 | 4.0 | 2.43 | none |
| score_propensity | 2.0 | 3.0 | 2.0 | 2.0 | 3.0 | 2.14 | none |
| generate_deck | 3.0 | 4.0 | 2.0 | 5.0 | 3.0 | 2.71 | none |
| **generate_pricing** | **5.0** | 4.0 | 2.0 | 5.0 | 4.0 | **4.14** | **required** |
| capacity_check | 2.0 | 1.0 | 1.0 | 2.0 | 2.0 | 1.71 | none |
| route_to_rep | 4.0 | 3.0 | 1.0 | 2.0 | 2.0 | 2.71 | none |
| write_crm | 4.0 | 5.0 | 1.0 | 1.0 | 3.0 | 3.43 | none |
| notify_rep | 3.0 | 4.0 | 1.0 | 5.0 | 2.0 | 3.14 | none |
| log_pipeline_event | 3.0 | 3.0 | 1.0 | 3.0 | 1.0 | 3.0 | none |

### Checkpoints

| Priority | Step | Type |
|---|---|---|
| required | generate_pricing | pre-flight review |
| required | write_crm | pre-flight review |
| required | write_crm | post-action verification *(new — Fix R2-2)* |
| recommended | generate_deck | sampling audit |
| recommended | generate_pricing | sampling audit |
| recommended | notify_rep | sampling audit |
| recommended | notify_rep | post-action verification |

### Cost Summary (Post Fix R2-4)

| Metric | Value |
|---|---|
| Monthly token cost | $1,488.86 |
| Annual token cost | $17,881.13 |
| Cost per request | $49.63 |

---

## Eval Regression Results

All 5 GTM PLG eval checks pass:

| Check | Result |
|---|---|
| generate_pricing blast_radius ≥ 5.0 (Fix R2-1) | **PASS** — 5.0 |
| generate_pricing composite > 4.0 (Fix R2-1) | **PASS** — 4.14 |
| write_crm required checkpoint (Fix R2-2) | **PASS** — pre-flight review (required) |
| enrich_usage silent_failure HIGH | **PASS** — flagged HIGH |
| log_pipeline_event metadata_inconsistency HIGH | **PASS** — flagged HIGH |

Score threshold checks:

| Check | Result |
|---|---|
| generate_pricing composite > 4.0 | **PASS** — 4.14 |
| identify_accounts frequency ≤ 2.0 (Fix R2-3) | **PASS** — 1.0 |

---

## Remaining Known Gaps

None identified. All 4 gaps from the Round 1 baseline assessment are closed.

Future improvement candidates (not blocking):
- `generate_deck` composite (2.71) is below the recommended-checkpoint threshold despite being customer-facing with sycophantic confirmation and context degradation risks — investigate whether brand risk field should feed into blast radius
- `write_crm` composite (3.43) is below recommended despite being the golden record write — the cross-workflow checkpoint rule (R2-2) compensates operationally, but the composite score itself doesn't reflect the full downstream risk

*Generated: 2026-03-30 — rerun audit with `uv run python run_audit.py evals/workflows/gtm_plg_engine.yml -o evals/results/gtm_plg_engine --no-evidence`*
