# M4 · Benchmark + CHANGELOG 计划书 v0.1

**起草时间**：2026-07-12 23:35 GMT+8
**作者**：ArkClaw（与用户共同起草）
**当前基线**：v1.6.2（commit 20abcca）· 已 push · pytest 29/29 · doctor 4 组全绿
**上游依赖**：M1（KB-A/KB-B 双层）✅ · M3（PDF 视觉辅助识别）✅
**下游影响**：M5（对话式 + 批量）需要 M4 的 benchmark 集合与判级基线做回归

---

## 0. 一句话目标

**"让每一次改动都能被量化回答两个问题：判得对不对？出得快不快？"**

M4 的产物 = **一份可回归的样本集 + 一套自动化跑分脚本 + 一份从 v1.0 起完整的 CHANGELOG**。

---

## 1. 背景与动机

M1（知识库）和 M3（视觉）之后，Skill 已具备**判断内核 + KB-A 规范挂载 + KB-B 参照卡 + PDF 视觉辅助识别**四大能力，但目前的验证只在**单个论文（张弘济初稿）**上完成。存在四个具体风险：

| # | 风险 | 具体表现 |
|---|---|---|
| R1 | **判级抖动无法察觉** | 同一篇论文，改一次 rules/ 或 KB-A 后，红黄绿数量、issue_id 命中集是否变了？现在只能人工肉眼比对 |
| R2 | **视觉能力真实召回率未知** | 张弘济 p20 表 3 是唯一验证过的样本，其他类型的表（异方差表、Hausman 表、DID 交互项表）、图（散点、系数图、机制图）、公式截图完全没跑过 |
| R3 | **KB-A 命中偏差不可见** | 18 条规范里，哪些高频命中、哪些从未命中、哪些误挂到无关 issue？没数据 |
| R4 | **性能没有基线** | 一份 24 页 DOCX/PDF 端到端需要多少秒、多少 token、多少钱？没有数字，用户体验决策无据 |

**M4 的核心是把这四条黑箱变成白箱**，不是"再加新功能"。判断内核仍然禁改，M1/M3 代码仍然禁改。

---

## 2. 边界与非目标（Non-Goals）

以下不在 M4 范围，明确列出以防范围蔓延：

- ❌ **不做新规则**：KB-A writing/summary/figures_tables 三域仍空置，等学校模板
- ❌ **不改判断内核**：rules/、agent_instructions/、references/ 一行不动
- ❌ **不改 M1 知识库代码**：kb_query.py、kb_admin.py、build_reference_card.py 一行不动
- ❌ **不改 M3 视觉链路核心**：vision_pipeline.py、providers/ark_provider.py 一行不动
- ❌ **不做 M5（对话式 + 批量）**：批量跑分脚本≠批量交付产品，两码事
- ❌ **不做 M2（前端 UI）**：M2 放最后
- ❌ **不做真实性/查重/OCR 补齐**：仍走 Skill 边界

M4 只加**新脚本 + 新数据 + 新文档**，不改老代码。

---

## 3. 交付物清单（Deliverables）

### 3.1 Benchmark 层（新增，位于 `benchmarks/` 目录）

```
benchmarks/
├── README.md                          # 使用说明 · 样本清单 · 指标定义
├── samples/                           # 论文样本（脱敏后）
│   ├── S01_zhc_docx/                  # 张弘济 DOCX 版本（现有基线）
│   ├── S02_zhc_pdf/                   # 张弘济 PDF 版本（现有）
│   ├── S03_scan_only_pdf/             # 纯扫描档 PDF（新收集）
│   ├── S04_chart_heavy/               # 图表密集论文（新收集）
│   └── S05_kb_sparse/                 # KB-B 主题命中稀疏样本（新收集）
├── expected/                          # 每份样本的期望判级
│   ├── S01.expected.yaml              # 人工标注的红/黄/绿 issue_id 清单
│   └── ...
├── runners/
│   ├── run_single.py                  # 单样本跑分：输出 metrics.json
│   ├── run_all.py                     # 批量跑分：输出 summary.json + summary.md
│   ├── diff_baselines.py              # 两次跑分对比：判级 diff / 性能 diff / KB-A 挂载 diff
│   └── coverage_report.py             # KB-A 18 条命中覆盖率 · 未命中/误挂条款清单
├── baselines/
│   ├── v1.6.2/                        # 首次基线快照（本次 M4 落地）
│   │   ├── S01.metrics.json
│   │   ├── ...
│   │   └── summary.md
│   └── README.md                      # 基线管理规范：何时打新基线、如何回滚
└── metrics_schema.yaml                # 指标字段定义（下节详列）
```

