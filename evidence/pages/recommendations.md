---
title: Recommendations
---

# Recommendations

## High-Risk Failure Modes

```sql high_risk_failures
SELECT
    step_id,
    step_name,
    failure_type,
    risk_level,
    rationale,
    mitigation
FROM audit_results.failure_matrix
WHERE risk_level = 'high'
ORDER BY step_name
```

<DataTable data={high_risk_failures} />

---

## Recommended Checkpoints

```sql checkpoints_ordered
SELECT
    step_id,
    step_name,
    checkpoint_type,
    priority,
    rationale,
    implementation_detail,
    estimated_daily_reviews
FROM audit_results.checkpoints
ORDER BY
    CASE priority
        WHEN 'required' THEN 1
        WHEN 'recommended' THEN 2
        WHEN 'suggested' THEN 3
        ELSE 4
    END,
    step_name
```

<DataTable data={checkpoints_ordered} />

---

## Risk Scores — Prioritized

```sql risk_scores_desc
SELECT
    step_id,
    step_name,
    blast_radius,
    reversibility,
    frequency,
    verifiability,
    cascading_risk,
    composite,
    checkpoint_level
FROM audit_results.risk_scores
ORDER BY composite DESC
```

<DataTable data={risk_scores_desc} />

---

## Navigation

- [Executive Summary](/)
- [Workflow Map](/workflow-map)
- [Failure Modes](/failures)
- [Checkpoints](/human-checkpoints)
- [Cost Analysis](/cost-analysis)
- [Recommendations](/recommendations)
