# M4 Benchmark + CHANGELOG 计划书 v0.2

**起草时间**：2026-07-13 00:02 GMT+8
**版本演进**：v0.1 → v0.2（完整吸收「追加补齐清单」15 个 P0 项 + 8 个 P1 项）
**当前基线**：v1.6.2 · commit `20abcca` · 冻结 tag `v1.6.2-pre-m4-frozen`
**Pre-Build Audit**：`plans/M4_PREBUILD_AUDIT.md` ✅
**目标发布**：**先打 `v1.7.0-rc.1`，通过 Release Gate + 观察期后再发布 `v1.7.0`**

---

## 0. 一句话目标（v0.2 升级版）

**"不仅知道版本变了什么，还能证明：高风险问题没有漏、正确内容没有被误判、证据和规范可复核、视觉数字没有读错、性能与成本可控制、每次发布都有可审计依据。"**

不再是「加一套秤」，而是「建立可信性证据体系」。

---

## 1. v0.1 → v0.2 关键升级摘要

| 维度 | v0.1（弃用） | v0.2（本版） |
|---|---|---|
| 样本结构 | 5 篇完整论文即 Benchmark | **四层**：规则夹具 + KB 查询 + 视觉裁剪 + 完整论文集成 |
| 期望标注 | 只有 anchor_issues（must_hit） | **must_hit + forbidden_issues 双向**；禁止「先跑模型再当真值」 |
| 回归主键 | issue_id (R-01 等) | **issue_fingerprint**（rule_id + type + location + evidence_key） |
| 质量指标 | 红黄绿数量区间 | **正确性指标**：anchor_recall / false_red_count / norm_precision / critical_cell_accuracy 等 20+ 项 |
| 视觉门禁 | regions_recognized/dispatched ≥ 90% | **数值正确性**：exact_match ≥ 95%、负号/小数点 100%、显著性 ≥ 98%、header_binding ≥ 95%、visual_false_red = 0 |
| 样本来源 | CNKI 抓取脱敏 | **禁止默认抓取**；仅授权论文 / 合成夹具 / 开源许可样本 |
| Baseline 保护 | run 直接写 baseline | **runs/ 与 baselines/ 分离，promote_baseline.py 人工审批** |
| CI | 可选 | **离线 CI 必交**；真调 Ark 仅手动运行 |
| 版本策略 | 直接 v1.7.0 | **先 rc.1，通过 Release Gate 再 v1.7.0** |
| CHANGELOG 追认 | 粗粒度即可 | **必须有 commit/tag 证据**，无证据则标"约在 v1.3-v1.4 期间" |
| M4 代码边界 | "不改老代码" | **允许只读、向后兼容的 metrics hook**，但独立 PR + 单测 + 默认行为零变化 |

---

## 2. 边界（Non-Goals）

- ❌ 不改判断内核（rules/ + agent_instructions/ + references/）**业务逻辑**
- ❌ 不改 M1 知识库业务逻辑（kb_query / kb_admin / build_reference_card）
- ❌ 不改 M3 视觉业务逻辑（vision_pipeline / providers / dispatcher）
- ❌ 不做 M5（对话式 + 批量）、M2（前端 UI）
- ❌ **不做真实性/查重/OCR 补齐**（Skill 边界）
- ❌ **不默认抓取 CNKI 或任何公开论文库**
- ✅ **允许**：新增只读 metrics hook / 结构化 result object 返回（独立 PR + 单测 + 默认零变化）

---

## 3. 四层 Benchmark 数据集设计

### 3.1 目录结构

