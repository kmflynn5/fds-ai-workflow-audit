# Failure Taxonomy

The 6 failure types used in this assessment are drawn from Nate B. Jones' framework for LLM system failures. Each type represents a distinct failure mechanism with its own detection strategy and mitigations.

---

## 1. Context Degradation

**Definition:** Output quality degrades as the context window fills. Earlier instructions, examples, or facts get effectively overwritten by recency bias or simply fall outside the model's reliable attention range.

**Real-world example:** A customer support agent handles a complex multi-turn conversation. By turn 15, it stops referencing the customer's original complaint and starts giving generic responses, having effectively "forgotten" the initial context.

**Susceptible step types:** Multi-turn conversation handlers, long-running session steps, summarization steps that accumulate input.

**Detection:** Monitor output quality metrics over session length. Compare early-session vs. late-session outputs on the same factual questions. Alert when output length or specificity drops.

**Mitigation:** Context summarization at regular intervals. Rolling window strategies that compress older context. Periodic re-injection of key facts (customer ID, original complaint, constraints).

---

## 2. Specification Drift

**Definition:** An agent gradually diverges from its original instructions or constraints over the course of a long-running task. The agent may start following its instilled behaviors faithfully, then progressively deprioritize constraints as the conversation evolves.

**Real-world example:** A document drafting agent is told to write in formal British English and avoid first-person voice. By section 4 of a long document, it is writing casual American English in first person, having drifted from the original spec through accumulated context.

**Susceptible step types:** Long-horizon generation tasks, agents with persistent state, workflows where a single LLM call spans many logical sub-tasks.

**Detection:** Periodic spec re-injection followed by output comparison. Checklist-based evaluations at defined intervals that verify constraints are still being honored.

**Mitigation:** Spec checkpoints — re-inject the full system prompt at regular intervals. Break long tasks into bounded chunks with explicit spec restatement at each boundary. Use structured output schemas to enforce invariants mechanically.

---

## 3. Sycophantic Confirmation

**Definition:** The agent confirms incorrect information provided by a user or upstream step, then builds further output on that incorrect foundation. The model agrees with false premises rather than challenging them.

**Real-world example:** A data enrichment agent receives a CRM record with an incorrect company revenue figure. A user asks "Can you confirm Acme Corp has $50M ARR?" The agent confirms it (it was told to be helpful and agreeable), then generates a prospect brief with that figure embedded throughout.

**Susceptible step types:** Data lookup + generation chains, any step that combines user-supplied or upstream-supplied data with LLM synthesis, Q&A steps where the question contains embedded assumptions.

**Detection:** Cross-reference LLM-confirmed facts against authoritative source data. Build validation steps that independently query source systems rather than relying on the model's recall of what was stated.

**Mitigation:** Validation gates between data ingestion and generation. Explicit system prompt instructions to flag rather than confirm uncertain data. Retrieval-augmented steps that ground generation in retrieved documents rather than conversational assertions.

---

## 4. Tool Selection Error

**Definition:** The agent selects the wrong tool for a task, uses the correct tool with incorrect parameters, or misinterprets a tool's output. In multi-tool environments, the agent may chain tools in an incorrect order.

**Real-world example:** A sales agent has access to both a CRM lookup tool and a web search tool. When asked to find a contact's current role, it uses web search (returning outdated LinkedIn data) instead of the CRM tool (returning the authoritative internal record), then bases its outreach on the stale data.

**Susceptible step types:** Steps with 3 or more available tools, steps where tool selection requires nuanced judgment about data freshness or authority, agentic loops with tool calling.

**Detection:** Tool call logging with expected-tool assertions in tests. Automated checks that verify which tool was called for a given input type. Anomaly detection on tool call frequency distributions.

**Mitigation:** Restrict available tools per intent — only expose the tools actually needed for a given step. Use tool descriptions that explicitly state when not to use them. Add a tool selection verification sub-step for high-stakes actions.

---

## 5. Cascading Failure

**Definition:** An error in one step propagates downstream, causing failures in dependent steps. Because each subsequent step treats the prior step's output as ground truth, a single upstream error can corrupt an entire workflow execution.

**Real-world example:** A workflow retrieves customer data (step 1), enriches it (step 2), generates a personalized email (step 3), and sends it (step 4). Step 1 retrieves the wrong customer record. Steps 2, 3, and 4 all succeed — but the email goes to the wrong person with the wrong content.

**Susceptible step types:** Any step with one or more downstream dependents. Early-pipeline steps that establish context, identity, or data records are highest risk because all subsequent steps inherit their errors.

**Detection:** Per-step validation gates with schema and business-logic checks before passing output downstream. Correlation IDs that allow tracing a failure back to its origin step.

**Mitigation:** Circuit breaker patterns — stop the workflow when a step's output fails validation rather than passing the error forward. Validation gates at high-value handoff points (especially before any action steps). Dead letter queues for failed executions with human review.

---

## 6. Silent Failure

**Definition:** The step produces output that looks correct syntactically, semantically, and stylistically — but is functionally wrong. The output passes all automated checks but fails the actual use case.

**Real-world example:** A content generation step produces a marketing email that reads fluently, passes tone checks, and contains no factual errors the automated system can detect. But it accidentally references a promotion that ended last month, because the model drew on training data rather than the provided campaign brief. Customers click and find an invalid offer.

**Susceptible step types:** Customer-facing generation steps, action steps (sending emails, posting content, updating records), any step where correctness requires domain knowledge the automated eval system lacks.

**Detection:** Functional correctness evaluations — not just "does this read well" but "does this accomplish the intended goal." Sampling audits where human reviewers check a random percentage of outputs. Red-teaming tests with deliberately wrong inputs to verify the step catches them.

**Mitigation:** Sampling audit pipelines (review N% of all outputs). Functional eval suites specific to each step's job (e.g., "does the email contain a valid, current offer code"). Human-in-the-loop checkpoints before customer-facing publication. A/B testing with monitoring on downstream success metrics.

---

## Summary Table

| Failure Type | Primary Trigger | Key Detection Signal | Primary Mitigation |
|---|---|---|---|
| Context Degradation | Long context windows | Quality drop over session length | Context summarization |
| Specification Drift | Long-running agents | Constraint violation at late turns | Periodic spec re-injection |
| Sycophantic Confirmation | Incorrect upstream data | Cross-ref against source systems | Validation gates |
| Tool Selection Error | Multi-tool environments | Tool call logs vs. expected | Restrict tools per intent |
| Cascading Failure | Downstream dependencies | Per-step output validation | Circuit breakers |
| Silent Failure | Customer-facing generation | Functional correctness evals | Sampling audits |
