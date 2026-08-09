# Mainframe AI Assistant

An AI agent that diagnoses mainframe batch job failures using natural language,
built entirely with free/local tools (Python + Ollama + Qwen 2.5 3B) — no paid
API, no cloud dependency, runs fully offline after setup.

## What it does

You ask a plain-English question like *"Why did job PAYJOB01 fail, and is it
safe to rerun?"* — the agent independently:

1. Looks up the job's real status and abend/return code
2. Classifies the abend into a plain-English explanation
3. Checks the job log for supporting detail
4. Decides whether it's safe to rerun
5. If asked to rerun, **pauses and requires explicit human approval** before
   simulating the action — it never acts autonomously on anything irreversible

All of this happens through genuine multi-step tool-calling — the LLM decides
which tools to call and in what order, based on the question, not a hardcoded
script.

## Architecture

```
User question (plain English)
        |
        v
   Qwen 2.5 3B (via Ollama, local)
        |
        | decides which tool(s) to call
        v
  +-----------------------------+
  |  Python Tool Layer          |
  |  - get_job_status()         |
  |  - check_abend()            |
  |  - check_jcl()               |
  |  - check_rerun_eligibility()|
  |  - rerun_job()  <-- gated   |
  +-----------------------------+
        |
        | real result (or clean error)
        v
   Qwen 2.5 3B interprets result
        |
        v
  Plain-English answer to user
```

For actions (not just information), a **human-in-the-loop gate** sits between
the model's request and execution — `rerun_job` will not run unless a real
person explicitly approves it at runtime.

## Why Ollama instead of a paid API

This project was deliberately built free of any paid API key, using Ollama to
run Qwen 2.5 3B locally. The architecture is model-agnostic by design — the
tool-calling pattern (`tools=[...]`, `AVAILABLE_FUNCTIONS`, the `while`/`for`
loop) is the same shape used by Claude, OpenAI, and Bedrock's APIs. Swapping
in a hosted model later is a small config change, not a redesign.

## Project structure

```
mainframe_ai_assistant/
├── agent.py                    # Core agent loop, tool definitions, safety checks
├── data/
│   └── synthetic_jobs.json     # Synthetic mainframe job/failure data
├── tools/
│   └── mainframe_tools.py      # Individual, independently-tested Python tools
├── tests/
│   └── test_multiple_failures.py  # Runs the agent against 7 different scenarios
└── README.md
```

## Setup

1. Install [Ollama](https://ollama.com/download)
2. Pull the model: `ollama pull qwen2.5:3b`
3. Install the Python client: `pip install ollama`
4. Run: `python agent.py` (or import `ask_agent` for custom questions)

No API key, no signup, no cost.

## Safety design

- **Error handling**: every tool function returns a clean error dict instead
  of raising an unhandled exception — bad job IDs, unknown abend codes, and
  missing data are all handled gracefully.
- **Layer 2 validation**: the agent cross-checks tool calls against the *real*
  data already fetched earlier in the conversation (not the user's wording),
  catching cases where the model tries to substitute an incorrect code.
- **Human-in-the-loop**: any action with real-world consequence (`rerun_job`)
  requires a live, explicit human "yes" before it executes — the model can
  recommend, but never authorize, an action on its own.

## Known limitations (found through testing, not assumed)

Being upfront about these is part of the engineering, not a weakness to hide:

- **Narration instead of action**: on a first pass, the 3B model sometimes
  described an intended tool call in plain text instead of actually issuing
  it. Fixed via a stricter system prompt, but this is a known tendency of
  smaller local models and worth monitoring.
- **Code substitution hallucination**: the model occasionally substituted a
  different, more "familiar" code than the one actually being discussed
  (e.g. answering about S0C7 when asked about an unrecognized code). Caught
  and mitigated via the Layer 2 ground-truth check described above.
- **Reasoning shortcuts**: in some multi-step questions, the model reached a
  correct conclusion (e.g. "not safe to rerun") without calling the dedicated
  `check_rerun_eligibility` tool — inferring instead of verifying. The
  answer happened to be right, but the *process* skipped a verification step.
  This is the clearest argument for why safety checks like Layer 2 matter:
  small models can be right for the wrong reason.
- **Hardware constraint**: tested and tuned specifically for 8GB RAM systems
  using the 3B model class; a 7B+ model would likely reduce these issues but
  wasn't feasible on this hardware.

## Example run

```
USER: Why did job PAYJOB01 fail?
  [Step 1] MODEL CALLS: get_job_status({'job_id': 'PAYJOB01'})
  [Step 2] MODEL CALLS: check_abend({'retcode': 'S0C7'})
  [Step 3] MODEL CALLS: check_jcl({'job_id': 'PAYJOB01'})

AGENT'S FINAL ANSWER:
The raw job log snippet indicates that a data exception occurred in the
program PAYCALC at field EMP-SALARY, specifically due to non-numeric data...
```

## What this demonstrates

- Real multi-step agentic tool-calling (not a single-shot chatbot wrapper)
- Defensive engineering around a genuinely imperfect small LLM — validation,
  not blind trust
- Human-in-the-loop design for any action with consequences
- A model-agnostic architecture, ready to swap to a hosted LLM API later
- Testing discipline: every tool independently verified before integration,
  then the full agent tested against 7 distinct failure scenarios

## Possible future extensions

- Swap Ollama for Claude/OpenAI/Bedrock API (architecture already supports this)
- Connect to real z/OSMF REST API instead of synthetic data
- RAG over historical incident tickets for pattern-based diagnosis
- Web UI instead of terminal interaction
