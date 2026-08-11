# local-ai-stack

<p align="center">
  <img src="assets/logo.svg" alt="local-ai-stack" width="720">
</p>

**Dual-node hybrid local AI stack** — orchestrate a CPU host plus a GPU secondary machine, tiering several local small models to get document automation done at low cost.

> Core value: no reliance on expensive cloud APIs. Organize heterogeneous CPU + GPU hardware and multiple local small models into a self-running three-tier agent system.

**README**: [English](README.md) | [中文](README.zh.md)

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="license">
  <img src="https://img.shields.io/badge/lang-English%20%26%20中文-0891b2.svg" alt="bilingual">
  <img src="https://img.shields.io/badge/docs-5%20topics-2ea44f.svg" alt="docs">
  <img src="https://img.shields.io/badge/architecture-dual--node%20%7C%20three--tier-6f42c1.svg" alt="architecture">
</p>

---

## Why

We face two real-world constraints:

1. **Cost sensitivity**: cloud LLM APIs bill per token; running long-term automation at cloud rates becomes uncontrollable.
2. **Heterogeneous hardware**: one iGPU host (strong CPU, no discrete GPU) plus an idle GPU secondary machine. A single machine cannot fit a large model, and the idle GPU goes to waste.

The local-ai-stack answer: **dual-machine cooperation + assigning the right small model per task difficulty**. Tiny 1.5B models for simple formatting/renaming, 8B for everyday text, 30B/14B for heavy reasoning, and vision tasks reserved exclusively for the GPU secondary machine. **Anything doable locally never goes to the cloud**; the cloud model is only a fallback.

## Core Features

- **Dual-node architecture**: the CPU host (keeping multiple models resident) handles dispatch and light tasks; the GPU secondary machine (a `llama-swap` service) handles real-time/heavy work (generation, vision, coding).
- **Three-tier agent dispatch**: decision agent (cloud, semantic judgment) → dispatch agent (local, task splitting) → execution agent (local small models, doing the work); anything it cannot do goes **back to a human for a decision — no automatic, budget-burning cloud escalation**.
- **Model tiering**: 1.5B formatting / 8B everyday / 14B+30B heavy / VL vision, routed automatically by task type.
- **Progressive skill loading**: wrap reusable flows (report templates, OCR pipelines) into skills that are **injected into the context only when used**, so they never blow through a small model's limited context window.
- **Automatic degradation on unavailability**: when the cloud API drops, fall back to local models and the system keeps running.
- **Humans keep the final say**: if any layer is stuck, it escalates to a human to decide — eliminating "automatic cloud escalation that burns money."

## Directory Structure

```
local-ai-stack/
├── README.md              # this file
├── README.zh.md           # Chinese version
├── LICENSE                # MIT
├── config/
│   ├── openclaw.example.json # sanitized config: three-tier dispatch + fallback chain + skill allowlist
│   └── llama-swap.example.yaml # dual-node llama-swap: host resident mode + GPU eviction mode
├── scripts/
│   ├── benchmark.py        # local LLM speed/accuracy benchmark (parametrized endpoint + models)
│   ├── tspeed.json         # request template for quick single-model speed checks
│   └── ocr_demo.py         # PaddleOCR one-shot document OCR (reading-order + table grouping)
└── docs/
    ├── architecture.md    # dual-node + three-tier dispatch (topology, agent roles, task flow)
    ├── model-tiering.md   # tiering strategy + measured performance baseline + routing rules
    ├── skills.md          # progressive skill loading + per-agent allowlist injection (ctx overflow prevention)
    ├── fallback.md        # fallback chain design + network resilience + local/cloud switching
    └── tuning.md          # optimization notes: system slimming, ctx tuning, pitfalls

> Every doc under `docs/` also has an English version suffixed `.en.md` (e.g. `architecture.en.md`), fully translated from the Chinese original.
```

## Quick Start (Overview)

1. On the **host**, run the OpenClaw gateway + `llama-swap` (three models resident on CPU: 30B/8B/1.5B).
2. On the **secondary machine** (with GPU), run a `llama-swap` service exposed as the `local-4070` endpoint (14B/vl/coder, etc.).
3. Configure OpenClaw providers to point at the two local endpoints, and define the multi-agent tiering.
4. Wrap reusable flows as skills, injected via per-agent allowlist.
5. Configure the cloud-model fallback chain (cloud → local 30B → local 8B).

For detailed steps see `docs/architecture.md`.

## Reproduce It Yourself

Everything in this repo exists to be copied and adapted, not just read. Suggested order:

1. **Models on two nodes** — adapt `config/llama-swap.example.yaml`:
   - host section: keep several small models resident (`swap: false`, `preload`);
   - GPU section: put the heavy/vision models in an `eviction` group so only one is loaded at a time.
   Start each node with `llama-swap -config <file> -listen ...`.
2. **Wire OpenClaw to both endpoints** — copy `config/openclaw.example.json`, replace the placeholders (`api.example.com`, ports, model aliases), and keep the three-tier agent list: `main` (cloud) → `courier`/`secretariat` (local 8B) → `super-engineer` (GPU 14B). Keep the skill allowlist per agent and the fallback chain intact.
3. **Measure your hardware** — run `scripts/benchmark.py` against your `llama-swap` endpoint to get real tok/s and pick the right tier per task (`python scripts/benchmark.py --url http://HOST:PORT/v1/chat/completions`).
4. **OCR a document** — `scripts/ocr_demo.py` shows a reusable PaddleOCR pipeline (reading-order sort + table grouping); adapt the paths to your own scans.
5. **Sweat the small-ctx constraint** — before adding skills, read `docs/skills.md` and `docs/tuning.md`: prefer `progressive loading` + per-agent allowlist, throttle bootstrap injection, and route large-context work to 30B or the cloud.
6. **Stay offline-fat** — keep the fallback chain (cloud → 30B → 8B) and test it by stopping your proxy; see `docs/fallback.md` for the diagnosis flow.

Each `docs/*` file has an English version under the same name with `.en.md`.

## Use Cases

- You have an idle GPU plus a CPU host and want to run local models for automation.
- Your workload is high-volume, repetitive, and formatting-heavy (document reports, recognition, organization) — too expensive on the cloud.
- You want several small models to divide work by complexity instead of one large model doing everything.

## Tech Stack

- [OpenClaw](https://github.com/openclaw/openclaw) — agent runtime and dispatch
- [llama-swap](https://github.com/mostlygeek/llama-swap) — multi-model routing gateway (OpenAI-compatible)
- Qwen family small models (1.5B / 8B / 14B / 30B) plus VL vision models
- Windows (dev machine) + Linux (GPU secondary machine)

## License

MIT

---

*Local-first · cost-sensitive · wherever a human can decide, never burn money on the cloud.*
