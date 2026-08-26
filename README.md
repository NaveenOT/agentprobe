# AgentProbe

AgentProbe is an authorized prompt-injection testing framework. It profiles a chatbot, selects attacks across nine technique families, executes them through an API or browser, evaluates evidence, and produces a severity-based report.

The repository includes a deliberately vulnerable local chatbot so the full workflow can be demonstrated without probing a third-party service.

Browser targets require only a URL by default. AgentProbe searches for visible text inputs, content-editable chat boxes, accessible send buttons, and common assistant-message structures, then waits for streaming text to stabilize. Manual selectors remain available through the API when automatic detection cannot handle a custom DOM.

When Groq is configured, browser input detection sends sanitized metadata for visible form candidates to the AgentProbe model. The model can select only a validated candidate index; it cannot return executable JavaScript or an arbitrary selector. The validated selector is cached per target URL, and deterministic detection remains the fallback. Set `AGENTPROBE_AI_DOM_DETECTION=false` to disable this call.

For an authorized site that requires login, select Browser mode, enter its URL, and choose **Open Login Browser**. Sign in manually in the headed Chromium window, complete any first-party verification, and close the window before starting a scan with **Use saved browser login session** enabled. AgentProbe never asks for or stores the account password; Playwright stores the resulting local browser profile in ignored `data/browser-profile`. This does not bypass CAPTCHA, Cloudflare, site policy, or anti-automation controls.

## Repository Layout

```text
apps/
  api/agentprobe/
    adapters/       API and Playwright target adapters
    main.py         FastAPI application and scan endpoints
    pipeline.py     LangGraph scan orchestration
    evaluator.py    Deterministic and optional Groq judge
    reporting.py    Metrics and remediation aggregation
    demo.py         Controlled vulnerable target
  web/
    app/            Next.js dashboard
    lib/            API client and shared UI types
infra/              Container definitions
scripts/            Optional public dataset importers
tests/              Backend unit and graph tests
compose.yaml        MongoDB, API, and dashboard stack
```

## Quick Start With Docker

1. Copy `.env.example` to `.env`. A Groq key is optional for the controlled demo.
2. Run `docker compose up --build`.
3. Open `http://localhost:3000` for AgentProbe.
4. Open `http://localhost:8000/demo` to inspect the controlled browser target.
5. Keep the default API target and confirm authorization, then start the baseline scan.

The API documentation is available at `http://localhost:8000/docs`.

## Local Development

Docker and MongoDB are not required for local development. On Windows, start both services with:

```powershell
.\start-local.cmd
```

Open `http://localhost:3000`. This mode keeps runs in memory and resets them when the API stops.

To start each service manually, run the backend:

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
playwright install chromium
uvicorn agentprobe.main:app --app-dir apps/api --reload
```

Then run the dashboard in a second terminal:

```bash
npm install --prefix apps/web
npm run dev --prefix apps/web
```

Run validation:

```bash
pytest
ruff check .
npm run build --prefix apps/web
```

## Dataset Import

The local `hackaprompt_local` Hugging Face dataset is detected automatically. AgentProbe samples successful submissions across the complete corpus, deduplicates them, maps them into the nine-category taxonomy, and balances category selection at run time. Configure this behavior in `.env`:

```dotenv
AGENTPROBE_DATASET_ENABLED=true
AGENTPROBE_DATASET_PATH=hackaprompt_local
AGENTPROBE_DATASET_SAMPLE_LIMIT=5000
```

The dashboard labels each attempt with its source. Built-in templates remain as fallbacks when a requested category has no matching dataset record. Review source dataset licenses and restrict testing to explicitly authorized systems.

The optional `scripts/import_hackaprompt.py` command remains available when MongoDB and ChromaDB persistence are required.

## Groq Models

Create a replacement Groq key and place it only in the ignored `.env` file:

```dotenv
AGENTPROBE_GROQ_API_KEY=
AGENTPROBE_GROQ_MODEL=openai/gpt-oss-120b
AGENTPROBE_GROQ_TARGET_MODEL=openai/gpt-oss-20b
AGENTPROBE_DEMO_PROVIDER=auto
```

With a key configured, Groq powers target profiling, context-aware attack adaptation, evaluation, and the controlled test chatbot. `demo` uses the deliberately vulnerable target policy; requests with model `demo-hardened` use the hardened comparison policy. Without a key, the tool falls back to deterministic local behavior.

Completed reports include provider-reported token totals grouped by profiler, attacker, target, and evaluator. Browser targets cannot expose their own model usage, so their target token count remains zero unless the target API returns usage metadata.

## Attack Outcomes

Each run can specify a desired outcome. A blank value uses the synthetic protected-marker objective. The attacker adapts MongoDB templates to the effective objective and the evaluator judges the response against the same objective. Requests for credentials are converted to synthetic-canary tests; dangerous hard-drug manufacturing goals are converted to non-actionable refusal-policy checks.

## MongoDB Templates

Local development starts a native MongoDB process automatically and uses `agentprobe.attack_templates` for runtime prompt selection. Every template stores `tags: [category]`; AgentProbe applies MongoDB `$sample` independently per requested category and combines the results in round-robin order. Import the local successful HackAPrompt records with:

```powershell
$env:PYTHONPATH="apps/api"
.\.venv\Scripts\python scripts\import_local_hackaprompt.py
```

## Configuration

All backend settings use the `AGENTPROBE_` prefix. See `.env.example` for MongoDB, Groq, CORS, and model settings. The dashboard uses `NEXT_PUBLIC_API_URL`.

Groq improves evaluation of arbitrary targets. Without a key, AgentProbe uses deterministic marker detection and conservative heuristics, which makes the local demonstration repeatable.