### 3.2 CHANGELOG 层（补齐）

```
CHANGELOG.md    # 已存在（从 v1.5.0 起），M4 补齐 v1.0-v1.4 的追认段落
```

- 补齐 v1.0 / v1.1 / v1.2 / v1.3 / v1.4 五个历史版本的**变更摘要 + 关键 commit 哈希**
- **不追认 v1.5 之前的详细 diff**（工作量不可控），只写"里程碑级"变更
- 新增 "v1.6.2 → v1.7.0（M4）" 段（本次落地时补写）

### 3.3 文档层

```
plans/M4_Benchmark_CHANGELOG_v0.1.md   # 本文件
plans/M4_metrics_definitions.md        # 指标定义详细版（如需要）
docs/BENCHMARK.md                      # 用户面向：如何跑 benchmark、如何解读结果
docs/CHANGELOG_POLICY.md               # 团队规范：改动落到 CHANGELOG 的最小要求
```

### 3.4 CI/自动化（可选，视时间）

- `scripts/preflight_extended.sh`：在原 preflight 基础上加 `benchmarks/runners/run_single.py S01` 的冒烟
- `.github/workflows/benchmark.yml`：手动触发的 workflow_dispatch，跑 S01 + S02 冒烟并输出 summary（**不做真实 Ark 调用**，Mock 模式）

---

## 4. 样本集设计（关键决策点）

### 4.1 样本容量

**v1.7.0 首版：5 个样本足矣，不追求 20+**。理由：
- 判级本身是 AI 主观 + 规则驱动，样本多≠信息多
- 每个样本要人工标注 expected 判级，成本非线性
- 5 个样本已覆盖：DOCX/PDF、扫描/图文、图表密集/稀疏、KB 命中丰富/稀疏

### 4.2 样本类型分层

| ID | 类型 | 用途 | 数据来源 | 处理 |
|---|---|---|---|---|
| **S01** | DOCX 完整论文 | 判断内核基线回归 | 张弘济初稿（现有） | 已入库 |
| **S02** | PDF 完整论文（同 S01 内容） | DOCX↔PDF 一致性验证 | 张弘济 PDF（现有） | 已入库 |
| **S03** | 纯扫描档 PDF | 视觉降级路径验证 | 新征集或从公开来源脱敏 | **需征集** |
| **S04** | 图表密集论文 | 视觉召回率验证（多种表/图/公式） | 新征集 | **需征集** |
| **S05** | 冷门主题论文 | KB-B 命中稀疏路径验证 | 新征集（如古典哲学、艺术史相关经管交叉） | **需征集** |

### 4.3 样本征集与脱敏红线（沿用 M1 KB-B 规范）

- 学生姓名/学校/学号：全部脱敏为 `AUTHOR_S03` / `SCHOOL_S03` 等
- 论文题目：**保留**（沿用 Q-C）
- 参考文献作者名：**保留**（沿用 Q-A）
- 附录中的原始数据表（如包含地区代码、公司代码）：抽样保留，删除敏感字段
- **纯扫描档单独走 upload_policy** 验证，图片本身**不入 Git**，只入 `.workdir/`

### 4.4 期望判级（expected.yaml）如何标注

每份样本产出一次"参考跑分"，然后人工挑出**关键锚点 issue**（不是每一个 issue 都锚定，那太脆弱），格式：

