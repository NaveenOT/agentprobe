# AgentProbe Four-Person Review Script

This script is designed for a 12-16 minute technical review followed by questions. Replace the person placeholders with team member names and rehearse the handoffs so the project sounds like one integrated system rather than four unrelated modules.

## Speaking Order

| Speaker | Area | Suggested time |
|---|---|---:|
| Person 1 | Problem, architecture, and multi-agent pipeline | 4 minutes |
| Person 2 | Target adapters, browser automation, and demo target | 3-4 minutes |
| Person 3 | FastAPI, MongoDB, dataset, models, and persistence | 3-4 minutes |
| Person 4 | Dashboard, telemetry, report, demo, and conclusion | 3-4 minutes |

## Person 1: Problem and Multi-Agent Pipeline

### Files to Know

```text
apps/api/agentprobe/pipeline.py
apps/api/agentprobe/agents.py
apps/api/agentprobe/objectives.py
apps/api/agentprobe/evaluator.py
apps/api/agentprobe/reporting.py
```

### Script

> Good morning. Our project is AgentProbe, an authorized prompt-injection testing framework for chatbots. A prompt injection attempts to make a chatbot ignore its intended instruction hierarchy, disclose protected context, or perform an unintended task. Testing this manually is repetitive and subjective, so AgentProbe automates the process while retaining evidence for every result.

> The user begins in a Next.js dashboard and specifies a target, attack categories, an attempt budget, and a measurable test outcome. The FastAPI backend validates the request and starts a background scan. A LangGraph workflow then profiles the target, selects attack templates, adapts each template, sends it to the target, evaluates the response, and builds a report.

> Our workflow has four graph nodes: profile, prepare, attack, and report. The profile node first sends a benign question through the target adapter. The answer is passed to the Profiler Agent, which uses Groq to identify the chatbot's domain, purpose, intended audience, capabilities, interaction style, observed constraints, and context summary. AgentProbe persists both the target probe exchange and the Profiler Agent input and output. If the model call fails, the pipeline records and uses a generic profile so the scan can continue.

> The prepare node requests a balanced queue of templates from the template repository. The attack node processes one queue entry at a time. The Attacker Agent receives the original technique, target profile, and effective objective. It adapts the technique to the current target and removes stale benchmark outcomes such as `I have been PWNED`. We validate the generated attack before execution and use a deterministic, category-specific fallback if generation fails.

> AgentProbe also normalizes objectives before the graph starts. An empty outcome becomes a synthetic protected-marker test. Credential requests become synthetic canary tests. Dangerous hard-drug objectives become refusal-policy controls rather than procedural jailbreaks. The effective objective and mode are visible in the dashboard, so this behavior is auditable.

> After the target responds, the Hybrid Evaluator uses three layers. A known synthetic marker gives deterministic ground truth. Otherwise, a Groq judge compares the response with the exact objective and returns success, severity, confidence, rationale, and evidence. If that model call fails, conservative heuristics provide a fallback result.

> The report stage calculates attack success rate, average severity, category vulnerability, execution duration, recommendations, and token usage. The report generator is deterministic rather than another LLM, which makes its calculations reproducible.

### Handoff

> The graph deliberately does not know whether the target is an HTTP API or a webpage. Person 2 will explain the adapter layer that provides this abstraction.

### Likely Questions

**Why use LangGraph instead of one large function?**

> The scan has explicit stages, conditional repetition, and shared state. LangGraph makes those transitions visible and lets us add retries or new nodes without coupling them to the API route.

**Why use both deterministic checks and an LLM judge?**

> Deterministic markers are reliable for known test fixtures, while the LLM judge can understand arbitrary natural-language objectives. The heuristic fallback preserves availability when Groq is unavailable.

**Is the system truly adaptive?**

> Attack wording is adapted using the target profile and objective. Template retrieval itself is currently balanced random sampling, not semantic retrieval. Mutation code exists, but its attempt-budget allocation needs improvement before we claim full iterative adaptation.

## Person 2: Target Integration and Browser Automation

### Files to Know

```text
apps/api/agentprobe/adapters/targets.py
apps/api/agentprobe/browser_sessions.py
apps/api/agentprobe/demo.py
tests/test_target_adapters.py
```

### Script

> AgentProbe reaches targets through a common `TargetAdapter` interface. Its single operation accepts a prompt and returns response text, duration, provider token usage, and optional browser-automation token usage. The pipeline therefore works with API and browser targets without separate orchestration logic.

> The API adapter sends an OpenAI-style body containing the model and user message. It supports both our simple `{response: ...}` output and the common `choices[0].message.content` format. If the provider includes usage metadata, the adapter records it. It also converts common HTTP failures into clear runtime errors.

