# M4 · Release Gate（发布门禁清单）

**版本**：v0.2-draft-1
**约束级别**：**硬阻止发布**（红灯）+ **需人工确认**（黄灯）+ **自动通过**（绿灯）
**引用**：v0.2 主计划书 §10 · P0-14
**适用于**：从 `v1.7.0-rc.1` 起所有 M4 及后续版本发布

---

## 一、红灯清单（自动阻止发布）

以下任一命中 → **拒绝打正式 tag，拒绝生成 GitHub Release**：

### 1.1 判断质量红线

- [ ] `judgment_quality.forbidden_issue_count > 0`（新增 forbidden 命中）
- [ ] `judgment_quality.false_red_count > 0`（错误红色问题存在）
- [ ] 任一 must_hit 高置信 anchor（`confidence: high`）丢失
- [ ] 任一红色 issue 的 `evidence_completeness_rate < 1.0`
- [ ] `kb_a_quality.unsupported_red_count > 0`（红色缺规范/方法学依据）

### 1.2 视觉红线

- [ ] `vision_quality.visual_false_red_count > 0`（视觉错误导致红色结论）
- [ ] `vision_quality.quality_gate_false_pass_count > 0`（低质量样本被错误放行）

### 1.3 基础流程红线

- [ ] DOCX 全流程冒烟失败
- [ ] Pre-Build Audit 复跑 sha256 不一致（`5bd30276...`）
- [ ] pytest 未全通过

### 1.4 数据治理红线

- [ ] 私有论文文件进入 Git 或 CI artifact
- [ ] Ark API Key / GitHub token 出现在日志或 artifact
- [ ] 未授权样本被 Benchmark 使用
- [ ] baseline 未经审批被覆盖

### 1.5 元数据一致性红线

- [ ] `arkclaw.yaml.version` ≠ 打算发布的 tag
- [ ] tag 已存在但内容与 release notes 不一致
- [ ] CHANGELOG 缺少本版本条目
- [ ] CHANGELOG 中的 commit/tag 引用不可解析

---

## 二、黄灯清单（需人工确认）

以下任一命中 → **暂停自动发布，转人工审阅**：

### 2.1 判级波动

- [ ] `judgment_counts.yellow` 相对 baseline 波动 > 30%
- [ ] `kb_b_cards.count` 相对 baseline 变化
- [ ] 新增 must_hit 未在旧 baseline 内（可能是"新的正确发现"）

### 2.2 性能波动

- [ ] `performance.total_seconds_p95` 相对 baseline 恶化 20%-35%
- [ ] `performance.tokens_total_p50` 相对 baseline 增加 30%-50%
- [ ] `performance.estimated_cost_cny_p50` 相对 baseline 增加 30%-50%

### 2.3 一致性波动

- [ ] 模型措辞变化但 `judgment_fingerprints` 不变（`EXPECTED_VARIANCE` 需确认非隐性回归）
- [ ] PDF↔DOCX 出现新的 allowed_differences 未在 parity_expectation 中

---

## 三、绿灯清单（自动通过）

以下情形**允许自动通过**，不触发人工审阅：

- issue 顺序变化（fingerprint 集合不变）
- 报告生成时间戳变化
- 文案轻微改写（fingerprint 保持一致）
- artifact 二进制 sha256 变化但 `canonical_result_json_sha256` 不变
- Mock 内部非语义字段变化
- `judgment_counts.yellow` 波动 ≤ 10%

---

## 四、diff 分类映射

`compare_run.py` 输出的 `diff_report.json` 必须将每处差异归到六类之一：

| 类别 | 语义 | 门禁影响 |
|---|---|---|
| `REGRESSION` | 已有 anchor 丢失、fingerprint 消失、性能明显恶化 | 🟥 红灯 |
| `INTENDED_IMPROVEMENT` | 新 fingerprint 命中且经人工裁决为"正确的新发现" | 🟨 黄灯（决定是否入 baseline） |
| `EXPECTED_VARIANCE` | 顺序/措辞变化，fingerprint 不变 | 🟩 绿灯 |
| `DATASET_CHANGE` | expected 或 sample manifest 变化 | 🟨 黄灯（须写 change_reason） |
| `ENVIRONMENT_CHANGE` | 模型 endpoint / 依赖 lock 变化 | 🟨 黄灯（须记录 reproducibility diff） |
| `NEEDS_REVIEW` | 无法自动判定 | 🟨 黄灯 |

---

## 五、Baseline 更新六问（P1-3）

每次 baseline 更新必须在 `APPROVAL.yaml` 中回答：

```yaml
baseline_id: v1.7.0-rc.1
approved_by: "user_name"
approved_at: "2026-07-13T15:00:00+08:00"

six_questions:
  q1_why_change: "首版 baseline 落定"
  q2_is_it_correct: "所有差异均经人工确认为 INTENDED_IMPROVEMENT 或 EXPECTED_VARIANCE"
  q3_who_approved: "user_name + ArkClaw"
  q4_what_changed:
    - "S01 首次入库"
    - "S02 首次入库"
    - "视觉裁剪集 V001-V015 入库"
  q5_impacts_changelog: true
  q6_impacts_version: true

dataset_manifest_hash: "<sha256>"
skill_version: "1.7.0-rc.1"
commit_sha: "<sha>"
rules_hash: "38425bb2..."
kb_a_snapshot_hash: "2f06c8f5..."
```