```yaml
sample_id: S01
paper_title: "LR对NIM的影响：来自..."
labeled_by: "user + arkclaw joint review"
labeled_at: 2026-07-13

anchor_issues:  # 稳定锚点，回归时必须命中
  - id: R-01
    category: red
    hint: "参考文献缺卷号页码 · gb7714_2015_journal_completeness"
    must_have_normative_basis: true
  - id: R-04
    category: red
    hint: "DID 未做平行趋势 · wooldridge_did_parallel_trends"
  # ...

count_expectations:  # 数量区间，不做精确等值
  red_min: 3
  red_max: 8
  yellow_min: 5
  yellow_max: 12
  green_min: 3
  green_max: 8
  gray_min: 0
  gray_max: 6

kb_a_coverage:
  must_hit:
    - gb7714_2015_journal_completeness
    - wooldridge_did_parallel_trends
  may_hit:  # 允许命中但不强制
    - wooldridge_ols_assumptions

vision_coverage:  # 仅 S02/S03/S04
  min_regions_recognized: 1
  must_have_table_id: ["表3"]

performance:  # 性能区间，只做上限约束
  total_seconds_max: 90
  ark_tokens_max: 20000
```

**约束**：anchor_issues 必须命中；count/性能/kb 走区间；vision 走"至少识别几个"下限。回归失败 = 锚点丢失或性能超标。

---

## 5. 指标定义（metrics_schema.yaml）

单次跑分产出的 metrics.json 字段：

```yaml
run_metadata:
  sample_id: str
  skill_version: str        # arkclaw.yaml.version
  commit_sha: str
  ran_at: iso8601
  ark_provider_used: bool   # 是否真调 Ark（vs Mock）

paper_summary:
  paper_type: docx|pdf|scan_pdf
  page_count: int
  word_count: int

judgment_counts:
  red: int
  yellow: int
  green: int
  gray: int
  total: int
  by_issue_type:            # writing/citation/methods/figures_tables/summary
    citation: int
    methods: int
    # ...

judgment_ids:               # 所有 issue_id 有序列表，用于 diff
  - R-01
  - R-04
  # ...

kb_a_hits:
  count: int
  distinct_norms: [str]     # 命中过的 norm_id 集合
  by_issue:
    R-01: [gb7714_2015_journal_completeness]
    R-04: [wooldridge_did_parallel_trends]

kb_b_cards:
  count: int
  avg_similarity: float

vision:
  used: bool
  regions_dispatched: int
  regions_recognized: int
  pages_touched: [int]
  seconds_total: float
  tokens_total: int
  provider_calls: int
  failures: int
  full_page_uploads_rejected: int

performance:
  total_seconds: float
  parse_seconds: float
  judgment_seconds: float
  kb_bridge_seconds: float
  vision_seconds: float
  render_seconds: float
  peak_rss_mb: float | null

artifacts:
  docx_sha256: str
  html_sha256: str
```

### 5.1 关键指标一览

| 指标 | 用途 | 阈值/来源 |
|---|---|---|
| `docx_sha256` | 判断内核回归 | 与 baseline 比对，允许 diff 但需人工确认 |
| `judgment_ids` | 判级稳定性 | anchor_issues 必须为子集 |
| `judgment_counts.red` | 数量区间 | expected.count_expectations |
| `kb_a_hits.distinct_norms` | KB-A 覆盖率 | 汇总所有样本 → 未命中条款清单 |
| `kb_b_cards.count` | KB-B 挂载数 | 与 CARD_MIN_SIMILARITY=0.45 相关 |
| `vision.regions_recognized / dispatched` | 视觉召回率 | ≥ 90% |
| `performance.total_seconds` | 端到端耗时 | 有 PDF 视觉 ≤ 120s；纯 DOCX ≤ 30s |

---

## 6. 分阶段实施路线

**总时间预估：2-3 个工作日**（不含用户征集样本的自然等待）

### Phase A · 骨架搭建（0.5 天）

**目标**：目录结构、runner 框架、指标契约就绪，先跑通 S01。

