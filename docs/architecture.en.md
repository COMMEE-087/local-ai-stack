# Architecture: Dual-Node + Three-Tier Agent Dispatch

## Design Goals

1. **Cheap**: anything doable locally never calls a cloud API; the cloud is only for decision-making and fallback.
2. **Fast**: real-time/heavy work (generation, vision, coding) runs on the GPU secondary machine and does not occupy the host CPU.
3. **Stable**: when a single machine cannot fit a large model, split the work across two machines; when the cloud drops, local models take over.
4. **Controlled**: no one can "escalate to the cloud on their own and burn money" — anything stuck goes back to a human for a decision.

## Dual-Node Topology

```
┌────────────── host (iGPU CPU, e.g. AMD 780M / Ryzen) ──────────────┐
│ OpenClaw gateway        llama-swap @8087             local KB        │
│  ┌──────────────┐       ├─ qwen3:30b   main, long-form   (optional ChromaDB)
│  │ L1 decision  │       ├─ qwen3:8b    everyday                      │
│  │ L2 dispatch  │       └─ qwen2.5:1.5b very fast formatting         │
│  └──────────────┘                                                    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ inter-agent dispatch (HTTP/WS)
                          ▼
┌────────────── secondary (dedicated GPU, 12GB+ VRAM) ────────────────┐
│ llama-swap @11440 (OpenAI-compatible endpoint)                      │
│  GPU pool: instruct-14b / coder-14b / vl-7b / hermes2pro-8b        │
│  CPU pool: qwen3:8b (long-text summarization, no GPU)              │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Two Machines

- **Host**: strong CPU, large RAM (64GB-class), good for **keeping multiple small models resident simultaneously** (30B/8B/1.5B can all be loaded at once; switching is just routing with no reload cost).
- **Secondary**: has a dedicated GPU but limited VRAM (12GB-class, **cannot fit a second large model** — only one at a time, switching requires unload+reload 2–6s). Suited for **real-time heavy work** (generation, vision, coding).

> Key insight: the host "keeps everything resident, never switches," while the secondary "one at a time, swapped on demand." This is dictated by memory bandwidth vs. VRAM capacity — a hardware property that configuration cannot work around.

## Three-Tier Agent Dispatch

| Tier | agent | model | responsibility | fallback |
|---|---|---|---|---|
| **L1 decision** | main | cloud model (strong semantics) | receive task → judge whether local can do it → if yes dispatch to L2, if no do it itself or ask a human | human is the final arbiter |
| **L2 dispatch** | courier / secretariat | local 8B | split task → dispatch execution sub-tasks in parallel → collect and aggregate | if stuck → return to L1, ask you |
| **L3 execution** | business execution agent | local 14B/8B | do the actual work (document generation, recognition, coding) | `__ESCALATE__` upstream |

### Task Flow (Three Cases)

**Case 1: local can handle it**
```
you → L1: judge "can this task be done locally?"
   → yes → L2 splits → spawn execution sub-tasks in parallel (specify 14B, don't inherit 8B CPU)
   → L2 aggregates → L1 → you
```

**Case 2: local cannot handle it**
```
L2 tries then fails → returns __ESCALATE__ + reason
   → L1 does NOT auto-escalate to cloud, but ASKS YOU "local can't do this (reason X), escalate to cloud?"
   → you decide: cloud / alternative / give up
```

**Case 3: it should be cloud or done by you from the start**
```
L1 receives → judges local not needed → handles directly or asks you → does not go through L2
```

### L1 Dispatch Criteria

When receiving a task, ask yourself:
1. Needs GPU/vision/transcoding? → L2 → business execution agent (secondary)
2. Needs retrieval / large-volume text? → L2 → local 30B
3. Pure formatting/naming/spreadsheet? → L2 → local 1.5B/8B
4. Complex reasoning/long-form/quality matters? → itself (cloud) or ask a human
5. Unsure local can do it → hand to L2 to try; on failure ask a human

## Key Mechanisms (Hard Rules)

- **No automatic cloud escalation**: any tier `__ESCALATE__`s or fails → return to L1 to ask a human. **If a human has not decided, do not spend on the cloud.**
- **Dispatch via one-shot clean sub-sessions**: resident agent sessions are not suited for multi-step dispatch (ctx accumulates and overflows) → use one-shot `spawn` sub-sessions for dispatch.
- **Execution sub-tasks must specify the model explicitly**: spawned sub-tasks inherit the parent model, so you must explicitly pass 14B (fast GPU), not inherit the 8B CPU.
- **Auto-clean after use**: all spawned sub-sessions carry `cleanup:"delete"` (archived after reporting) plus age-based auto-archive (e.g., 20 minutes) — no residue.
- **Inter-agent access**: configure an agentToAgent allowlist (main ↔ dispatch ↔ execution).

## Why "Humans Keep the Final Say"

Automatic cloud escalation = unbounded cost risk. The system is designed so that "any layer stuck → escalate to a human → a human decides (cloud / alternative / give up)."

This is a **cost guardrail, not a feature deficiency**: machines execute and attempt; humans decide on value and budget.

---

> This architecture diagram comes from production, validated in practice (see the performance baseline in `model-tiering.md` and the pitfalls in `tuning.md`).