```
benchmarks/
├── README.md
├── VERSION                          # dataset_version=benchmark-dataset-v0.1
├── env/lock.txt                     # pip freeze + dependency_lock_hash
├── fixtures/
│   ├── rules/                       # 微型规则夹具 ≥ 10
│   ├── kb_queries/                  # KB 检索夹具 ≥ 10
│   └── vision_crops/                # 视觉裁剪夹具 ≥ 15
├── documents/
│   ├── public_synthetic/            # 合成/半合成论文（可公开）
│   ├── private_local_manifest/      # 私有真实论文（只入 manifest+hash）
│   └── open_license/                # 明确开放许可样本
├── expected/                        # 每样本 expected.yaml
├── schema/
│   ├── metrics.schema.yaml
│   ├── expected.schema.yaml
│   └── sample_manifest.schema.yaml
├── runs/                            # 候选运行（可覆盖）
│   └── {run_id}/
├── baselines/                       # 黄金基线（只读）
│   └── v1.7.0-rc.1/APPROVAL.yaml
├── reports/
│   ├── latest_scorecard.md
│   └── latest_scorecard.html
├── lib/fingerprint.py
└── runners/
    ├── run_single.py                # 只写 runs/
    ├── run_all.py
    ├── compare_run.py               # candidate vs baseline
    ├── promote_baseline.py          # 需 --approved-by
    ├── coverage_report.py
    └── generate_scorecard.py
```

### 3.2 首版数量下限（DoD）

| 层 | 首版下限 | 备注 |
|---|---|---|
| 规则夹具 | ≥ 10 | 每个 1-3 个目标点 |
| KB 查询夹具 | ≥ 10 | 覆盖正例/误挂/空结果 |
| 视觉裁剪夹具 | ≥ 15 | 含清晰表、模糊表、易错符号、应降灰的不可读区域 |
| 完整文档 | ≥ 2（S01+S02） | 张弘济 DOCX + PDF |
| 其他文档 | 有则加、无则以合成夹具补齐 | 不阻塞首版 |

---

## 4. Ground Truth 标注协议

### 4.1 反循环流程（P0-3）

```
Step 1  标注者读论文/夹具 + 适用规范
Step 2  独立写出预期 issue（不看 Skill 输出）
Step 3  运行 Skill → 得到 actual
Step 4  人工裁决 expected vs actual 的差异
Step 5  记录：labeled_by / reviewed_by / rationale / decision
```

**禁止**：先跑 Skill → 挑锚点 → 写 expected。

### 4.2 双向锚点

- **must_hit**：必须命中的高置信问题
- **forbidden_issues**：不得出现的问题（控制假阳性 / 假红）

### 4.3 复核层级

| 严重度 | 要求 |
|---|---|
| Red | 两人独立复核，或"用户 + ArkClaw + 人工裁决" |
| Yellow / Gray | 单人可标注，注 confidence 高/中/低 |
| 争议 | 仅入观察指标，不入硬门禁 |

---

## 5. 稳定 Issue Fingerprint（P0-4）

### 5.1 定义

```
issue_fingerprint = 
    rule_id + "|" + normalized_issue_type 
    + "|" + normalized_location_anchor 
    + "|" + normalized_evidence_key
```

**示例**：
```
gb7714_2015_journal_completeness|citation|reference_12|missing_volume_pages
wooldridge_did_parallel_trends|methods|section_4_2|missing_parallel_test
```

### 5.2 归一化规则

| 字段 | 归一化 |
|---|---|
| `rule_id` | KB-A norm_id 或内置 rule_id |
| `issue_type` | 小写+下划线，只允许 citation/methods/writing/figures_tables/summary |
| `location_anchor` | 稳定位置词：`reference_N` / `section_N_M` / `table_N` / `equation_N`；**不用页码** |
| `evidence_key` | 结构化标签：`missing_volume_pages` / `sign_error` / `numeric_mismatch`，**不用原文措辞** |

### 5.3 使用规则

- `issue_id` 仅报告展示用
- `issue_fingerprint` 才是 Benchmark 主键
- 顺序变化 → EXPECTED_VARIANCE，不失败
- 页码偏移 → 允许 `tolerance: 1`
- 重复 fingerprint → 单独统计 `duplicate_issue_rate`

---

## 6. 质量指标全景（P0-5 + P0-6）

### 6.1 判断质量

| 字段 | 定义 |
|---|---|
| `anchor_recall` | must_hit 命中率 |
| `forbidden_issue_count` | 命中 forbidden 数（应 = 0） |
| `false_red_count` | 人工确认错误红色数（应 = 0） |
| `severity_match_rate` | 严重程度一致率 |
| `location_hit_rate` | 定位命中率（允许容差） |
| `evidence_completeness_rate` | 证据/原因/建议/规范依据完整率（红色应 = 100%） |
| `duplicate_issue_rate` | 重复 fingerprint 比例 |
| `repeatability_rate` | 重复 3 次运行 anchor 稳定率 |