> The browser adapter uses Playwright. It opens the URL, locates the chat input, records the current page and assistant-message state, fills the prompt, clicks a visible send control or presses Enter, and waits for a response. Because many chatbots stream their output, it polls every half second and returns once the text remains stable for three polls.

> Input detection has three levels. An explicitly configured selector has priority. Next, a selector previously validated for the URL can be reused from the in-process cache. When enabled, AI DOM detection gathers only sanitized metadata for up to thirty visible form candidates. Groq returns a zero-based candidate index, not JavaScript or an arbitrary selector. We validate that index before using the internally generated selector. If AI detection fails, deterministic textarea and content-editable selectors remain the fallback.

> Response extraction first searches common assistant-message elements and compares their count with the pre-submission count. If that fails, it computes a page-body text delta while excluding the submitted prompt. A scan fails clearly if no response is detected within 45 seconds.

> For authorized sites requiring login, the Browser Session Manager opens headed Chromium with a persistent profile. The user performs login and first-party verification manually, closes the window, and later enables the saved profile for a scan. AgentProbe never receives the password. It also does not bypass CAPTCHA, Cloudflare, anti-automation controls, or website policy.

> We include a controlled chatbot so the complete system can be demonstrated safely. The `demo` model is deliberately weaker and `demo-hardened` applies a stronger policy. Both use a synthetic marker so we know objectively whether protected context was exposed. Groq powers this chatbot when configured, and deterministic behavior keeps the demo functional without an API key.

### Handoff

> Every adapter returns the same typed response to the pipeline. Person 3 will now show how the API contracts, repositories, and attack corpus provide the data on both sides of that interface.

### Likely Questions

**Can it automate every chatbot website?**

> No. It handles common chat interfaces and allows selector overrides, but iframes, unusual DOMs, authentication controls, and anti-bot systems can require site-specific integration.

**Why is target token usage zero for browser scans?**

> A browser UI normally does not expose provider usage metadata. We only report usage that the target API actually returns.

**Why is AI DOM detection safer than asking a model for a selector?**

> The model sees sanitized metadata and can only choose a bounded integer index. AgentProbe constructs and validates the actual selector itself.

## Person 3: Backend, MongoDB, and Dataset

### Files to Know

```text
apps/api/agentprobe/main.py
apps/api/agentprobe/config.py
apps/api/agentprobe/models.py
apps/api/agentprobe/repository.py
apps/api/agentprobe/template_repository.py
apps/api/agentprobe/templates.py
scripts/import_local_hackaprompt.py
start-local.ps1
compose.yaml
```

### Script

> FastAPI is the system boundary between the dashboard and scan engine. Pydantic models validate the run name, target URL, target type, categories, objective, and attempt budget. The target and browser-session models require explicit authorization confirmation before execution.

> Creating a scan returns HTTP 202. The route normalizes the requested outcome, constructs a `ScanRun`, stores it, and schedules the LangGraph pipeline as a background task. The frontend can then poll the run while it moves through queued, profiling, running, reporting, completed, or failed states.

> We use repository interfaces to separate application logic from storage. Run storage can use an in-memory dictionary or MongoDB. Local configuration currently uses memory, which is convenient for development but means scan history disappears on restart. The Mongo implementation stores complete validated run documents and supports persistent history.

> Template storage is configured independently and currently uses MongoDB. The `agentprobe.attack_templates` collection has 19,729 templates: 19,720 unique successful HackAPrompt prompts and nine built-in templates. Each template stores an ID, category, technique, prompt, source, prerequisites, and tags. The category is guaranteed to appear in the tags array.

> Retrieval applies MongoDB `$sample` independently for each requested category. We calculate how many records are needed per category, run the category queries concurrently, and combine the results in round-robin order. This creates category coverage without allowing the largest category to dominate. Missing records are filled from the local corpus and built-ins.

> The HackAPrompt source does not contain our nine-category taxonomy, so the importer classifies records using explicit keyword rules. It filters for successful submissions, removes duplicates, rejects invalid lengths, creates stable hash-based IDs, and records the original level and source. This is transparent and reproducible, although it is heuristic rather than semantic classification.

> At startup, FastAPI selects run and template repositories from environment settings, creates MongoDB indexes, initializes the browser-session manager, and constructs one shared pipeline. Important indexes cover unique IDs, tags, and category plus source.

### Handoff

> The backend continuously saves run state and exposes it through typed endpoints. Person 4 will show how the dashboard turns that state into a live testing and reporting interface.

### Likely Questions

**Why are run storage and template storage separate settings?**

> Templates benefit from MongoDB sampling even during local development, while transient in-memory run storage is simpler and faster. Production can enable MongoDB for both.

**Is template selection semantic?**

> No. Runtime selection is random within selected category tags. Context-awareness happens during attack adaptation. Semantic or vector retrieval is future work; ChromaDB is not active in the runtime path.

**How do you prevent duplicate imports?**