- A.1 建立 `benchmarks/` 目录 + README.md 骨架
- A.2 定义 `metrics_schema.yaml` 与 `expected.yaml` schema
- A.3 编写 `runners/run_single.py`：
  - 输入：sample_id
  - 输出：`baselines/{version}/{sample_id}.metrics.json`
  - 内部调用 `parse_paper.py` + Skill 判断流 + `render_report.py`
  - 计时器采样每一步
- A.4 编写 `runners/coverage_report.py`：汇总 KB-A/KB-B 命中情况
- A.5 编写 `runners/diff_baselines.py`：两次 metrics.json 的关键字段 diff
- A.6 冒烟：`python runners/run_single.py S01` 跑通，落 metrics.json

### Phase B · 首个基线（0.5 天）

**目标**：S01 + S02 完整基线锁定为 v1.6.2 baseline。

- B.1 手工审阅 S01 现有 diagnostic report，抽取 anchor_issues
- B.2 写 `expected/S01.expected.yaml`
- B.3 同样处理 S02（PDF 版本）
- B.4 跑 `run_all.py` → 生成 `baselines/v1.6.2/summary.md`
- B.5 用 `diff_baselines.py` 对 S01↔S02 做一致性检查（应仅有视觉证据差异）

### Phase C · 新样本征集与录入（0.5–1 天，视用户征集速度）

**目标**：S03/S04/S05 入库，跑通并锁基线。

- C.1 用户征集 3 篇论文（可平行）
- C.2 脱敏处理（沿用 M1 KB-B 脱敏规范）
- C.3 人工标注 expected.yaml
- C.4 跑 `run_all.py` → 更新 baseline
- C.5 视觉专项验证 S04：`vision.regions_recognized / dispatched >= 0.9`

### Phase D · CHANGELOG 补齐（0.25 天）

**目标**：CHANGELOG.md 从 v1.0 起有连续记录。

- D.1 `git log --oneline v1.0..v1.4` 摘要出五个里程碑段
- D.2 追认段落写在 CHANGELOG.md 顶部"追认摘要"栏目
- D.3 v1.6.2 → v1.7.0 段落定稿（含 benchmark、CHANGELOG 补齐、新样本）
- D.4 新增 `docs/CHANGELOG_POLICY.md`：以后每次 commit 必须提及是否影响 CHANGELOG

### Phase E · 收尾与打 tag（0.25 天）

**目标**：v1.7.0 打 tag，push，release notes 落地。

- E.1 pytest 29/29 + 新增 benchmark 自测（若时间允许）
- E.2 doctor.py 加一组"benchmark 就绪度"检查（可选）
- E.3 arkclaw.yaml 版本号 1.6.2 → 1.7.0
- E.4 CHANGELOG.md 首块换成 v1.7.0
- E.5 commit + tag v1.7.0 + push + release
- E.6 memory/2026-07-13.md 落地 M4 收尾摘要

---

## 7. 关键决策点（需用户确认）

M4 起跑前，请用户回答四个问题：

### Q1：S03/S04/S05 三份新样本从哪来？

三个来源，用户任选：
- **A. 用户手上有**：直接给 PDF/DOCX，Skill 自动脱敏
- **B. 使用公开来源**：CNKI 硕博论文库、CORE.ac.uk 等开源经管论文，Skill 抓取脱敏
- **C. 生成型样本**：ArkClaw 用张弘济为模板，改题目/改数据/合成图表，做"半合成样本"

> **建议**：A（现有真实论文）优先；A 不够时以 C 补齐（合成可控性最好）。

### Q2：Benchmark 里跑视觉的时候，是否真调 Ark？

- **真调**：数据最真实，但每次 M4 跑分要花约 $0.05–0.15、8-20 分钟
- **Mock**：CI/日常回归 0 成本 0 秒，但需要预先录制 fixture

> **建议**：Baseline 用真调（一次性成本可控），日常 CI 用 Mock。metrics.json 里的 `ark_provider_used` 字段就是为了区分这两类。

