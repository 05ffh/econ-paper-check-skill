# Benchmarks · 经管论文智检 Skill 可回归质量体系

**首版**：`v1.7.0-rc.1`（M4 交付）
**数据集版本**：见 `VERSION`
**主计划**：`../plans/M4_Benchmark_CHANGELOG_v0.2.md`
**Release Gate**：`../plans/M4_RELEASE_GATE.md`
**样本治理**：`../plans/M4_SAMPLE_GOVERNANCE.md`

---

## 一句话

**"不仅知道版本变了什么，还能证明：高风险问题没有漏、正确内容没有被误判、证据和规范可复核、视觉数字没有读错、性能与成本可控制、每次发布都有可审计依据。"**

---

## 四层数据

| 层 | 目录 | 首版下限 |
|---|---|---|
| 规则夹具 | `fixtures/rules/` | ≥ 10 |
| KB 查询夹具 | `fixtures/kb_queries/` | ≥ 10 |
| 视觉裁剪夹具 | `fixtures/vision_crops/` | ≥ 15 |
| 完整文档样本 | `documents/` | ≥ 2 |

---

## 目录

```
benchmarks/
├── VERSION                      # dataset 版本号
├── env/lock.txt                 # pip freeze 快照 + hash
├── fixtures/                    # 微型夹具（可入 Git）
├── documents/
│   ├── public_synthetic/        # 合成 / 半合成论文（可入 Git）
│   ├── private_local_manifest/  # 私有真实论文（只入 manifest+hash）
│   └── open_license/            # 开放许可样本
├── expected/                    # 完整文档 expected.yaml
├── schema/                      # 3 份 JSON Schema
├── runs/                        # 候选运行（可覆盖）
├── baselines/                   # 黄金基线（只读）
├── reports/                     # scorecard
├── lib/                         # fingerprint / schema_validator
└── runners/                     # run_single / compare / promote / …
```

---

## 快速开始

```bash
# 生成 env lock
python benchmarks/runners/refresh_env_lock.py

# 校验所有 schema
python benchmarks/lib/schema_validator.py --all

# 跑冒烟 fixtures/rules
python benchmarks/runners/run_single.py --sample R001 --run-id smoke-$(date +%Y%m%d%H%M)

# 对比 baseline
python benchmarks/runners/compare_run.py \
    --candidate benchmarks/runs/smoke-XXXX \
    --baseline benchmarks/baselines/v1.7.0-rc.1

# 晋升 baseline（需人工审批）
python benchmarks/runners/promote_baseline.py \
    --from benchmarks/runs/smoke-XXXX \
    --to v1.7.0-rc.1 \
    --approved-by "user_name" \
    --change-reason "首版 baseline 落定"
```

---

## 硬约束（拷贝自 §6 / §10 / Sample Governance）

- **runs/ 与 baselines/ 严格分离**，baseline 只读，晋升需人工审批
- **must_hit + forbidden_issues 双向锚点**
- 回归主键：**issue_fingerprint**（非 R-01）
- 视觉门禁：数值正确性（exact_match ≥ 0.95、sign = 1.0、visual_false_red = 0）
- 私有论文**不入 Git**，只入 manifest + sha256
- Ark 云调用需 `allowed_uses.cloud_vision: true`
- 硬门禁字段（须 = 0）：`forbidden_issue_count`, `false_red_count`, `unsupported_red_count`, `quality_gate_false_pass_count`, `visual_false_red_count`

---

## 状态

- Phase 0（Audit + Freeze）✅
- Phase A（Schema + 骨架）🚧 **进行中**
- Phase B（10+10+15 夹具）
- Phase C（完整文档集成）
- Phase D（真调 Ark + 性能）
- Phase E（CHANGELOG + rc.1 发布）
