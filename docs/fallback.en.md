# Fallback Chain Design + Network Resilience

## Problem: cloud API drop stalls the whole system

Scenario: the primary model uses the cloud (e.g., DeepSeek), and one day the **proxy tool isn't started** (common on Windows), so all proxied cloud requests fail, surfacing as "Agent failed before reply: network connection error." It's not an OpenClaw bug, nor a dead model — the **underlying network (proxy) isn't ready**.

## Solution: Fallback chain (cloud → local, degraded step by step)

Configure a model degradation chain so a cloud drop automatically falls to local models and the system keeps running:

```jsonc
// openclaw.json
{ "agents": { "defaults": { "model": {
    "primary":   "cloud/deepseek-chat",      // preferred: cloud
    "fallbacks": [
      "local/qwen3:30b",   // offline degradation 1: local 30B (no internet needed)
      "local/qwen3:8b"     // offline degradation 2: local 8B (last resort)
    ]
} } } }
```

- **Preferred**: cloud, strong semantics, used normally.
- **Degradation 1/2**: local models, **completely independent of the internet**, run even offline.
- Result: cloud drops → automatically falls to local, task continues, the only cost is slightly lower quality.

## Key Experience (pitfalls distilled)

### 1. Local endpoints need no API key

OpenClaw shows "Missing auth: set an API key" for local `OpenAI-compatible` endpoints (llama-swap) — **this is normal; local endpoints connect directly, key-free, and it does not affect requests.** Don't be misled by it.

### 2. Configuration has gotchas

- Assigning `agents.defaults.model.fallbacks` **cannot be done via `config set` with inline JSON arrays** (raises "Too many arguments").
- **Correct way**: add entries one by one with the dedicated command:
  ```bash
  openclaw models fallbacks add local/qwen3:30b
  openclaw models fallbacks add local/qwen3:8b
  ```
- **You must restart the gateway after changes** for them to take effect (`openclaw gateway restart`).

### 3. Proxy (HTTP_PROXY) is the silent killer

Windows has a system proxy configured (e.g., Clash/mihomo at `127.0.0.1:7890`) and the `HTTP(S)_PROXY` env vars apply globally. When the proxy process isn't running:
- Every proxied cloud request → can't reach 7890 → connection error.
- **Symptoms look like "the model is down," but it's really "the proxy wasn't started."**

Diagnosis:
```bash
# Is the proxy process running? (e.g., mihomo/Clash)
Get-Process | Where-Object {$_.Name -match "mihomo|clash|verge"}

# Direct vs proxied comparison
curl --noproxy "*" https://api.example.com   # direct, see the real public IP
curl -x http://127.0.0.1:7890 https://api.example.com  # via proxy
```

### 4. Direct connection usually works; proxy is not required

Many cloud APIs (including DeepSeek) **work fine when connected directly** (no proxy, returns the real public IP and responds normally). Whether to use a proxy depends on your network policy. If local direct connection works, consider letting OpenClaw's cloud requests bypass the proxy env vars to reduce dependence on the proxy process.

## Network Troubleshooting Flow (quick reference)

1. "network connection error" → first check **whether the proxy process is up** (most common).
2. Up → test proxy port connectivity; down → start the proxy, or configure cloud requests for direct connection.
3. Cloud still down → verify the fallback chain lets local models take over (works even offline).
4. No local model either → back to a human to decide (ties into "humans keep the final say" in `architecture.md`).

---

> The direct value of this approach: turning "cloud down = total outage" into "cloud down = automatic degradation to local, slightly lower quality but no interruption."
