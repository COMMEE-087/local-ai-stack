# Fallback 链设计 + 网络容错

## 问题：云 API 断连时系统直接卡死

场景：主模型用云端（如 DeepSeek），某天**代理工具没启动**（Windows 上常见），所有走代理的云请求连不上，表现为"Agent failed before reply: network connection error"。不是 OpenClaw 的 bug，也不是模型挂了，是**底层网络（代理）没就绪**。

## 解法：Fallback 链（云端 → 本地，逐级降级）

配置一条模型降级链，云断自动落到本地，系统不中断：

```jsonc
// openclaw.json
{ "agents": { "defaults": { "model": {
    "primary":   "cloud/deepseek-chat",      // 首选：云端
    "fallbacks": [
      "local/qwen3:30b",   // 断网降级 1：本机 30B（不依赖外网）
      "local/qwen3:8b"     // 断网降级 2：本机 8B（兜底）
    ]
} } } }
```

- **首选**：云端语义强，正常情况用。
- **降级 1/2**：本地模型，**完全不依赖外网**，断网也跑。
- 效果：云断了，自动落到本机，任务不中断，代价只是质量略降。

## 关键经验（踩坑沉淀）

### 1. 本地端点不需要 API key

OpenClaw 对本地 `OpenAI-compatible` 端点（llama-swap）会显示 "Missing auth: set an API key"——**这是正常提示，本地端点直连免 key，不影响请求**。别被它误导。

### 2. 配置方法有坑

- 给 `agents.defaults.model.fallbacks` 赋值**不能直接用 `config set` 传内联 JSON 数组**（会报 "Too many arguments"）。
- **正确做法**：用专门的命令逐条加：
  ```bash
  openclaw models fallbacks add local/qwen3:30b
  openclaw models fallbacks add local/qwen3:8b
  ```
- **改完必须重启网关**才生效（`openclaw gateway restart`）。

### 3. 代理（HTTP_PROXY）是隐形杀手

Windows 上配置了系统代理（如 Clash/mihomo 到 `127.0.0.1:7890`），且环境变量 `HTTP(S)_PROXY` 全局生效。当代理进程没启动：
- 所有走代理的云请求 → 连不上 7890 → connection error。
- **症状看似"模型挂了"，实为"代理没起"**。

诊断要点：
```bash
# 看代理进程是否在跑（如 mihomo/Clash）
Get-Process | Where-Object {$_.Name -match "mihomo|clash|verge"}

# 直连 vs 走代理对比测试
curl --noproxy "*" https://api.example.com   # 直连看真实公网 IP
curl -x http://127.0.0.1:7890 https://api.example.com  # 走代理
```

### 4. 直连通常可行，代理非必须

很多云端 API（含 DeepSeek）**直连也能访问**（不走代理返回真实公网 IP 且正常响应）。是否走代理取决于你的网络策略。若本地能直连，可考虑让 OpenClaw 的云请求绕过代理环境变量，减少对代理进程的依赖。

## 网络故障排查流程（速查）

1. 报 "network connection error" → 先查**代理进程在不在**（最常见）。
2. 在 → 测代理端口连通性；不在 → 启动代理，或配云请求直连。
3. 云仍不通 → 验证 fallback 链是否能让本地模型接管（断网也能干）。
4. 本地也没有 → 回人拍板（harden 到 `architecture.md` 的"人留最终裁决"）。

---

> 本方案的直接价值：**把"云断了=全瘫"变成"云断了=自动降级本地，质量略降但不中断"**。
