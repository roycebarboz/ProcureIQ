# PRD: ProcureIQ — Vendor Risk & Procurement Intelligence Copilot

## Problem Statement

Enterprise procurement teams must manually vet vendors before awarding contracts. This process requires cross-referencing external market signals (financial health, news, sanctions), internal procurement policies (spend thresholds, diversity requirements, SLA minimums), and historical contract data. Done manually, it takes hours per vendor, is inconsistently applied across analysts, and produces no auditable trail. Teams lack a system that surfaces risk proactively, applies policy uniformly, and degrades gracefully when data sources are unavailable — rather than silently returning a confident but incomplete assessment.

## Solution

ProcureIQ is a multi-agent procurement intelligence system. A procurement analyst submits a vendor name, spend amount, and category. Three agents execute in sequence: Market Scout retrieves external signals (web search, ERP spend history), Policy Librarian retrieves and applies internal policy documents via semantic search, and Risk Synthesizer produces a structured risk brief with a score, confidence level, and recommendation. Results stream to the analyst in real time as each agent completes. When data sources fail, the system degrades visibly — labeling partial assessments, capping scores, and routing dual-failure cases to human review — rather than producing false confidence.

## User Stories

1. As a procurement analyst, I want to submit a vendor name and receive an automated risk brief, so that I can make informed sourcing decisions without manual research.
2. As a procurement analyst, I want to specify spend amount and vendor category when submitting a vendor, so that policy thresholds relevant to that category are applied correctly.
3. As a procurement analyst, I want to see each agent's progress as it runs, so that I understand what data the system is working from before the final brief appears.
4. As a procurement analyst, I want to see market signals (news, financial health, web search results) surfaced in the risk brief, so that I know what external intelligence informed the assessment.
5. As a procurement analyst, I want to see which specific policy clauses triggered risk flags, so that I can cite policy in my sourcing decision documentation.
6. As a procurement analyst, I want a numeric risk score (1–10) and a confidence level on that score, so that I can compare vendors quantitatively and understand how much data backed the assessment.
7. As a procurement analyst, I want a clear recommendation (Approve / Escalate / Reject / Pending), so that I know what action to take without interpreting a raw score.
8. As a procurement analyst, I want to see a warning when the assessment is based on partial data, so that I am not misled by a confidently-stated score derived from incomplete inputs.
9. As a procurement analyst, I want the system to route dual-failure assessments to human review rather than generating a brief, so that I never receive a risk score based on no data at all.
10. As a procurement analyst, I want to see what data was unavailable during an assessment, so that I can decide whether to wait for the data source to recover before acting.
11. As a procurement analyst, I want assessments to recover gracefully if my browser connection drops mid-stream, so that I can retrieve the completed result without resubmitting.
12. As a procurement manager, I want a dashboard showing node latency, partial assessment rate, recommendation distribution, and cost per assessment, so that I can monitor system health and identify data source degradation patterns.
13. As a procurement manager, I want confidence score distributions over time, so that I can assess whether the system is consistently retrieving sufficient data.
14. As a procurement manager, I want LLM token usage and cost tracked per assessment, so that I can forecast operational costs as usage scales.
15. As a procurement manager, I want to see Tavily and Azure AI Search latency tracked separately, so that I can identify which external dependency is causing slowdowns.
16. As a policy administrator, I want internal procurement policy documents to be indexed and retrieved semantically, so that the system applies the most relevant policy clauses to each vendor category rather than keyword-matching.
17. As a policy administrator, I want the system to fall back to a general procurement risk rubric when no relevant policy chunks are found, so that assessments are never blank even for vendor categories not yet covered by indexed documents.
18. As a risk auditor, I want each assessment to carry a unique request ID, so that I can trace any risk brief back to the exact state snapshot, agent outputs, and errors that produced it.
19. As a risk auditor, I want NodeErrors to record which node failed, the failure reason, and whether a fallback was used, so that I have an auditable record of what data was and was not available at assessment time.
20. As a risk auditor, I want partial_output flagged on any assessment where a fallback was used, so that historical assessments can be filtered by reliability.
21. As a developer, I want the graph to emit SSE events per agent completion, so that frontend state reflects actual pipeline progress rather than a polling approximation.
22. As a developer, I want a GET endpoint that returns final assessment state by request ID, so that frontend reconnect logic can recover a completed assessment without resubmitting.
23. As a developer, I want confidence computed as a pure function of state fields, so that it can be tested exhaustively without LLM invocation.
24. As a developer, I want routing to human_review expressed as a pure conditional function on state, so that failure routing logic can be tested independently of the graph.

## Implementation Decisions