### Q3：CHANGELOG 追认 v1.0-v1.4 用什么颗粒度？

- **粗粒度**（推荐）：每版本一段，写"里程碑变更 + 关键 commit"，约 100-200 字/版本
- **细粒度**：每版本按 Added/Changed/Fixed 拆开，重看 commit
- **只写 v1.5 及以后**（现状）

> **建议**：粗粒度追认，节省时间又满足审计需求。

### Q4：M4 交付后立刻打 v1.7.0，还是留一段观察期？

- **立刻打**：M4 = v1.7.0，直接 release
- **观察期**：M4 落到 v1.6.3-rc，跑一段时间稳定后升 v1.7.0

> **建议**：立刻打。M4 是"加脚手架"而非"改内核"，风险极低。

---

## 8. 风险与规避

| 风险 | 影响 | 规避手段 |
|---|---|---|
| 新样本收集慢，卡在 Phase C | M4 交付延后 | Phase A/B/D 独立可先行，C 有则加、无则以 S01/S02 打第一个基线 |
| 期望判级人工标注不客观 | anchor_issues 定义有偏 | 采用"数量区间 + 锚点集合"两级门槛，anchor 只选高置信度的必然命中 |
| 视觉真调成本失控 | Ark 账单意外 | 单样本 20000 tokens 上限硬拦截；baseline 全量跑一次记录，日常回归走 Mock |
| CHANGELOG 追认失真 | 老版本记录不准确 | 明确标注"追认摘要，非完整变更"，可疑处引用 commit SHA |
| Phase E 打 tag 前发现 anchor 判级抖动 | 阻止 release | 判级抖动=判断内核感知到 KB-A/KB-B 影响。需先跑 diff_baselines.py 定位再决定是否 hotfix |

---

## 9. 与其他 M 的接口

### 9.1 与 M1 的接口

- 读 `knowledge_base/norms/` 汇总所有 norm_id → coverage 计算
- 读 `knowledge_base/examples/metadata/` 汇总所有 EXAMPLE-XXXX → KB-B 命中分布
- **不修改** kb_query.py、kb_admin.py

### 9.2 与 M3 的接口

- 通过 `vision_pipeline.process_pdf()` 返回值获取 vision metrics
- 复用 `.workdir/{sample_id}/manifest.json` 结构
- **不修改** vision_pipeline.py、ark_provider.py

### 9.3 为 M5 铺路

- `runners/run_all.py` 提供批量执行原型，M5 的批量交付管线可借鉴调度方式
- `metrics.json` schema 可被 M5 复用作为批量任务的进度/结果标准

---

## 10. 落地后长期收益

- ✅ **每次 PR/commit 都能量化影响**：跑一遍 benchmark，diff 一眼看清
- ✅ **KB-A 补条时可评估价值**：新增条款后 coverage_report 显示命中变化
- ✅ **视觉真跑数据长期沉淀**：为将来切模型（如 Doubao-Vision 升级或换 GLM/Qwen）提供 A/B 依据
- ✅ **用户答疑有据**："这份论文为什么判 5 红？"→ 直接放 anchor + kb_a_hits
- ✅ **CHANGELOG 让贡献者/审计方一眼看清演进**

---

## 11. 需要用户确认的一句话清单

请回复以下四问，得到确认后启动 Phase A：

1. **样本来源**：Q1 选 A / B / C 或组合？
2. **Ark 真调策略**：Q2 选真调 baseline + Mock CI 吗？
3. **CHANGELOG 追认颗粒度**：Q3 选粗粒度追认吗？
4. **版本号策略**：Q4 直接打 v1.7.0 吗？

也欢迎补充你希望在 M4 里额外覆盖的场景（例如"我想看 KB-A 命中的分域分布图"或"能不能生成一份 PDF 判级摘要给答辩老师看"）。

---

**文件位置**：`plans/M4_Benchmark_CHANGELOG_v0.1.md`
**下一步**：等 Q1-Q4 回复 → 进入 Phase A 骨架搭建
