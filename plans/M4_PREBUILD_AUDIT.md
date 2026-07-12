# M4 Pre-Build Audit · v1.6.2 冻结点

**审计时间**：2026-07-12 23:56 GMT+8
**审计人**：ArkClaw（自检）+ 用户复核
**审计目的**：M4 Build 前证明「当前基线真实存在且可复现」
**冻结 tag**：`v1.6.2-pre-m4-frozen`（本次新打）

---

## 一、仓库状态

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/05ffh/econ-paper-check-skill.git |
| HEAD commit | `20abcca78f672f034b6a3743b1161c6549fe7975` |
| Branch | `main` |
| Exact tag on HEAD | `v1.6.2` |
| Working tree clean | ⚠️ 一个未跟踪文件：`plans/M4_Benchmark_CHANGELOG_v0.1.md`（M4 计划书本身，进入 build 后由 v0.2 归档） |
| Origin 同步 | HEAD == origin/main ✅ |
| 新打冻结 tag | `v1.6.2-pre-m4-frozen`（annotated，指向 20abcca）✅ |

---

## 二、测试与诊断状态

### pytest
```
tests/vision/  ............................  29 passed in 0.77s
```
- 组成：14 pipeline/injection + 15 Ark Mock
- 已运行时间：2026-07-12 23:57
- 结果：29/29 ✅

### doctor.py（v1.6.1 内部版本号）
```
基础论文质检:        ✅ 可用
KB-B 范例参照:       ✅ 可用
PDF 视觉辅助识别:    ⚪ 未配置（可选能力；Word/文本 PDF 质检不受影响）
```
- Vision 当前状态：⚪「未配置」（用户已撤销 Ark Key，尚未新建；这是**预期**状态）
- 结论：审计不阻塞。Vision 层依赖用户操作，M4 Baseline 首轮真调需重新配置 Key。

---

## 三、Skill 版本与哈希指纹

| 组件 | 值 |
|---|---|
| Skill 版本 | `1.6.2` (arkclaw.yaml) |
| **规则集哈希**（`rules/` + `agent_instructions/` + `references/` 全 md/yaml 归并 sha256） | `38425bb29edd81be1b43dda6e908dee456d0bb10268ac2b77b3e193391ad3db5` |
| **KB-A 快照哈希**（`knowledge_base/norms/**/*.yaml`） | `2f06c8f5e8c5e7a034cfc0446c643be837d2aa43bd1f23d3444a4d014ab82201` |
| KB-A citation 条款数 | 9（GB/T 7714—2015） |
| KB-A methods 条款数 | 9（Wooldridge） |
| **M3 视觉代码哈希**（`scripts/vision/**/*.py`） | `17b3d10d07c7b26107672a59a24f782f12fd843f0f865d76f3ce63238dc717c1` |
| KB-B ledger | 20 篇论文 / 2198 chunks / 18M active DB |
| KB-B 已有快照 | 3 个 |

> 复现命令（可再次执行核对）：
> ```bash
> find rules/ agent_instructions/ references/ -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.yml" \) | sort | xargs sha256sum | sha256sum
> find knowledge_base/norms -type f -name "*.yaml" | sort | xargs sha256sum | sha256sum
> find scripts/vision -type f -name "*.py" | sort | xargs sha256sum | sha256sum
> ```

---

## 四、M3 Provider / Schema / Quality Gate 存在性核验

| 关键文件 | 状态 | 行数 |
|---|---|---|
| `scripts/vision_pipeline.py` | ✅ | 328 |
| `scripts/vision/providers/ark_provider.py`（含 `_SYSTEM_PROMPT_STRICT`） | ✅ | 353 |
| `scripts/vision/providers/base.py`（VisionRequest/Response/Error 契约） | ✅ | 存在 |
| `scripts/vision/providers/mock_provider.py` | ✅ | 存在 |
| `scripts/vision/upload_policy.py`（4MB/3000×4000 门禁） | ✅ | 存在 |
| `scripts/vision/dispatcher.py` | ✅ | 存在 |
| `scripts/vision/normalizer.py`（caption/n_rows/n_cols） | ✅ | 存在 |
| `scripts/vision/quality_scorer.py`（extraction_quality_score / hard_gates） | ✅ | 存在 |
| `scripts/vision/knowledge_bridge.py`（compute_kb_eligibility） | ✅ | 存在 |
| `scripts/doctor.py`（4 组 + 3 态视觉） | ✅ | 存在 |
| `tests/vision/test_pipeline_smoke.py` | ✅ | 存在 |
| `tests/vision/test_prompt_injection.py`（4 项） | ✅ | 存在 |
| `tests/vision/test_ark_mock_openai.py`（15 项） | ✅ | 存在 |

