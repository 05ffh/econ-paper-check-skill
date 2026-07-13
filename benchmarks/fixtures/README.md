# benchmarks/fixtures/ — M4 三层微型夹具

> **Phase B 交付**：10 规则夹具 + 10 KB 查询夹具 + 15 视觉裁剪夹具

本目录只放**微型合成夹具**，不放真实论文。真实论文样本入 `benchmarks/documents/`。

## 三层夹具

| 层 | 目录 | 前缀 | 首版数量 | 目的 |
|---|---|---|---|---|
| 规则夹具 | `rules/` | `R` | ≥ 10 | 每个 1-3 个目标点，验证 rule_id 命中 + evidence_key 生成 |
| KB 查询夹具 | `kb_queries/` | `Q` | ≥ 10 | 覆盖 KB-A 正例/未命中/跨域拒绝 |
| 视觉裁剪夹具 | `vision_crops/` | `V` | ≥ 15 | 覆盖表格/公式/图表 + quality_gate 边界 |

## 每个夹具目录结构

```
R001_gb7714_journal_completeness/
├── input.md          # 微型输入（学生论文片段，1 KB 以内）
├── expected.yaml     # M4 expected schema (v0.2)
└── NOTES.md          # 该 fixture 的意图 / 反循环记录（可选）
```

## 反循环协议

按 `plans/M4_Benchmark_CHANGELOG_v0.2.md §4.1` 五步：

1. 标注者读规范条款 + 构造 input
2. **独立**写 expected.yaml（不看 Skill 输出）
3. 运行 Skill → 获取 actual
4. 人工裁决差异
5. 记录 `labeled_by / reviewed_by / rationale`

**禁止**：先跑 Skill → 挑锚点 → 写 expected。

## 命名

- `R001_<rule_slug>` — 规则夹具目录（例：`R001_gb7714_journal_completeness`）
- `Q001_<query_slug>` — KB 查询夹具
- `V001_<crop_slug>` — 视觉裁剪夹具

sample_id 正则：`^(S|D|R|Q|V)[0-9]{2,3}(_[A-Za-z0-9_]+)?$`

## 现状（v1.7.0-rc.0-fixtures）

Phase B 首版：10R + 10Q + 15V 目录已建；expected.yaml 分批落地。