### 6.2 KB-A 质量

| 字段 | 定义 |
|---|---|
| `norm_precision` | 挂载规范正确率 |
| `norm_recall` | 需规范的问题挂载覆盖率 |
| `irrelevant_norm_rate` | 误挂率 |
| `unsupported_red_count` | 红色问题无规范依据数（应 = 0） |

### 6.3 KB-B 质量

| 字段 | 定义 |
|---|---|
| `precision_at_k` | 前 k 卡相关率 |
| `empty_when_irrelevant_rate` | 无适用范例时能否不强推 |
| `duplicate_card_rate` | 重复卡片比例 |

### 6.4 视觉质量（严格对齐 M3 轻量化）

**首版硬门禁只覆盖 OCR_REGION + TABLE_STRUCTURE**：

| 字段 | 阈值 |
|---|---|
| `region_detection_recall` | ≥ 0.9 |
| `critical_cell_accuracy` | ≥ 0.95 |
| `numeric_exact_match` | ≥ 0.95 |
| `sign_accuracy` | = 1.0 |
| `significance_marker_accuracy` | ≥ 0.98 |
| `header_binding_accuracy` | ≥ 0.95 |
| `quality_gate_false_pass_count` | = 0 |
| `visual_false_red_count` | = 0 |

**规则**：
- 「返回了内容」≠「识别正确」，返回率退出主门禁
- 无视觉配置时，文本质检流程不得失败
- 首版校准后阈值可微调

### 6.5 性能

| 字段 | 首版建议 |
|---|---|
| `p50_total_seconds`, `p95_total_seconds` | 至少重复 3 次采样 |
| 分阶段耗时 | parse / judgment / kb / vision / render |
| `tokens_total_p50` | 视觉真调场景 |
| `estimated_cost_cny_p50` | 按 Ark 定价估算 |
| `peak_rss_mb` | 峰值内存 |
| 阈值 | p95 ≤ 20%（黄灯）/ ≤ 35%（阻止发布） |

### 6.6 计数规范化

- `issues`: 仅 red/yellow/gray
- `passed_checks`: 独立放"绿色通过项"
- **不再混合**

---

## 7. 复现元数据（P0-9）

`metrics.json` 必录：

```yaml
reproducibility:
  python_version: "3.12.3"
  os: "Linux 6.8.0-55-generic (x64)"
  architecture: "x86_64"
  dependency_lock_hash: <sha256 of benchmarks/env/lock.txt>
  model_provider: "ark" | null
  model_id: "doubao-seed-2-0-mini-260428" | null
  model_endpoint_id: str | null
  model_config_hash: str | null
  temperature: 0.0
  seed: int | null
  prompt_template_hash: str        # _SYSTEM_PROMPT_STRICT sha256
  rules_hash: "38425bb2..."
  agent_instructions_hash: str
  kb_a_snapshot_hash: "2f06c8f5..."
  kb_b_snapshot_hash: str
  vision_schema_hash: "17b3d10d..."
  report_template_hash: str
  cache_used: bool
  run_kind: mock_ci | real_manual | performance
```

---

## 8. Baseline 保护（P0-8）

### 8.1 目录分离

- `runs/{run_id}/` — 候选（可覆盖）
- `baselines/{baseline_id}/` — 黄金基线（**只读**）

### 8.2 晋升流程

```bash
python benchmarks/runners/run_all.py --run-id 20260713-phaseB
python benchmarks/runners/compare_run.py \
    --candidate benchmarks/runs/20260713-phaseB \
    --baseline benchmarks/baselines/v1.7.0-rc.1
# 审阅 diff_report.json（分类见 §10.3）
python benchmarks/runners/promote_baseline.py \
    --from benchmarks/runs/20260713-phaseB \
    --to v1.7.0-rc.1 \
    --approved-by "user_name" \
    --change-reason "首版 baseline 落定"
```

### 8.3 只读保护

