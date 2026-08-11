# 技能（Skill）渐进加载 + 按 Agent 白名单注入

## 问题：小模型 ctx 不够装技能

小模型的上下文窗口有限（8B≈16–32K、14B≈16–24K）。若把所有可复用流程（报告模板、OCR 步骤、检查清单）都做成"常驻系统提示"，会被 agent 运行时自身注入（系统提示 + 技能列表 + 工作区文档 ≈ **12K tokens**）挤爆。

## 解法：渐进加载（Progressive Disclosure）

OpenClaw 技能机制天然支持：**技能只注入"名字 + 一句描述"进上下文，正文（SKILL.md 主体）在 agent 实际需要时才按需读取。**

这带来两个好处：
1. **ctx 几乎零占用**：常驻的只有一行描述，不是整篇流程。
2. **不会被低频技能污染**：用不到的技能不占任何注意力。

## 关键机制

### 1. SKILL.md 格式

每个技能一个目录，根放 `SKILL.md`：

```markdown
---
name: my-workflow
description: 一句话描述触发条件与用途（这条会注入 ctx）
metadata:
  { "openclaw": { "os": ["win32"], "requires": { "bins": ["python"] } } }
---

# 完整流程（正文，用时才加载）
- 步骤 1...
- 步骤 2...
```

- **description 必须极短**（一句话）——这是唯一常驻 ctx 的部分。
- **frontmatter 的 `name`** 即技能标识（不加 slug 冲突）。
- **`metadata.openclaw.requires`** 可做门槛（如要求 `python`/`ssh` 存在才激活），缺依赖不误加载。

### 2. 按 Agent 白名单注入（防 ctx 溢出的核心）

OpenClaw 的 `agents.list[].skills` 是一个 **allowlist**（允许该 agent 看到的技能列表）：

```jsonc
// openclaw.json
{ "agents": { "list": [ {
    "id": "worker-1",
    "skills": ["my-workflow", "ocr-flow"]   // 只允许这 2 个，其余全排除
} ] } }
```

- **`skills: []`（空数组）= 该 agent 一个技能都看不到**（全禁）。
- **装了技能但没加进 allowlist = 技能存在但不可见**（"excluded by agent allowlist"）。
- 只有显式列入的技能才会被注入，**其余（含系统自带的 browser/notion/weather 等）全部排除**。

这让"给哪个 agent 配哪些技能"变成**精确控制**：业务执行 agent 只背它要用的技能，调度/决策 agent 完全不背技能注入。

### 3. 可选：完全禁用模型注入

若某个技能只想让人手动调（斜杠命令/显式调用），**不想进常驻 prompt**：

```markdown
---
name: heavy-tool
description: 重活工具
disable-model-invocation: true
---
```

这样该技能指令不进 agent 日常 prompt，只在被显式请求时加载——**最强 ctx 保护**。

## 安装与验证

```bash
# 从本地目录安装到指定 agent 的 workspace
openclaw skills install ./my-skill --agent worker-1

# 查看某 agent 实际能看到哪些技能、注入状态如何
openclaw skills list --agent worker-1
openclaw skills check --agent worker-1
```

`check` 输出会告诉你：`Visible to model: N` / `Excluded by agent allowlist: M`——一眼看出谁的 ctx 被谁占用。

## 实践建议

- **description 一句话**，正文尽量精简（贴流程、贴命令，不贴大段论述）。
- **按 agent 职责配技能**：执行 agent 配它干活的；调度/决策 agent 尽量 `skills: []`。
- **大 ctx 需求（长文档/复杂推理）人肉分级**：需要背大段历史时，别塞进小 ctx agent，改走 30B 或云端（见 `model-tiering.md`）。
- 验证技能真实生效：`sessions_send` 问该 agent"你有哪些技能、会怎么执行"，看它是否复述正确。

---

> 这套方法解决了"装技能 = 撑爆小模型 ctx"的经典矛盾，让技能注入服务于业务而非拖累性能。
