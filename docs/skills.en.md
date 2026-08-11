# Progressive Skill Loading + Per-Agent Allowlist Injection

## Problem: small-model ctx cannot fit skills

Small models have a limited context window (8B≈16–32K, 14B≈16–24K). If you made every reusable flow (report templates, OCR steps, checklists) a "resident system prompt," the agent-runtime self-injection (system prompt + skill list + workspace documents ≈ **12K tokens**) would blow it up.

## Solution: Progressive Disclosure

OpenClaw's skill mechanism supports this natively: **only "name + one-line description" is injected into the context; the body (SKILL.md content) is read on demand only when the agent actually needs it.**

Two benefits:
1. **Nearly zero ctx footprint**: only a one-line description stays resident, not the whole flow.
2. **No pollution from rarely-used skills**: unused skills consume no attention at all.

## Key Mechanisms

### 1. SKILL.md format

One directory per skill, with `SKILL.md` at the root:

```markdown
---
name: my-workflow
description: one-line description of trigger conditions and use (this line is injected into ctx)
metadata:
  { "openclaw": { "os": ["win32"], "requires": { "bins": ["python"] } } }
---

# Full flow (body, loaded only when used)
- step 1...
- step 2...
```

- **description must be very short** (one line) — this is the only resident-ctx part.
- The **frontmatter `name`** is the skill identifier (no slug conflicts).
- **`metadata.openclaw.requires`** can act as a gate (e.g., require `python`/`ssh` to exist before activating); it won't load when a dependency is missing.

### 2. Per-agent allowlist injection (the core ctx-overflow guard)

OpenClaw's `agents.list[].skills` is an **allowlist** (the list of skills that agent is allowed to see):

```jsonc
// openclaw.json
{ "agents": { "list": [ {
    "id": "worker-1",
    "skills": ["my-workflow", "ocr-flow"]   // only these 2 are allowed; all others excluded
} ] } }
```

- **`skills: []` (empty array) = the agent sees no skills at all** (all disabled).
- **A skill installed but not in the allowlist = exists but invisible** ("excluded by agent allowlist").
- Only explicitly listed skills are injected; **everything else (including built-ins like browser/notion/weather) is excluded**.

This turns "which skills to give which agent" into **precise control**: a business execution agent only carries the skills it uses; dispatch/decision agents carry no skill injection at all.

### 3. Optional: fully disable model injection

If a skill is only meant for manual invocation (slash command / explicit call) and **should not enter the resident prompt**:

```markdown
---
name: heavy-tool
description: heavy-lifting tool
disable-model-invocation: true
---
```

The skill's instructions then stay out of the agent's daily prompt and load only when explicitly requested — **the strongest ctx protection**.

## Install and Verify

```bash
# Install from a local directory into a specific agent's workspace
openclaw skills install ./my-skill --agent worker-1

# See which skills an agent can actually see and their injection state
openclaw skills list --agent worker-1
openclaw skills check --agent worker-1
```

`check` tells you: `Visible to model: N` / `Excluded by agent allowlist: M` — at a glance who is consuming whose ctx.

## Practice Suggestions

- **One-line description**, keep the body lean (paste the flow and commands, not lengthy prose).
- **Assign skills by agent responsibility**: execution agents get what they need; dispatch/decision agents preferably `skills: []`.
- **Manually tier large-ctx needs (long docs/complex reasoning)**: when lots of history must be carried, don't stuff it into a small-ctx agent; route to 30B or the cloud instead (see `model-tiering.md`).
- Verify a skill is truly active: use `sessions_send` to ask that agent "what skills do you have and how would you execute them," and check it repeats them correctly.

---

> This method resolves the classic "installing a skill = blowing up the small model's ctx" contradiction, making skill injection serve the business rather than hurt performance.
