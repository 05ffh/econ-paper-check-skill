# ArkClaw Team-Mode 模板：三 Agent 并行经管论文智检

> 适用场景：想让"论文智检"在 ArkClaw 团队模式下拆成三个专职 sub-agent 并行处理，
> 提升执行确定性与可解释性，也符合 ArkClaw 项目 workflow 演示需求。

## 何时启用

单 agent 直接跑 SKILL.md 的流程已经能完整交付。以下情况建议启用团队模式：

- 学生上传的论文体量较大（> 3 万字），单 agent context 压力大
- 想让判断链路更可审计（每个 sub-agent 输出各自的中间产物）
- 火山杯路演场景想展示 ArkClaw 项目/团队 workflow

## 三 Agent 分工

| Agent | 职责 | 输入 | 输出 |
|---|---|---|---|
| **画像 Agent（profiler）** | 读 paper_text.json，生成 paper_profile 与 trigger_plan | paper_text.json + paper_profile_schema.md + rule_registry.yaml | paper_profile.json |
| **判断 Agent（inspector）** | 按 5 域执行语义判断 + 7 项强制交叉核对 + 6 条硬伤清单 | paper_text.json + paper_profile.json + rules/*.yaml + agent_instructions/*.md | diagnostic_result.json |
| **报告 Agent（reporter）** | 调 render_report.py 与 render_report_html.py 出双版本报告，按渠道投递 | diagnostic_result.json | 报告.docx + 报告.html + 结构化摘要 |

## 依赖顺序（不能并行的部分）

```
profiler → inspector → reporter
```

三者是**顺序依赖**，本质上是拆解而非并行。如果论文很大，可以进一步在 inspector
内部按域并行（5 个 sub-inspector 各负责一个诊断域），最后由 inspector 主 agent 合并。

## 使用 arkclaw-team-project-builder skill 一键组队

对话中直接说：

> 用 arkclaw-team-project-builder 帮我搭一个"经管论文智检"团队项目，包含 profiler / inspector / reporter 三个 agent，按 team_mode.md 分工。

builder skill 会创建项目、组员、任务，profiler 完成后自动派发 inspector，以此类推。

## 团队模式 vs 单 agent 模式选择

| 维度 | 单 agent | 团队模式 |
|---|---|---|
| 上手成本 | ✅ 直接跑 SKILL.md | 需要先建项目 |
| Context 使用 | 单进程累积 | 每个 sub-agent 从零开始，需要在 task 描述中显式传递上下文 |
| 可审计性 | 中间产物在同一 session | 每个 sub-agent 独立产物，更易 review |
| 适用体量 | ≤ 3 万字论文 | > 3 万字或需要展示 workflow 场景 |

默认推荐单 agent 模式；团队模式作为 ArkClaw 生态展示用例保留。