- promote 脚本写完 chmod 444
- 已发布 baseline 更新必须写 `change_reason` + 触发 CHANGELOG

---

## 9. CI 分层（P0-12）

### 9.1 必进 CI（PR 门禁）

- pytest 全套
- 规则夹具 / KB 查询夹具 / M3 Mock 视觉夹具
- S01 或合成小文档冒烟
- Schema 校验 / CHANGELOG 格式 / 密钥扫描
- runs/ 输出字段完整性

### 9.2 手动 / 计划任务

- 完整 S01/S02 端到端
- 真调 Ark（需 secrets.ARK_API_KEY，仅 push/main 分支）
- 私有论文样本
- 性能与成本测试（重复 3 次）

### 9.3 CI 安全

- PR 分支不读 ARK_API_KEY
- 私有论文永不上 Git/CI artifact
- Mock fixture 必须脱敏
- artifact 上传前扫敏感串

---

## 10. Release Gate（P0-14）

### 10.1 硬阻止

- 新增 forbidden_issue 命中
- `false_red_count > 0`
- 任一高置信红色 anchor 丢失
- 红色 `evidence_completeness_rate < 1.0`
- 红色缺规范/方法学依据
- `visual_false_red_count > 0`
- 低质量视觉被质量门禁错误放行
- DOCX 基础流程失败
- API Key / 私有论文进入 Git / CI artifact
- baseline 未经审批被覆盖
- CHANGELOG / 版本 / tag 不一致

### 10.2 黄灯（需人工确认）

- 黄色问题数明显波动
- KB-B 推荐卡变化
- p95 恶化 20%-35%
- 模型措辞变化但 fingerprint 不变
- 新增正确问题（决定是否晋升 baseline）

### 10.3 差异分类

- `REGRESSION` / `INTENDED_IMPROVEMENT` / `EXPECTED_VARIANCE` / `DATASET_CHANGE` / `ENVIRONMENT_CHANGE` / `NEEDS_REVIEW`

### 10.4 自动通过

- issue 排序变化
- 生成时间变化
- 文案轻微改写
- artifact 二进制变但 canonical result 不变

---

## 11. 版本策略（P0-14 + P0-15）

```
v1.6.2 (当前) 
    → v1.6.2-pre-m4-frozen ✅（已打）
    → v1.7.0-rc.1（Phase E 首打）
    → 观察期 + Release Gate
    → v1.7.0（正式）
```

### 11.1 CHANGELOG 追认规范

- 只写 tag/commit/历史文件可证明的
- 不确定边界 → "约在 v1.3-v1.4 期间"
- 顶部保留 `[Unreleased]`
- 栏目：Added / Changed / Fixed / Removed / Security
- 每个面向用户的变更必须入 CHANGELOG
- 版本号 == arkclaw.yaml == tag == release notes

### 11.2 追认模板

```markdown
## [1.4.0] - Retrospective
> 本节为 2026-07-xx 根据 Git 历史追认的里程碑摘要，不代表完整变更记录。

### Added
- KB-B 范例层上线（证据：commit 88e6644, tag v1.4.0-kb-b）
```

---

## 12. 分阶段实施路线

**总时间预估：3-4 个工作日**

### Phase 0 · 审计与冻结 ✅

- ✅ `plans/M4_PREBUILD_AUDIT.md`
- ✅ 冻结 tag `v1.6.2-pre-m4-frozen`
- ⚠️ S01/S02 授权 manifest 待用户签署（阻塞 Phase C）

### Phase A · 契约与数据治理（0.75 天）

- A.1 建立 `benchmarks/` 目录 + README + VERSION
- A.2 3 份 schema：metrics / expected / sample_manifest
- A.3 fingerprint 归一化模块（`benchmarks/lib/fingerprint.py`）
- A.4 `benchmarks/env/lock.txt` + dependency_lock_hash
- A.5 baseline promotion policy + approval schema

### Phase B · 离线小型 Benchmark（1 天）

- B.1 10 个规则夹具
- B.2 10 个 KB 查询夹具
- B.3 15 个视觉裁剪夹具
- B.4 `run_single.py`（只写 runs/）
- B.5 `compare_run.py`（fingerprint 集合 diff + 分类）
- B.6 `coverage_report.py`
- B.7 CI：`.github/workflows/benchmark-offline.yml`

