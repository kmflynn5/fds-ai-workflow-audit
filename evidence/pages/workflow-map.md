---
title: Workflow Map
---

# Workflow Map

## Workflow Steps

```sql workflow_steps
SELECT
    step_id,
    name,
    type,
    model,
    depends_on,
    customer_facing,
    reversible,
    data_sensitivity
FROM audit_results.workflow_steps
ORDER BY step_id
```

<DataTable data={workflow_steps} />

---

## Risk Scores by Step

```sql risk_scores
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

<DataTable data={risk_scores} />

---

## Navigation

- [Executive Summary](/)
- [Workflow Map](/workflow-map)
- [Failure Modes](/failures)
- [Checkpoints](/human-checkpoints)
- [Cost Analysis](/cost-analysis)
- [Recommendations](/recommendations)