---

## 六、发布流程（v1.7.0-rc.1 → v1.7.0）

### 6.1 rc.1 发布（Phase E）

```bash
# 1. 跑一遍完整 benchmark
python benchmarks/runners/run_all.py --run-id 20260713-rc1

# 2. 校验所有 metrics.json 符合 schema
python benchmarks/lib/schema_validator.py --run 20260713-rc1

# 3. 生成 scorecard
python benchmarks/runners/generate_scorecard.py --run 20260713-rc1

# 4. 检查红灯
python benchmarks/runners/release_gate_check.py --run 20260713-rc1
# 如果任一红灯 → 退出 1，禁止发布

# 5. 晋升为 baseline
python benchmarks/runners/promote_baseline.py \
    --from benchmarks/runs/20260713-rc1 \
    --to v1.7.0-rc.1 \
    --approved-by "user_name" \
    --change-reason "M4 首版 rc.1 落定"

# 6. 更新 arkclaw.yaml 版本号
# 7. 更新 CHANGELOG.md
# 8. commit + tag v1.7.0-rc.1
# 9. push origin main + tag
# 10. gh release create v1.7.0-rc.1 --prerelease
```

### 6.2 观察期

- **最少 3 个自然日**
- **最少 1 次真调 Ark benchmark 复跑**（可 CI 手动触发）
- 期间任何红灯发现 → 回退到 rc.1，修复后 → rc.2

### 6.3 v1.7.0 正式发布

```bash
# 1. 全部红灯检查通过
python benchmarks/runners/release_gate_check.py --strict --baseline v1.7.0-rc.1

# 2. 至少 3 次重复运行确认稳定
python benchmarks/runners/run_all.py --repeats 3 --run-id 20260716-stable

# 3. 对比 rc.1 baseline
python benchmarks/runners/compare_run.py \
    --candidate benchmarks/runs/20260716-stable \
    --baseline benchmarks/baselines/v1.7.0-rc.1

# 4. 差异全部 EXPECTED_VARIANCE 或 INTENDED_IMPROVEMENT
# 5. 更新 arkclaw.yaml → 1.7.0
# 6. 更新 CHANGELOG（[1.7.0-rc.1] → [1.7.0]，追加正式段）
# 7. commit + tag v1.7.0
# 8. push origin main + tag
# 9. gh release create v1.7.0 --latest
```

---

## 七、脚本清单（Phase A/B 落地）

| 脚本 | 用途 | 优先级 |
|---|---|---|
| `benchmarks/runners/release_gate_check.py` | 自动化红灯扫描 | P0 |
| `benchmarks/runners/compare_run.py` | 差异分类 | P0 |
| `benchmarks/runners/promote_baseline.py` | 晋升 + APPROVAL.yaml | P0 |
| `benchmarks/lib/schema_validator.py` | metrics/expected/manifest 校验 | P0 |
| `benchmarks/runners/generate_scorecard.py` | Scorecard 生成 | P1 |
| `benchmarks/runners/coverage_report.py` | KB-A/KB-B 覆盖 | P1 |

---

## 八、release_gate_check.py 首版接口

```bash
python benchmarks/runners/release_gate_check.py \
    --run <run_id> \
    --baseline <baseline_id> \
    [--strict]              # 严格模式：黄灯也阻止
    [--allow-baseline-none] # 首版无 baseline 时用
```

**输出**：
- exit 0 = 全绿
- exit 1 = 有红灯（细节 stderr）
- exit 2 = 有黄灯（非 strict 模式下也是 exit 0）
- 落 report：`benchmarks/runs/{run_id}/release_gate_report.md`

---

## 九、常见发布决策场景

### 场景 1：首版落地，无 baseline
- 允许 `--allow-baseline-none`
- release_gate_check 只检查绝对红线（false_red = 0 等），不做 diff
- promote 后自动成为 baseline

### 场景 2：修复 KB-A 命中偏差
- 修改 kb_query.py A 路由（假设需要）→ 需独立 PR + 单测
- 跑 benchmark → 会看到 kb_a_hits 变化 → 分类 INTENDED_IMPROVEMENT
- 人工审阅 → APPROVAL.six_questions
- baseline 晋升 → CHANGELOG 记录 → 版本号 patch

### 场景 3：模型换代（doubao → 下代）
- reproducibility.model_id 变化 → 全部差异标 ENVIRONMENT_CHANGE
- 必须重跑基线对比，重新审阅所有 fingerprint 变化
- 视为**重要变更**，minor 版本

### 场景 4：新增合成样本 D02
- dataset_version bump → benchmark-dataset-v0.2
- expected/D02.expected.yaml 落地
- baseline v1.7.x 追加 D02 metrics
- 不 bump skill version（只 bump dataset version）

---

**首版 DoD**：
- [ ] `release_gate_check.py` 覆盖红灯清单全部条目
- [ ] `compare_run.py` 输出六分类
- [ ] `promote_baseline.py` 强制 --approved-by 和 --change-reason
- [ ] 首个 baseline `v1.7.0-rc.1/APPROVAL.yaml` 完整签署
- [ ] release_gate_report.md 可读、可审计