---

## 五、样本资产存在性与授权状态

| 项 | 状态 | 备注 |
|---|---|---|
| S01 (张弘济 DOCX 版) 源文件 | ⚠️ 未在 upload/ 内直接可见 | 需从最近 workspace 副本溯源（`.econ-paper-check/20260710_213222/`） |
| S02 (张弘济 PDF 版) 源文件 | ✅ `upload/张弘济初稿-1783849863542-17g1ta.pdf`（1.5 MB, 24 页） |
| S01 v1.5.0 基线 parse_result | ✅ `.workdir/baseline_test/parsed/paper_text.json` |
| **S01 parse sha256** | ✅ `5bd30276d8f8ee9930fcac729f54a88e83333350029619aecba7e9e0d167ad7e` |
| S02 端到端产物（含视觉版和无视觉版） | ✅ `.workdir/zhc_test/reports_with_vision/`, `reports_without_vision/` |
| **张弘济样本授权** | ⚠️ **待用户书面确认**：是否允许作为 Benchmark 集成样本、是否允许 Ark 云调用、是否允许 Git 分发 |

**风险**：M4 v0.2 落地前，必须完成张弘济样本的 sample_manifest.yaml 签署。若用户不同意云调用或不同意 Git 分发，则 S01/S02 只能保留在 `.workdir/`（gitignore），Git 中只保留 `manifest + hash`。

---

## 六、当前端到端跑通证据

**已知可复现结果**（来自 M3 收尾）：
- **张弘济 p20 表 3 视觉识别**：10×3 表格，30/30 格 100% 正确
- **caption 提取**：「表 3 主回归结果：LR对NIM的影响」正确
- **耗时**：15.3s
- **tokens**：5316
- **模型**：doubao-seed-2-0-mini-260428
- **产物路径**：`.workdir/zhc_test/reports_with_vision/`

**DOCX 基线零回归证据**：
- v1.5.0 vs v1.6.1 parse_result.json sha256 完全一致
- 值：`5bd30276d8f8ee9930fcac729f54a88e83333350029619aecba7e9e0d167ad7e`

---

## 七、运行环境

| 项 | 值 |
|---|---|
| OS | Linux 6.8.0-55-generic (x64) |
| Python | 3.12.3 |
| openai | 1.109.1 |
| pypdfium2 | 5.7.1 |
| chromadb | 0.5.23 |
| sentence-transformers | 3.3.1 |
| python-docx | 1.2.0 |
| pypdf | 6.14.2 |
| PyYAML | 6.0.3 |
| pydantic | 2.12.5 |
| pillow | 12.3.0 |
| Jinja2 | 3.1.6 |

---

## 八、依赖锁定与冻结建议

- `constraints-tested.txt`（v1.6.1 快照）已存在 → M4 v0.2 首次基线跑分时直接采用
- **建议 M4 Phase A 增加**：`benchmarks/env/lock.txt`（本次 pip freeze 完整快照 + 关键包 hash）→ 供 metrics.reproducibility.dependency_lock_hash 使用

---

## 九、审计结论

**Conditional GO 前置条件已具备**：
- ✅ 仓库状态干净可追溯
- ✅ pytest / doctor 通过
- ✅ 核心哈希已锁定
- ✅ 冻结 tag 已打
- ⚠️ **待用户确认**：
  1. 张弘济样本授权 manifest（能否云调用 / 能否 Git 分发）
  2. M4 v0.2 决策 Q1-Q4（样本来源、Ark 策略、CHANGELOG 颗粒度、版本策略）

**本审计文件不修改任何生产代码，不改判断内核，不改 M1/M3。**

---

## 十、下一步

1. 用户回复：样本授权 + Q1-Q4
2. ArkClaw 起草 v0.2 主计划书 + 5 份配套 schema/文档
3. v0.2 审阅通过 → 进入 Phase A（骨架）

**冻结点**：任何 Phase A 之后的改动都必须能对比回 `v1.6.2-pre-m4-frozen` 验证零回归。