### Agent Framework
LangGraph with a single flat graph. Three nodes execute sequentially: `market_scout` → `policy_librarian` → conditional edge → `risk_synthesizer` or `human_review`. No subgraphs. Full execution trace visible in LangGraph Studio.

### LLM Configuration
GPT-4o via Azure OpenAI for all three agents. Temperature varies by role: Market Scout and Policy Librarian use temperature=0 for deterministic retrieval behavior; Risk Synthesizer uses temperature=0.3 to allow natural-language variation in risk narratives.

### State Schema
Shared LangGraph `State` TypedDict with typed inner classes. Key design: no `dict` or `list[dict]` fields — all structured data uses inner TypedDicts to keep node contracts explicit.

Inner types (from grilling session, encode decisions too precise for prose):

```python
class MarketSignal(TypedDict):
    source: str           # "web_search" | "erp" | "news"
    content: str
    retrieved_at: str
    confidence: float

class PolicyHit(TypedDict):
    chunk_text: str
    score: float
    source_doc: str
    risk_category: str

class NodeError(TypedDict):
    node: str             # "market_scout" | "policy_librarian"
    reason: str
    fallback_used: bool
```

Top-level State includes: `request_id`, `vendor_name`, `spend_amount` (Optional), `category`, `market_data: list[MarketSignal]`, `policy_hits: list[PolicyHit]`, `contract_flags: list[str]`, `risk_brief`, `risk_score`, `confidence: float`, `recommendation: Literal["Approve","Escalate","Reject","Pending"]`, `errors: list[NodeError]`, `partial_output: bool`.

### Resilience Architecture
Timeout values: Market Scout 15s (1 retry), Policy Librarian 10s (1 retry). No exponential backoff — unnecessary complexity at this scale.

Four failure cases handled:
- **Scout timeout**: `market_data=[]`, `NodeError(fallback_used=True)`. Synthesizer runs with prompt injection acknowledging missing market data. `risk_score` capped at 6.
- **Scout partial failure** (e.g. ERP not found): `MarketSignal` written with `confidence=0.0` for failed source. `partial_output=True`. Synthesizer flags spend history as unverified. Does not block Librarian.
- **Librarian zero chunks**: `policy_hits=[]`, `NodeError(fallback_used=True)`. Synthesizer runs with general procurement risk rubric injected in prompt.
- **Both hard fail**: `recommendation="Pending"`, `risk_score=0`, `confidence=0.0`. Synthesizer does not run. Graph routes to `human_review` terminal node.

Routing logic (pure function):
```python
def should_synthesize(state: State) -> str:
    scout_hard = any(e["node"] == "market_scout" and not e["fallback_used"] for e in state["errors"])
    lib_hard = any(e["node"] == "policy_librarian" and not e["fallback_used"] for e in state["errors"])
    return "human_review" if (scout_hard and lib_hard) else "risk_synthesizer"
```

Confidence formula (pure function):
```python
def compute_confidence(state: State) -> float:
    score = 1.0
    if not state["market_data"]: score -= 0.35
    elif not any(s["source"] == "erp" for s in state["market_data"]): score -= 0.15
    if not state["policy_hits"]: score -= 0.35
    if not state["contract_flags"]: score -= 0.10
    return round(max(score, 0.1), 2)
```

### Policy Corpus
Four documents indexed in Azure AI Search:
1. FAR Part 9 — Contractor Qualifications (US public domain)
2. NIST SP 800-161 Rev 1 — Supply Chain Risk Management (US public domain)
3. OMB Circular A-123 — Enterprise Risk Management (US public domain)
4. "ProcureIQ Supplier Risk Policy v2.pdf" — fabricated internal document

Chunking strategy: semantic (split on numbered section headers). Preserves policy clause integrity. Azure AI Search handles variable-length chunks.

Embedding model: `text-embedding-3-small` via Azure OpenAI.

### API Layer
FastAPI backend. Key endpoints:
- `POST /assess` — accepts vendor input, returns SSE stream of agent completion events
- `GET /assess/{request_id}/result` — returns final State for reconnect recovery
- `GET /health`

SSE events emitted per agent: `scout_complete`, `librarian_complete`, `assessment_complete`. Degraded nodes still emit their event with partial data and error metadata. Frontend renders ⚠ warning inline.

### Frontend
Vite + React + TailwindCSS. Three screens:
- **Assess**: input form + live agent progress cards populated via SSE
- **Risk Brief**: risk score, confidence, recommendation badge, narrative, expandable policy hits and market signals
- **Dashboard**: App Insights charts — node latency, partial_output rate, recommendation distribution, recent assessments table

No downloadable PDF. No authentication.

### Observability
Azure Application Insights. Full instrumentation: per-node duration, confidence score distribution, partial_output rate, recommendation breakdown, LLM token usage per node, Tavily latency, Azure AI Search latency, cost-per-assessment.

