# Optimization Notes and Pitfalls

> Reusable lessons from running this system end to end. Every item was earned by actually hitting a pitfall, to save you from repeating the work.

## 1. System Slimming (Windows)

Used Win11Debloat for system trimming. After 13 measured changes (stopping Windows Update service, removing telemetry scheduled tasks, disabling background apps, etc.):

- **Inference speed did not meaningfully regress** (peak tok/s differences are measurement noise).
- **The real gain was stability**: background tasks (updates/telemetry) no longer randomly interrupt your inference process.

> Conclusion: system slimming is not for "speeding up" but for **eliminating background interference**. Don't expect tok/s to soar.

### Operating rules
- **Back up the registry first** (Debloat auto-creates a `Backups/` folder; keep it for reference).
- Record a baseline (performance, state) before changes so you can compare after.
- Stop when good; don't over-trim and break the system.

## 2. Benchmark Pitfalls

- **Request templates are not universal**: different scripts (e.g., qspeed/bench) depend on different request-template files (tspeed.json); missing ones cause errors. Confirm a script's dependencies before benchmarking.
- **First measurement contains cold-start noise**: a model's first load is slow (30B first-token 16s+), so **let it warm up and take the steady-state mean**; don't draw conclusions from the first number.
- **Multiple resident models compete for memory bandwidth**: when the host loads several models at once, a single model measures slightly lower than when alone — that's bandwidth contention, not a failed optimization.

## 3. Small-Model Context Window Tuning (the most critical pitfall)

Small models have limited ctx, while the **agent-runtime injection (system prompt + skill list + workspace documents) ≈ 12K tokens** heavily squeezes or even overflows it.

### Mitigations (use together)
1. **`tools.profile: "minimal"`**: cuts most tools, keeping only the essentials. ⚠️ But minimal is so extreme it **leaves only 1 tool**, so you must use `tools.alsoAllow` to precisely add back the duty tools (read/write/exec/sessions_*, etc.), or the agent can only chat, not work.
2. **`skills: []`** + per-agent allowlist (see `skills.md`): disable skill injection, save 4–5K tokens.
3. **Bootstrap injection throttling**: `bootstrapMaxChars` / `bootstrapTotalMaxChars` limit the character count of injected documents (e.g., 2000/8000).
4. **Tier large-ctx tasks**: when lots of history must be carried, route to 30B (large window) or cloud instead of stuffing a small-ctx agent.

> ⚠️ Real lesson: after configuring the minimal profile you **must** verify the tools were really added back — "verified" may be a false positive; the agent can actually only chat and not execute tasks.

## 4. Architecture Execution Pitfalls

1. **Resident agent threads aren't suited to multi-step dispatch**: ctx accumulates and overflows across tasks, or it "answers but doesn't run." → Use **one-shot clean `spawn` sub-sessions** for dispatch.
2. **Sub-sessions inherit the parent model**: a spawned sub-task, unless explicitly specified, inherits the parent agent's model — heavy work must explicitly pass the target model (e.g., 14B GPU), not inherit the 8B CPU and get slow.
3. **Aggregation agents drift/generalize**: having 8B do "strict item-by-item merge" tends to invent or miss entries. → Add a hard constraint: "merge strictly item-by-item based on input; add nothing, assume nothing."
4. **Sub-sessions must be cleaned**: use `cleanup:"delete"` when done plus age-based auto-archive, leaving no residue, or the more resident sessions, the slower things get.

## 5. Cross-Platform File Transfer (Chinese Filenames)

**Transferring Chinese filenames from Windows to Linux garbles them** (GBK enters the tar header, Linux shows mojibake, paths can't be found).

Solution:
- Rename assets to a hash/ASCII-unique mapping before transfer.
- Don't match filenames with Chinese literals in scripts (they'll mismatch); rely on ASCII aliases.
- Write complex logic as script files and execute them, rather than piling up Chinese characters in the shell.

## 6. PaddleOCR Environment

- Install PaddleOCR in a separate environment (to avoid polluting system Python). If installing into system Python, mind the version (3.13+ works).
- A single-page scan takes ~8s to recognize (warm model) — a useful rhythm reference for batch processing.

## Efficiency Philosophy

- **Templatize, script, and skill-ify every flow**: sink what you finish on the spot; don't re-derive it.
- **Investigate existing assets before building**: avoid reinventing the wheel.
- **Measurement-driven**: measure before and after every change; let data speak, not feelings.
