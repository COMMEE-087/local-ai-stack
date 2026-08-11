# local-ai-stack

**双机混合本地 AI 工作栈** — 用一台 CPU 主机 + 一台 GPU 副机，分层调度多个本地小模型，低成本完成文档自动化。

> 核心卖点：不依赖云端高额 API，把 CPU + GPU 异构硬件和多个本地小模型组织成一个可自主运行的三级智能体系统。

**README**: [English](README.md) | [中文](README.zh.md)

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
└── docs/
    ├── architecture.md    # 双机 + 三级分流架构详解（拓扑图、agent 分工、任务流）
    ├── model-tiering.md   # 模型分层策略 + 实测性能基准 + 路由规则
    ├── skills.md          # 技能渐进加载 + 按 agent 白名单注入（防 ctx 溢出）
    ├── fallback.md        # fallback 链设计 + 网络容错 + 本地/云端切换
    └── tuning.md          # 优化经验：系统瘦身、ctx 调优、踩坑记录
```

## 快速上手（概览）

1. **主机**跑 OpenClaw 网关 + `llama-swap`（CPU 常驻 30B/8B/1.5B 三模型）。
2. **副机**（有 GPU）跑 `llama-swap` 服务，暴露 `local-4070` 端点（14B/vl/coder 等）。
3. 配置 OpenClaw 的 provider 对接两个本地端点，定义多 agent 分级。
4. 把可复用流程写成 skill，按 agent 白名单注入。
5. 配好云模型 fallback 链（云端 → 本地 30B → 本地 8B）。

详细步骤见 `docs/architecture.md`。

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
