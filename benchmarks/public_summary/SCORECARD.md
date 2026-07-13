# 经管论文智检 Skill · 质量摘要（Scorecard）

**当前状态**：🟡 **候选版 v1.7.0-rc.1**（Phase D 完成 · 观察期评审中）

**约束**：本文档表述严格遵守 `benchmarks/policies/PUBLIC_CLAIMS_POLICY.md`。任何数字必须同时给出样本量和 dataset_version；任何“能力”必须同时给出未覆盖场景。黑名单词汇已在生产 CI 断言（具体词条见上述 policy 文件二小节）。

---

## 版本信息

| 项目 | 值 |
|---|---|
| Skill 版本 | v1.7.0-rc.1（候选版，未发正式版） |
| 规则版本 | rules-2026.07 · hash `38425bb2…` |
| 知识库版本 | kb-2026.07 · KB-A hash `2f06c8f5…` |
| 视觉模型 | 火山方舟 doubao-seed-2-0-mini-260428（OpenAI Compatible） |
| Benchmark 数据集 | benchmark-dataset-v0.1 |
| 最近验证日期 | 2026-07-13 |
| 发布验证状态 | 候选版 · 待 Release Gate 观察期通过后升 v1.7.0 |

---

## 覆盖范围（v0.1 数据集）

| 输入类型 | 样本数 | 状态 |
|---|---|---|
| DOCX（本科毕业论文初稿） | 1（S01） | ⏸️ 真身未就位，manifest 占位待更新 |
| 文本型 PDF（本科毕业论文初稿） | 1（S02） | ✅ 端到端跑通 Ark 真调（4 页表格） |
| 扫描型 PDF | 0（S03 待征集） | ❌ 未覆盖 |
| 图表密集论文 | 0（S04 待征集） | ❌ 未覆盖 |
| KB-B 稀疏场景 | 0（S05 待征集） | ❌ 未覆盖 |
| 小型规则夹具 | **10**（R001-R010，35 个 must_hit + forbidden） | ✅ Phase B/C 全绿 |
| 小型 KB-A 查询夹具 | **10**（Q001-Q010） | ✅ 真调检索器全绿 |
| 小型视觉裁剪夹具 | **15**（V001-V015） | 🟡 骨架就绪，V001-V015 真调延后至 Phase F |

---

## 未覆盖场景（明示，不外推）

- ❌ 硕博盲审论文
- ❌ 期刊终稿 / 已发表论文
- ❌ 跨学科（非经管）
- ❌ 非中文母语作者
- ❌ 特殊格式（LaTeX 编译产物、双栏排版、批注文档等）
- ❌ 学位以外的评审场景（内部答辩、投稿评审等）
- ❌ 扫描件 PDF（无文本层，M3 视觉链路对此仅提供辅助识别）

---

## KB-A 检索真调基线（10 Q 样本 · Phase B）

| 指标 | 数值 | 覆盖 |
|---|---|---|
| norm_precision（多样本均值） | 1.0000 | 10/10 白名单内正例 |
| norm_recall（多样本均值） | 1.0000 | 10/10 白名单内正例 |
| empty_when_irrelevant | 成立 | Q008 无关 query 返回 0 命中 |
| 白名单外反常识过滤 | 成立 | Q007 `variable_definition` 拒绝命中 |
| 检索延迟 p50 | ~20-70 ms | 本地 CPU 冷/热启动 |

---

## S02 视觉链路真调基线（PDF 24 页 · Phase C/D · 3 次真调）

| 页 | 表格 | 尺寸 | quality | hard_gates | 延迟均值 |
|---|---|---|---|---|---|
| 17 | 表 1 变量指标体系 | 7×4 | 0.80 | ✅ | ~8 s |
| 18 | 表 2 描述性统计 | 8×6 | 0.80 | ✅ | ~14 s |
| 19 | （无表） | — | 0.00 | ⬇降级正确 | ~3 s |
| 20 | 表 3 主回归 LR→NIM | 16×3 | 0.80 | ✅ | ~28 s |

**Phase D 3 次真调聚合**（run1 51.9s / run2 37.5s / run3 37.9s）：

| 指标 | 数值 |
|---|---|
| performance.total_seconds_p50 | **37.919 s** |
| performance.total_seconds_p95 | **50.458 s** |
| repeat_count | 3 |
| avg tokens/run | 12,067 |
| avg quality_score | 0.80 |
| avg critical_field_score | **1.00** |
| avg regions_recognized | 3/4（p19 正确降级） |
| quality_gate_false_pass_count | **0** |
| visual_false_red_count | **0** |

---

## 反循环闭环验证（Phase C）

用 R001 作 double-blind 演示：

| 场景 | 内核判定 | anchor_recall | forbidden_count | Release Gate |
|---|---|---|---|---|
| pass | 内核正确判 [1] 缺卷号页码 | 1.0 | 0 | 🟩 通过 |
| fail | 内核漏红 [1] + 错红 [3] | 0.0 | 1 | 🟥 阻断 × 2 |

**结论**：fingerprint 抽取器不受运行期 `issue_id / evidence 措辞`扰动；expected 由人工独立写，与内核输出对齐后才算通过。

---

## 关键回归状态

| 检查项 | 状态 |
|---|---|
| 硬门禁字段全 = 0 的样本比例 | 48/48 metrics 全绿 |
| DOCX v1.5.0 sha256 零回归 | ✅ `5bd30276d8f8…` |
| 判断内核（rules/ + agent_instructions/）零改动 | ✅ |
| M1 知识库（kb_query.py / kb_admin.py）零改动 | ✅ |
| M3 视觉链路（vision_pipeline.py）零改动 | ✅ |
| pytest 全绿 | 77/77 |
| self_check.py 5 项 | 5/5 通过 |
| p50 / p95 相对上一版 | ⏳ v1.7.0-rc.1 首个 baseline，Phase F 起做同比 |

---

## 判定原则

> 本 Skill 用于协助教师、导师、学生对经管本科毕业论文初稿进行**格式规范、方法论完整性、参考文献一致性**的智能自检。它**不能代替**任何真人评审。

> 测试结果仅代表在本 Scorecard 声明的样本（dataset_version=benchmark-dataset-v0.1，共 S01/S02 + 35 fixtures）、模型（doubao-seed-2-0-mini-260428）、规则（rules-2026.07）与运行环境下的表现，**不能外推**至未覆盖场景。

> 视觉链路对 PDF 输入的表格/公式/图表提供“辅助识别”；扫描件 PDF 与无文本层 PDF 一律降级为需人工确认。

---

## 变更日志入口

见 `CHANGELOG.md`。M4 Phase A/B/C/D 全部落地记录附相应 commit sha 与 tag。