### Phase C · 完整文档集成（0.5 天，需授权）

- C.1 S01/S02 sample_manifest.yaml（用户签署）
- C.2 S01 DOCX + expected 双向标注
- C.3 S02 PDF + 视觉真调（需 Key）
- C.4 D01 合成经管论文样本
- C.5 视觉裁剪抽样真跑

### Phase D · 真实 Ark 与性能（0.5 天）

- D.1 关键样本 3 次重复采样
- D.2 p50/p95 报告
- D.3 tokens / cost 估算
- D.4 视觉真值对比

### Phase E · CHANGELOG 与候选发布（0.5 天）

- E.1 CHANGELOG 历史追认（v1.0-v1.4，仅 commit/tag 证据）
- E.2 `docs/VERSIONING_POLICY.md`
- E.3 `docs/CHANGELOG_POLICY.md`
- E.4 Release Gate 自动化脚本
- E.5 打 tag `v1.7.0-rc.1` → push → release
- E.6 生成 Benchmark Scorecard（`benchmarks/reports/latest_scorecard.md/.html`）

---

## 13. 与其他 M 的接口（P1-8）

### 13.1 M4 → M5（只提供稳定接口）

M4 只暴露给 M5：
- result schema
- progress schema
- failure taxonomy
- artifact manifest
- 只读评测适配器

M5 **不得**直接调用：
- baseline promotion
- expected 对比
- 私有 benchmark 样本目录

### 13.2 M4 内部只读 hook 边界

允许（独立 PR + 单测 + 默认零变化）：
- 判断流程返回结构化 result object
- KB 查询暴露命中 metadata
- M3 返回 provider usage / 质量门禁结果
- 可选 `metrics_collector`

禁止：
- 为让 Benchmark 通过而改判级
- 改阈值不记录
- 对样本写死特殊逻辑
- 生产代码识别 sample_id 后走不同分支

---

## 14. 风险与规避

| 风险 | 规避 |
|---|---|
| S01/S02 授权未及时到位 | Phase A/B 无依赖，可先跑；Phase C 可以合成样本 D01 补齐 |
| 视觉真调成本失控 | 单样本 20000 tokens 硬拦截；日常回归走 Mock；成本估算入 metrics |
| 期望标注人工偏差 | 反循环流程 + 双向锚点 + 复核层级 |
| baseline 误覆盖 | 目录分离 + promote 需 --approved-by + 只读保护 |
| CHANGELOG 追认失真 | 无证据不写；模糊边界标"约在..." |
| 模型漂移 | reproducibility 记录 model_id + endpoint + config_hash |

---

## 15. 首版 Definition of Done（对齐追加补齐清单 §九）

- [ ] Pre-Build Audit 已生成并审阅 ✅
- [ ] Benchmark 覆盖规则/KB/视觉/完整文档四层
- [ ] 样本有 manifest / 授权 / 脱敏状态
- [ ] 私有真实论文不进入 Git
- [ ] expected 同时含 must_hit + forbidden_issues
- [ ] 使用 issue_fingerprint（非 R-01）
- [ ] runner 输出 runs/，不直接覆盖 baseline
- [ ] baseline 晋升需人工审批
- [ ] metrics 含正确性/证据/KB/视觉/性能/复现
- [ ] 视觉指标衡量数值/结构正确性，非返回率
- [ ] DOCX/PDF 用可比子集 + allowed_differences
- [ ] 至少一个合格样本验证假阳性
- [ ] false red 为硬门禁
- [ ] 离线 CI 已落地
- [ ] 真调 Ark 与 Mock CI 明确分离
- [ ] 私有资产不入 CI artifact
- [ ] 性能测试至少重复 3 次报告 p50/p95
- [ ] canonical result 可复现可 diff
- [ ] CHANGELOG 历史追认均有 commit/tag 证据
- [ ] `[Unreleased]` / 版本号 / tag / release notes 一致
- [ ] M4 首发 rc.1 → 通过 Release Gate 后再 v1.7.0
- [ ] Benchmark Scorecard 生成

