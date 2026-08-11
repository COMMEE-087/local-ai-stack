# Model Tiering and Performance Baseline

## Rationale

Rather than "one large model doing everything," assign **different small models by task difficulty/type**:

| Tier | model | use | runs on |
|---|---|---|---|
| **T0 formatting** | 1.5B (Q8) | naming, very-fast formatting, simple rewriting | host CPU |
| **T1 everyday** | 8B | chat, task splitting, summarization, dispatch logic | host/secondary CPU |
| **T2 execution main** | 14B | document generation, scripting, tool-calling | secondary GPU |
| **T3 heavy/long-form** | 30B (MoE) | complex reasoning, long-text summarization | host CPU |
| **vision** | VL 7B | image understanding/OCR/chart recognition | secondary GPU |

## Why 14B on GPU and 30B on CPU (seems counter-intuitive)

- **14B**: small enough to fit in 12GB VRAM and reaches **~50 tok/s** on the GPU (below), suited for **real-time interactive generation**.
- **30B** (MoE A3B): large parameter count, cannot fit in small VRAM, but CPU RAM is enough and the MoE has only 3B active parameters, so pure-CPU still reaches **~20–25 tok/s**, suited for **long-form tasks that need quality rather than speed**.

> Conclusion: **speed needs → GPU 14B; quality needs → CPU 30B**. This is the optimal division on heterogeneous hardware.

## Measured Performance Baseline (numbers actually produced by this architecture)

> Note: values are hardware-dependent and only reference for selection. Single measurements contain cold-start noise; steady state is authoritative.

### Host (CPU, 8C16T, DDR5) — three models resident

| model | generation rate | note |
|---|---|---|
| qwen3:30b (MoE) | **~20–25 tok/s** | stable after warm-up; 8-core iGPU environment |
| qwen3:8b | ~11–13 tok/s | everyday |
| qwen2.5:1.5b (Q8) | ~20–23 tok/s | formatting only |

- All three models stay **resident simultaneously** (host has enough memory bandwidth); switching is just routing at 0.6–1.7s.
- 30B first-token cold start ~16.7s; warm start is much faster.

### Secondary (dedicated GPU 12GB) — one at a time

| model | generation rate | first cold load | hot load |
|---|---|---|---|
| instruct-14b | **~49 tok/s** | ~5s | <1s |
| coder-14b | ~49 tok/s | — | — |
| vl-7b (vision) | ~90+ tok/s | — | — |
| hermes2pro-8b | ~87 tok/s | — | — |
| qwen3:8b (CPU, secondary) | ~12 tok/s | — | — |

- 12GB VRAM **cannot fit a second large model**: switching = unload+reload (14B ~5–6s, 8B/7B ~2.5–3s).
- GPU 14B is about **3.8× faster** than CPU 8B (49 vs 13), confirming "real-time work goes to the GPU."

## Routing Rules (experience)

1. **Templated/batch documents** → T1 8B (good enough, cheap, fast)
2. **Real-time generation/interaction** → T2 14B (GPU)
3. **Long-form/complex reasoning** → T3 30B (CPU) or cloud
4. **Vision/OCR/charts** → VL 7B (GPU), **never run on CPU** (too slow to be usable)
5. **Naming/minimal formatting** → T0 1.5B
6. **Unsure** → try local first; on failure go back to a human, do not auto-escalate to cloud

## Context Window Budget (the key constraint for small models)

Small models have tiny ctx (8B≈16–32K, 14B≈16–24K), while the **agent-runtime-injected system prompt + skill list + workspace documents ≈ 12K tokens** heavily squeezes it.

Mitigations (see `skills.md`):
- Skills load **progressively**, not resident injection
- Inject only necessary skills via per-agent **allowlist**
- Limit bootstrap-injected character count (e.g., 2000/8000)
- Large-ctx needs go to 30B or the cloud

---

> Data collected from an actual deployment in production; see the tuning process and pitfalls in `tuning.md`.