### Infrastructure
Terraform. Azure resources: Container Apps (backend), Static Web Apps (frontend), Azure OpenAI, Azure AI Search, Application Insights + Log Analytics, Key Vault, Container Registry, Storage Account (Terraform remote state).

Secrets: `.env` + python-dotenv locally. Key Vault + managed identity in production.

### Dependencies
Python: `uv` with `pyproject.toml` + `uv.lock`. Node: standard npm/Vite.

### CI/CD
GitHub Actions, 3 jobs on push to main: `lint-test` (ruff + pytest), `build` (Docker → ACR), `deploy` (terraform apply + containerapp update).

## Testing Decisions

A good test asserts external behavior — what state is written, what event fires, what node is reached — not how the internal implementation produced it. Mock at the boundary (LLM client, Tavily client, Azure AI Search client), not inside business logic.

Six test seams, in priority order:

**Seam 1: `compute_confidence(state)`**
Pure function. Test all five confidence scenarios exhaustively: all data present (1.0), no ERP source (0.85), no market data (0.65), no policy hits (0.65), no market + no policy (0.30). No mocking required. Highest return per minute of test-writing time.

**Seam 2: `should_synthesize(state)`**
Pure function. Test all four routing cases: both hard fail → `"human_review"`, Scout hard fail only → `"risk_synthesizer"`, Librarian hard fail only → `"risk_synthesizer"`, no failures → `"risk_synthesizer"`. This function guards against Synthesizer running on empty state — subtle logic errors here are silent and dangerous.

**Seam 2.5: `infer_severity(content: str)`**
Pure function determining whether a policy chunk becomes a blocking flag. Test keyword coverage: DPA violations, sanctions hits, debarment language must route to blocking. Missing a keyword here silently downgrades a blocking flag to advisory in production. Five tests, zero mocking required.

**Seam 3: Agent nodes (Scout, Librarian, Synthesizer)**
Mock Azure OpenAI client and Tavily client. For each node, assert the correct fields are written to State. Focus on failure paths over happy path: Scout timeout must write correct `NodeError(fallback_used=True)` and empty `market_data`. Librarian returning zero chunks must set `partial_output=True`. Synthesizer receiving `partial_output=True` must cap `risk_score` at 6 and inject degradation language in `risk_brief`.

**Seam 4: Full graph integration**
`graph.invoke(...)` with mocked LLM and tools. Two cases: happy path (assert `recommendation` is set, `confidence == 1.0`, `partial_output == False`), both-nodes-hard-fail (assert terminal node is `human_review` AND assert `State.recommendation == "Pending"` and `State.risk_score == 0`). Reaching the node and writing correct state are two distinct assertions — test both.

**Seam 5: FastAPI SSE endpoint**
Integration test with mocked graph. Assert event sequence: `scout_complete` fires before `librarian_complete`, which fires before `assessment_complete`. This validates LangGraph node ordering matches the intended pipeline — ordering is easy to accidentally break during graph edits, and no other seam catches it. Also assert `request_id` is present in all events and that `GET /assess/{request_id}/result` returns the final state after stream completes.

## Out of Scope

- Authentication and authorization
- Multi-user or role-based access control
- Downloadable PDF reports
- Real ERP system integration (SAP, Coupa) — mocked fixtures only
- Real contract document ingestion from SharePoint or Google Drive
- Streaming token-by-token LLM output (events fire on node completion, not token-by-token)
- Vendor comparison across multiple assessments in a single session
- Assessment history persistence beyond the current session (no database)
- Feedback loop / human correction of assessments
- Mobile-responsive frontend
- Internationalization
- Rate limiting or quota management

## Further Notes

- The system's key differentiator is visible, honest degradation. When data is missing, the UI must show what is missing — not hide it behind a spinner or suppress the score. This should be reinforced at every frontend PR review.
- `request_id` must be generated at the API boundary (FastAPI), not inside the graph. It must be present in every SSE event and every App Insights trace to enable end-to-end correlation.
- The fabricated policy document ("ProcureIQ Supplier Risk Policy v2.pdf") should be written before the ingest script is run. Its content determines the density of policy hits in demos — it should include spend thresholds, DPA/data handling requirements, diversity targets, and SLA minimums to ensure Librarian returns non-trivial results across vendor categories.
- Terraform remote state requires the Azure Storage Account to be provisioned manually before `terraform init`. Document this as a one-time bootstrap step in the repo README.
- For the Deloitte FDE showcase context: the Dashboard screen and observability instrumentation are what differentiate this from a standard RAG demo. Prioritize getting App Insights wired up early so the dashboard has real data by demo time.
