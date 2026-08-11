# local-ai-stack

<p align="center">
  <img src="assets/logo.svg" alt="local-ai-stack" width="720">
</p>

**双机混合本地 AI 工作栈** — 用一台 CPU 主机 + 一台 GPU 副机，分层调度多个本地小模型，低成本完成文档自动化。

> 核心卖点：不依赖云端高额 API，把 CPU + GPU 异构硬件和多个本地小模型组织成一个可自主运行的三级智能体系统。

**README**: [English](README.md) | [中文](README.zh.md)

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="license">
  <img src="https://img.shields.io/badge/lang-English%20%26%20中文-0891b2.svg" alt="bilingual">
  <img src="https://img.shields.io/badge/docs-5%20topics-2ea44f.svg" alt="docs">
  <img src="https://img.shields.io/badge/architecture-dual--node%20%7C%20three--tier-6f42c1.svg" alt="architecture">
</p>

---

## 为什么做这个

面对两类真实约束：

1. **成本敏感**：云端大模型 API 按 token 计费，长期跑自动化任务开销不可控。
2. **硬件异构**：一台核显主机（CPU 强、无独立 GPU）+ 一台闲置 GPU 副机，单机装不下大模型，闲置 GPU 又浪费。

local-ai-stack 的解法：**双机协同 + 按任务难度分配合适的小模型**。简单格式化/命名用极小的 1.5B 模型，日常文本用 8B，复杂推理用 30B/14B，视觉任务独留给 GPU 副机。**能本地办到的绝不上云**，云模型只作兜底。

## 核心特性

- **双机架构**：CPU 主机（常驻多模型）负责调度与轻量任务；GPU 副机（`llama-swap` 服务）负责实时/重活（生成、视觉、编码）。
- **三级智能体分流**：决策 agent（云端语义判断）→ 调度 agent（本地拆单分发）→ 执行 agent（本地小模型干活）；干不了的**回人决断，不自动烧钱上云**。
- **模型分层（tiering）**：1.5B 格式化 / 8B 日常 / 14B+30B 重活 / VL 视觉，按任务类型自动路由。
- **技能渐进加载**：把可复用流程（报告模板、OCR 流程）封装成 skill，**用时才注入上下文**，不撑爆小模型有限的 context window。
- **不可用自动降级**：云 API 断连时 fallback 本地模型，系统不中断。
- **人留最终裁决权**：任何层搞不定 → 上报人类拍板，杜绝"自动上云烧钱"。

## 目录结构

```
local-ai-stack/
├── README.md              # 英文版
├── README.zh.md           # 本文件（中文版）
├── LICENSE                # MIT
├── config/
│   ├── openclaw.example.json # 脱敏配置：三级分流 + fallback 链 + 技能白名单
│   └── llama-swap.example.yaml # 双节点 llama-swap：主机常驻模式 + GPU 按需换模式
├── scripts/
│   ├── benchmark.py        # 本地模型测速/准确度基准（端点+模型名参数化）
│   ├── tspeed.json         # 单模型快速测速的请求模板
│   └── ocr_demo.py         # PaddleOCR 文档识别示例（阅读排序 + 表格分组）
└── docs/
    ├── architecture.md    # 双机 + 三级分流架构详解（拓扑图、agent 分工、任务流）
    ├── model-tiering.md   # 模型分层策略 + 实测性能基准 + 路由规则
    ├── skills.md          # 技能渐进加载 + 按 agent 白名单注入（防 ctx 溢出）
    ├── fallback.md        # fallback 链设计 + 网络容错 + 本地/云端切换
    └── tuning.md          # 优化经验：系统瘦身、ctx 调优、踩坑记录

> `docs/` 下每篇均有英文版（后缀 `.en.md`，如 `architecture.en.md`），由中文原文完整翻译。
```

## 快速上手（概览）

1. **主机**跑 OpenClaw 网关 + `llama-swap`（CPU 常驻 30B/8B/1.5B 三模型）。
2. **副机**（有 GPU）跑 `llama-swap` 服务，暴露 `local-4070` 端点（14B/vl/coder 等）。
3. 配置 OpenClaw 的 provider 对接两个本地端点，定义多 agent 分级。
4. 把可复用流程写成 skill，按 agent 白名单注入。
5. 配好云模型 fallback 链（云端 → 本地 30B → 本地 8B）。

详细步骤见 `docs/architecture.md`。

## 自己复现（实操顺序）

仓库里的一切都是给你**照抄改写**的，不只是读的。建议顺序：

1. **双节点模型** — 改 `config/llama-swap.example.yaml`：
   - 主机段：让多个小模型常驻（`swap: false` + `preload`）；
   - GPU 段：把重活/视觉模型放进 `eviction` 组，同一时刻只加载一个。
   两个节点各用 `llama-swap -config <文件> -listen ...` 启动。
2. **OpenClaw 对接两端点** — 复制 `config/openclaw.example.json`，替换占位符（`api.example.com`、端口、模型别名），保留三级 agent 名单：`main`（云端）→ `courier`/`secretariat`（本地 8B）→ `super-engineer`（GPU 14B）。保持每个 agent 的技能白名单和 fallback 链不变。
3. **测你的硬件** — 对自家 `llama-swap` 端点跑 `scripts/benchmark.py` 拿真实 tok/s，再按任务选层（`python scripts/benchmark.py --url http://HOST:PORT/v1/chat/completions`）。
4. **OCR 一份文档** — `scripts/ocr_demo.py` 提供了可复用的 PaddleOCR 流水（阅读排序 + 表格分组），把路径换成你自己的扫描件。
5. **盯紧小 ctx 约束** — 加技能前先读 `docs/skills.md` 和 `docs/tuning.md`：优先**渐进加载** + 按 agent 白名单，限流 bootstrap 注入，大上下文任务走 30B 或云端。
6. **保持断网可用** — 保留 fallback 链（云端 → 30B → 8B），停掉代理实测降级是否生效；诊断流程见 `docs/fallback.md`。

每篇 `docs/*` 都有同名 `.en.md` 英文版。

## 适用场景

- 你有闲置 GPU + 一台 CPU 主机，想跑本地模型做自动化。
- 你的任务量大、重复、格式化（文档报告、识别、整理），走云端太贵。
- 你想让多个小模型按复杂度分工，而不是"一个大模型硬扛所有"。

## 技术栈

- [OpenClaw](https://github.com/openclaw/openclaw) — agent 运行时与调度
- [llama-swap](https://github.com/mostlygeek/llama-swap) — 多模型路由网关（OpenAI-compatible）
- Qwen 系列小模型（1.5B / 8B / 14B / 30B） + VL 视觉模型
- Windows（开发机）+ Linux（GPU 副机）

## License

MIT

---

*本地优先 · 成本敏感 · 人能拍板的地方绝不上云烧钱。*