---

## 16. P1 增强项（首版一并落地）

### P1-1 假阳性控制
- 每层 benchmark 至少 1 个「合格样本」/「合格片段」
- S05 若征集，选择经管领域内 KB-B 稀疏主题（金融科技/审计/公司治理/营销/产业经济），而非古典哲学/艺术史

### P1-2 DOCX/PDF 一致性 · 可比子集

```yaml
parity_expectation:
  must_match_fingerprints:
    - citation|ref_12|missing_pages
  allowed_pdf_only:
    - visual_review_required|table_3
  allowed_docx_only:
    - native_table_structure|table_3
```

### P1-3 diff 分类

compare_run.py 输出必须包含以下六类之一：
- REGRESSION / INTENDED_IMPROVEMENT / EXPECTED_VARIANCE
- DATASET_CHANGE / ENVIRONMENT_CHANGE / NEEDS_REVIEW

baseline 更新必须回答 6 问：为何变 / 是否正确 / 谁批准 / 变了什么 / 是否入 CHANGELOG / 是否影响版本号。

### P1-4 非确定性策略
- 尽可能低温度
- 支持 seed 时记录 seed
- 核心样本重复 3 次
- 高置信 anchor 需 3/3 命中
- 争议黄色 2/3 命中即可
- 重复运行出现一次 false red → 阻止发布

### P1-5 Scorecard 内容

```
Benchmark Scorecard v1.7.0-rc.1
- 高置信问题召回率：X%
- 错误红色问题数：0
- 证据完整率：100%
- KB-A 挂载准确率：X%
- 图片表格关键数字准确率：X%
- DOCX/PDF 可比锚点一致率：X%
- 平均耗时 / p95：X / Y 秒
- 单篇估算成本：¥X
- 未覆盖内容比例：X%
```

输出：`benchmarks/reports/latest_scorecard.md` + `.html`

### P1-6 失败可定位产物

每次 failed run 保留：
- 输入 manifest
- canonical_result.json
- expected diff
- 实际 fingerprint
- 缺失/新增问题
- 规范挂载 diff
- 视觉裁剪结构化输出
- provider 错误类型
- 无密钥无敏感正文的日志

`run_single.py` 支持 `--explain-failures`

### P1-7 数据集版本号

```
benchmarks/VERSION: benchmark-dataset-v0.1
```

变更需记录：新增/删除样本 / expected 修订 / 脱敏修订 / 许可变化 / 真值裁决变化。

**跨 dataset 版本的 Skill 结果不能直接比对。**

### P1-8 M4↔M5 接口

见 §13。

---

## 17. 决策回复（v0.1 Q1-Q4 的 v0.2 版）

1. **样本来源**：**A + C 为主**。真实论文必须获授权并本地保存；用合成/半合成夹具补齐规则覆盖。**不默认抓取 CNKI 全文。**
2. **Ark 策略**：**真实 Baseline / 手动验收真调；日常 CI 使用脱敏 Mock**。两种严格分离。
3. **CHANGELOG**：**粗粒度追认**，但每项必须有 commit/tag/历史文件证据，不确定不猜。
4. **版本策略**：**先 `v1.7.0-rc.1`，通过 Release Gate + 短观察期后再 `v1.7.0`。**

---

## 18. 配套文档索引（本次一并交付）

| 文档 | 内容 |
|---|---|
| `plans/M4_Benchmark_CHANGELOG_v0.2.md` | 本文 |
| `plans/M4_PREBUILD_AUDIT.md` | Pre-Build 审计 ✅ |
| `plans/M4_METRICS_SCHEMA_v0.2.yaml` | metrics.schema 草案 |
| `plans/M4_EXPECTED_SCHEMA_v0.2.yaml` | expected.schema 草案 |
| `plans/M4_SAMPLE_GOVERNANCE.md` | 样本治理规范 |
| `plans/M4_RELEASE_GATE.md` | Release Gate 门禁清单 |

---

**下一步**：等用户对本 v0.2 + 5 份配套文档给出「进入 Phase A」批准 → 建 `benchmarks/` 骨架 + 3 份 schema + fingerprint 模块 → 冒烟。
