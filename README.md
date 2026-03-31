# fds-ai-workflow-audit

Config-driven AI workflow risk and quality assessment tool. Input a workflow description, get back an assessment a CTO can act on.

## What It Does

Takes a YAML description of an AI-powered workflow and produces:

1. **Risk scores** — 5-dimension scoring (blast radius, reversibility, frequency, verifiability, cascading risk) for every step
2. **Failure mode mapping** — Each step analyzed against 6 failure types (context degradation, specification drift, sycophantic confirmation, tool selection error, cascading failure, silent failure)
3. **Human checkpoint recommendations** — Where humans should stay in the loop, with staffing estimates
4. **Cost analysis** — Token economics per step, infrastructure costs, 12-month growth projections
5. **Evidence BI report** — Interactive dashboard with charts, tables, and prioritized recommendations

## Quick Start

```bash
# Install dependencies
uv sync

# Run the audit on an example workflow
uv run python run_audit.py examples/workflow.example.yml

# View the Evidence report (CSVs are auto-synced to evidence/sources/)
cd evidence && npm install && npm run sources && npm run dev
```

## Workflows

`examples/` contains workflow configs to audit.

- `examples/workflow.example.yml` — Tier 1 customer support agent (reference workflow)
- `examples/customer_support_agent.yml` — Support with sentiment-based escalation
- `examples/content_generation_pipeline.yml` — Marketing content with brand voice checks
- `examples/data_enrichment_system.yml` — CRM enrichment with validation gates
- `examples/sales_outreach_agent.yml` — Personalized outreach with compliance checks
- `examples/internal_knowledge_qa.yml` — RAG-based Q&A with feedback capture

## Architecture

```
workflow.yml → Assessment Engine (Python) → JSON + CSVs → Evidence BI Report
```

**Engine modules:**
- `engine/parser.py` — YAML config → Pydantic models → networkx step graph
- `engine/risk_scorer.py` — 5-dimension risk scoring with composite formula
- `engine/failure_mapper.py` — 6 failure type susceptibility analysis
- `engine/checkpoint_recommender.py` — Human-in-the-loop placement logic
- `engine/cost_calculator.py` — Token + infrastructure cost model
- `engine/claude_enricher.py` — Optional Claude API enhancement

## Documentation

- [Methodology](docs/METHODOLOGY.md) — How the assessment works
- [Failure Taxonomy](docs/FAILURE_TAXONOMY.md) — The 6 failure types explained
- [Risk Dimensions](docs/RISK_DIMENSIONS.md) — How risk scoring works
- [Implementation Spec](docs/init-spec.md) — Original design specification

## Dependencies

```
pyyaml>=6.0          # YAML parsing
pydantic>=2.0        # Config validation
networkx>=3.0        # Step graph / dependency analysis
anthropic>=0.40.0    # Optional: Claude enrichment
```

## License

Apache 2.0
