# 🤖 Digital FTE Agent — Sentinel

![Lines of code](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/furqunali/digital-fte-agent/main/.github/badges/loc.json)

A prototype **"Digital FTE" (Full-Time-Equivalent) sentinel**: a background agent that watches an inbox for new instructions, processes them, and writes results back to a dashboard — the seed of an AI co-worker that handles tasks autonomously.

## How it works

- **Watches** an `AI_Employee_Vault/Inbox` folder for new `.md` instruction files (`watchdog`)
- On a new instruction, **processes** it and generates an output (e.g. a plan) into `AI_Employee_Vault/Dashboard/`
- Organised around a **Vault** structure — a `Constitution.md` (operating rules), `Inbox`, `Skills`, and `Dashboard` — mirroring the spec-driven "Digital FTE" architecture

## Run it

```bash
pip install watchdog
python watcher.py
```

Then drop a `.md` task file into `AI_Employee_Vault/Inbox/` and watch it get picked up.

## Concept

Part of my work on **Digital FTEs** — AI workers defined by specs + domain knowledge + human oversight. See also my [`Digital_FTE`](https://github.com/furqunali/Digital_FTE) repo.



## State & CLI Reliability

The persisted loop state is validated before resume: task identifiers, iteration counts, final state, nested step/event data, and collection lengths must match the stored schema. The CLI reports malformed persisted state as `invalid_state` instead of leaking a traceback, including the inconsistent step/event case covered by regression tests.

---

*Part of [Furqan Ali](https://github.com/furqunali)'s portfolio — AI & Intelligent Automation / Digital Transformation.*