> Prompts are normalized for deduplication, stable IDs are derived from SHA-256 hashes, and MongoDB has a unique index on template ID.

## Person 4: Dashboard, Telemetry, Results, and Demo

### Files to Know

```text
apps/web/app/page.tsx
apps/web/app/globals.css
apps/web/app/tokens.css
apps/web/app/browser-session.css
apps/web/lib/api.ts
apps/web/lib/types.ts
README.md
```

### Script

> The dashboard is implemented in Next.js and React with TypeScript contracts matching the backend models. It is a single operational view for configuration, live execution, evidence inspection, and final reporting.

> The form supports API and browser targets, the desired outcome, attempt budget, and explicit authorization. Browser mode exposes the saved-session controls. Before a scan, the dashboard also retrieves system status, including whether Groq is configured, which models are active, whether AI DOM detection is enabled, the template backend, and the current template count.

> After creating a run, the UI polls the backend approximately every 1.5 seconds. The run's `live_exchange` metadata displays the current stage, category, submitted input, and current output. This is near-live state polling rather than token-by-token streaming.

> The result view clearly labels an ordinary attack objective versus a refusal control. The profiling log exposes the target probe, target response, Profiler Agent input and output, structured context, latency, and fallback status. Each attempt then preserves its source template ID, category, technique, adapted prompt, target response, latency, evaluation, severity, confidence, rationale, evidence, and role-specific token usage. This creates an audit trail rather than showing only a final score.

> The report summarizes total and successful attacks, attack success rate, average severity, category vulnerability, duration, recommendations, and token usage. Recommendations are mapped to the categories that actually succeeded. For example, an obfuscation finding recommends canonicalizing encoded input before safety classification.

> For the live demonstration, I will first select API mode, use `http://localhost:8000/api/v1/demo/chat`, choose the `demo` model, request a system-prompt disclosure test, confirm authorization, and run nine attempts. We will watch profiling, adaptation, target execution, and evaluation in the live panel. Then I will run the same objective against `demo-hardened` and compare the success rate and evidence.

> AgentProbe's value is not merely sending jailbreak strings. It provides an end-to-end, objective-aware, category-balanced and evidence-based security evaluation workflow with repeatable local ground truth. Our immediate future work is persistent production run storage, better mutation budgeting, semantic template retrieval, scan cancellation, report export, authentication, and cost controls.

### Closing

> In summary, the system separates orchestration, target execution, data storage, and user experience through typed interfaces. That separation lets us add a new target adapter, repository, evaluator, or UI visualization without rewriting the entire product. Thank you; we are ready for questions.

### Likely Questions

**Is the live view WebSocket streaming?**

> No. The frontend polls the run endpoint about every 1.5 seconds. The backend saves stage-level input and output in `live_exchange` metadata.

**Can users export a report?**

> Not yet. Results remain available in the UI for the lifetime of the configured run repository. PDF and JSON export are future work.

**What happens if Groq is unavailable?**

> Profiling and adaptation use deterministic fallbacks, the demo can use deterministic behavior, and evaluation falls back to marker checks and conservative heuristics.

## Coordinated Demo Checklist

1. Run `.\start-local.cmd` before the review.
2. Verify the dashboard at `http://localhost:3000`.
3. Verify API docs at `http://localhost:8000/docs`.
4. Confirm the status panel reports Groq, MongoDB templates, and the expected models.
5. Keep one completed `demo` run as a backup if live network calls fail.
6. Keep one completed `demo-hardened` run for comparison.
7. Open MongoDB Compass to `agentprobe.attack_templates` before presenting.
8. Rehearse the handoffs exactly once so no component is explained twice.
9. Do not claim ChromaDB, semantic retrieval, WebSocket streaming, universal browser support, or persistent local history as completed.
10. Use only targets for which explicit authorization has been obtained.

## One-Sentence Answers for the Whole Team

| Question | Answer |
|---|---|
| What problem does it solve? | It automates authorized prompt-injection testing and produces objective evidence instead of subjective manual results. |
| Why multi-agent? | Profiling, attack generation, and evaluation have different instructions and outputs, so separating them improves control and observability. |
| Where do attacks come from? | Successful HackAPrompt records in MongoDB plus nine built-in fallback templates. |
| What makes attacks target-aware? | The Attacker Agent receives the target profile, attack technique, and effective objective. |
| How is success measured? | Synthetic marker checks, an objective-aware Groq judge, and conservative fallback heuristics. |
| Is it safe to demo? | The built-in target uses synthetic protected data and requires explicit authorization confirmation. |
| Is it chatbot-independent? | The adapter interface is generic, but unusual APIs and websites may still require target-specific configuration. |
| What is the largest current gap? | Production hardening: persistent runs, authentication, cancellation, rate limits, cost budgets, and stronger adaptive attack scheduling. |
