---
title: Human-in-the-Loop Checkpoints
---

# Human-in-the-Loop Checkpoints

## Checkpoint Summary

```sql checkpoint_summary
SELECT
    COUNT(*) AS total_checkpoints,
    SUM(CASE WHEN priority = 'required' THEN 1 ELSE 0 END) AS required_count,
    SUM(CASE WHEN priority = 'recommended' THEN 1 ELSE 0 END) AS recommended_count,
    SUM(CASE WHEN priority = 'suggested' THEN 1 ELSE 0 END) AS suggested_count
FROM audit_results.checkpoints
```

<BigValue data={checkpoint_summary} value="total_checkpoints" title="Total Checkpoints" fmt="num0" />
<BigValue data={checkpoint_summary} value="required_count" title="Required" fmt="num0" />
<BigValue data={checkpoint_summary} value="recommended_count" title="Recommended" fmt="num0" />
<BigValue data={checkpoint_summary} value="suggested_count" title="Suggested" fmt="num0" />

---

## All Checkpoints

```sql all_checkpoints
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

<DataTable data={all_checkpoints} />

---

## Navigation

- [Executive Summary](/)
- [Workflow Map](/workflow-map)
- [Failure Modes](/failures)
- [Checkpoints](/human-checkpoints)
- [Cost Analysis](/cost-analysis)
- [Recommendations](/recommendations)
