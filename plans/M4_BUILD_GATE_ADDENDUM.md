# M4 Build Gate Addendum · 新增补充信息清单落地

**起草时间**：2026-07-13 14:22 GMT+8
**性质**：v0.2 主计划书的**约束性补充**，Phase B 开跑前必须全部落实
**上游文件**：`upload/M4_Benchmark_CHANGELOG_新增补充信息清单-*.md`（用户版）
**约束优先级**：本 Addendum > `M4_Benchmark_CHANGELOG_v0.2.md`（如有冲突以本文件为准）

---

## 0. 一句话总纲

> **开发者负责运行 M4；普通用户享受 M4 带来的稳定性。M4 不改普通用户流程、不动 Skill 主依赖、不把测试样本当训练数据、不把发现问题当解决问题、不把首版结果当普适证明。**

---

## 1. 十一条硬约束落地对照表

| # | 补充清单条目 | 落地动作 | 状态 |
|---|---|---|---|
| 1 | M4 是开发者模块，不进普通用户主流程 | 新增 §2 边界声明 + Skill 主入口零 M4 依赖 | ✅ 新增 |
| 2 | Benchmark 数据与 KB / 训练数据严格隔离 | 新增 `benchmarks/policies/DATA_ISOLATION_POLICY.md` + 代码审计 | ✅ 新增 |
| 3 | M4 依赖不进 `requirements-core.txt` | 新增 `requirements-benchmark.txt` + core 保持零污染 | ✅ 新增 |
| 4 | 失败整改闭环（failure_id + 12 字段 + 10 类型） | 新增 `benchmarks/failures/` + `FAILURE_RECORD_TEMPLATE.md` + schema | ✅ 新增 |
| 5 | 用户可见的质量摘要（README/CHANGELOG/报告底部） | 新增 `benchmarks/public_summary/` + 报告 footer 字段 | ✅ 骨架 |
| 6 | 对外声明边界（禁夸大） | 新增 `benchmarks/policies/PUBLIC_CLAIMS_POLICY.md` | ✅ 新增 |
| 7 | 用户侧轻量自检 `self_check.py` | 新增 `scripts/self_check.py`（不调 Ark、不碰私有样本） | ✅ 新增 |
| 8 | 用户反馈转夹具的长期机制 | 新增 `benchmarks/policies/FEEDBACK_TO_FIXTURE_POLICY.md` | ✅ 新增 |
| 9 | 目录结构补齐（internal/failures/public_summary/policies） | 新增 4 目录 | ✅ 新增 |
| 10 | M4 最终业务定位固化 | 本文件 §2 + §12 | ✅ 新增 |
| 11 | Build Gate 未完成前不发正式版 | 本文件 §11 检查表 | ✅ 新增 |

---

## 2. M4 产品边界（明确声明）

### 2.1 普通用户流程（**M4 前后完全一致**）

```
上传论文 → 执行质检 → 查看报告
```

- **不新增**必填配置项、命令或操作步骤
- **不加载** `benchmarks/` 任何模块
- **不安装** `requirements-benchmark.txt`
- **不依赖** Baseline、Mock、CI 的存在
- Skill 主入口 `main.py` / `SKILL.md` 引用文件白名单：**benchmarks/ 一个都不能出现**

### 2.2 开发者流程（新增）

```
修改代码 → 跑 Benchmark → 看 diff → 处理 REGRESSION → 更新 Baseline → 发新版
```

### 2.3 M4 失败的责任范围

- ✅ M4 失败**只能阻止新版本发布**
- ❌ M4 失败**不得影响已发布正式版**运行
- ❌ M4 失败**不得触发自动修复**（禁止根据 fail 结果自动改 rules / prompts / KB）

### 2.4 验收指标

```bash
# 删除 benchmarks/ 后基础质检仍工作
rm -rf benchmarks/
pip install -r requirements-core.txt
python scripts/run_skill.py --input sample.docx   # 必须 exit 0
```

---

## 3. 数据隔离硬红线

### 3.1 Benchmark 样本 ≠ 训练数据 ≠ KB-B 范例

| 用途 | Benchmark 允许？ | 说明 |
|---|---|---|
| 回归测试 / 失败复现 | ✅ | 本职工作 |
| 自动进入 KB-A 或 KB-B | ❌ 禁止 | 隔离目录 + 隔离入库脚本 |
| 用作 KB-B 优秀论文范例 | ❌ 默认禁止 | 需重新独立授权 + 独立审核 |
| 微调 / 提示词训练 | ❌ 禁止 | 首个 Ark 微调触发前用户手动书面确认 |
| 生产代码根据 sample_id 特殊判断 | ❌ 禁止 | pre-commit hook + CI grep 扫描 |

### 3.2 目录隔离（**强制**）

```
benchmarks/                       # 测试隔离区
├── documents/                    # Benchmark 样本
│   ├── private_local_manifest/   # 私有真实论文 manifest（源文件不入 Git）
│   ├── public_synthetic/         # 合成样本
│   └── open_license/             # 开放授权样本
├── internal/                     # (新增) 完整私有论文样本挂载点，不进公开包
├── fixtures/                     # 小夹具（可公开）
└── failures/                     # (新增) 失败记录

knowledge_base/                   # 生产 KB（M1）
├── examples/                     # KB-B 范例层（独立入库流程）
└── norms/                        # KB-A 规范层
```

**互斥性**：`kb_ingest.py` 明确拒绝 `benchmarks/**` 路径。

### 3.3 生产代码防污染

**pre-commit + CI 扫描**（`benchmark-offline.yml`，仅 `.py`）：

```bash
# 禁止生产代码（.py）硬编码 sample_id / 私有样本名
grep -RnE '(sample_id\s*==\s*"[SDRQV][0-9]{2,3}|_zhc_)' \
     --include='*.py' \
     scripts/ rules/ agent_instructions/ references/ 2>/dev/null
```

命中 → CI RED。

> `.md` 文档描述历史样本（如 vision_protocol.md）不属于污染，不受本断言约束。

---

## 4. 依赖隔离

### 4.1 分层规范

| 依赖文件 | 用途 | 允许包 |
|---|---|---|
| `requirements-core.txt` | 生产必装（DOCX/PDF/KB-A YAML/报告/M3 视觉 schema） | 不含 pytest/chroma/openai/sklearn；jsonschema（M3 P1-13）已在 core 不受本约束 |
| `requirements-kb.txt` | KB-B 向量库（可选） | chromadb, sentence-transformers |
| `requirements-vision.txt` | 视觉（可选） | openai |
| `requirements-dev.txt` | 开发辅助 | linter/formatter |
| **`requirements-benchmark.txt`** | **新增 · M4 专用** | **pytest（jsonschema 已在 core，不重复列）** |

### 4.2 core 零污染验收

```bash
diff <(grep -Ev '^(#|$)' requirements-core.txt | cut -d= -f1 | sort) \
     <(cat <<EOF | sort
python-docx
pypdf
pdfplumber
lxml
pyyaml
jinja2
markdown
pypdfium2
Pillow
EOF
)
# 期望：无差异（除非本条策略被明确更新）
```

### 4.3 Benchmark 缺失时的降级行为

```python
# scripts/run_skill.py 入口示意
try:
    import benchmarks   # noqa: F401
    _BENCHMARK_AVAILABLE = True
except ImportError:
    _BENCHMARK_AVAILABLE = False
# 不 raise、不告警——生产流程根本不 import benchmarks
```

---

## 5. 失败整改闭环

### 5.1 12 字段模板（每个 fail 必填）

```yaml
failure_id: F-YYYYMMDD-NNN
sample_id: S02_zhc_pdf
evidence_locator: "p20, table 3"
failure_type: missing_red | false_red | wrong_severity | wrong_evidence | \
              kb_a_mismatch | kb_b_bad_recall | vision_error | docx_pdf_delta | \
              perf_regression | render_error
expected: "..."
actual: "..."
root_cause_module: rules | kb_a | kb_b | vision | parse | render | perf
fix_owner: "@user"
fix_commit: <sha>
before_after_diff: <path or inline>
requires_changelog_entry: true|false
promote_baseline_allowed: true|false
opened_at: 2026-07-13
closed_at: null
```

### 5.2 目录

```
benchmarks/failures/
├── SCHEMA.md                              # 12 字段说明
├── TEMPLATE.yaml                          # 空模板
├── open/                                  # 未闭环
│   └── F-20260713-001.yaml
└── closed/                                # 已闭环
    └── F-20260710-001.yaml
```

### 5.3 Release Gate 联动

- **未闭环的 `open/*.yaml` 且 promote_baseline_allowed=false** → 阻断发布
- 每个阻断问题必须有关闭证据（`fix_commit` + `before_after_diff`）
- **禁止把"发现问题"自动等同于"问题已解决"**

---

## 6. 用户可见质量摘要

### 6.1 报告底部固定字段（新增到 `render_report_html.py` / `render_report.py`）

```
────────────────────────────────
Skill 版本：v1.7.0
规则版本：rules-2026.07
知识库版本：kb-2026.07
Benchmark 数据集：benchmark-dataset-v0.1
发布验证状态：已通过 / 候选版
最近验证日期：2026-07-13
────────────────────────────────
```

**信息保护红线**：报告底部**不得**含学生原文摘录、姓名、学号、学校、私有样本路径、模型原始响应、API Key、内部错误栈、账户费用。

### 6.2 `benchmarks/public_summary/` 目录

```
benchmarks/public_summary/
├── SCORECARD.md          # 面向评委的对外摘要
└── README.md             # 生成脚本 + 保护红线
```

`SCORECARD.md` 内容项（**只列，不夸大**）：
- 当前版本
- 最近验证日期
- Benchmark 数据集版本
- 覆盖的输入类型（DOCX/文本 PDF/扫描 PDF/图表密集/KB-B 稀疏）
- 关键问题回归状态（红/绿灯）
- 硬门禁字段 = 0 的样本数
- DOCX/PDF 能力回归状态
- 平均运行耗时 p50/p95 区间
- 发布验证状态（已通过 / 候选版 / 未验证）

### 6.3 README 更新（v1.7.0 时）

在 README.md 末尾新增「质量验证说明」段落，链到 `benchmarks/public_summary/SCORECARD.md`。

---

## 7. 对外声明边界（禁夸大）

### 7.1 每次公开公示必须同时给出

- dataset_version
- 完整论文样本数量 + 小型夹具数量
- 覆盖学科 + 论文类型
- **未覆盖场景**
- Skill 版本、规则版本、KB 版本、视觉模型版本
- 测试日期 + 测试环境
- Mock vs 真调 Ark 区分

### 7.2 禁止表述（黑名单）

- ❌ "适用于所有学科和所有论文"
- ❌ "整体准确率 XX%"（首版 5 样本无从代表）
- ❌ "可替代教师/导师/专家审阅"
- ❌ "所有 PDF/表格/公式均能正确识别"
- ❌ "视觉模型识别绝对可信"
- ❌ "通过 5 篇论文即可证明系统普适有效"

### 7.3 推荐官方措辞

> 当前版本已在指定的 DOCX、文本型 PDF、扫描 PDF、图表密集论文及知识库稀疏场景中完成回归验证。测试结果仅代表当前数据集、模型、规则与运行环境下的表现，不能替代教师或专业评审。

### 7.4 落地文件

`benchmarks/policies/PUBLIC_CLAIMS_POLICY.md`（后续 §9 生成）

---

## 8. 用户侧轻量自检 `scripts/self_check.py`

### 8.1 检查项

| 项 | 检查方法 | 通过标准 |
|---|---|---|
| DOCX 基础解析 | 用内置合成 docx 走 parse_docx | 返回非空 clean_units |
| 文本型 PDF 解析 | 用内置合成 pdf 走 parse_pdf | 返回非空文本 |
| KB-A 加载 | 读 `knowledge_base/norms/*.yaml` | ≥ 1 条 rule |
| 报告渲染 | 空 issue list 走 render_report_html | 生成非空 HTML |
| 视觉未配置降级 | 检查 vision_pipeline 未 crash | fallback 到人工复核提示 |
| 视觉配置后（可选） | 用户显式 `--with-vision` | 用合成 PNG 跑 Ark 一次 |

### 8.2 硬约束

- ❌ 默认不调 Ark
- ❌ 不碰任何私有 Benchmark 样本
- ❌ 不宣称"质检准确率已重新验证"
- ✅ 只回答"当前安装能否运行"

### 8.3 依赖

只依赖 `requirements-core.txt`。

---

## 9. 用户反馈转夹具流程

`benchmarks/policies/FEEDBACK_TO_FIXTURE_POLICY.md`（后续 §11 生成）核心：

1. 记录用户反馈**不保存完整原论文**
2. 明确取得**用户授权**
3. 只提取**最小必要片段**（问题所在段/表/图）
4. 删除姓名、学号、学校、联系方式
5. 优先转化为**合成或半合成夹具**
6. 补充 `must_hit` 或 `must_not_hit`
7. 修复后纳入后续 CI
8. CHANGELOG 记录 `Added — Fixture: F-YYYYMMDD-NNN 复现用户反馈 XXXX`
9. **未经授权**不得将用户论文加入 Benchmark、KB 或公开仓库

---

## 10. 新增目录/文件清单（Phase B 前必须存在）

```
benchmarks/
├── internal/                                     # 新增（占位）
│   └── README.md                                  # 私有论文挂载说明
├── failures/                                     # 新增
│   ├── SCHEMA.md
│   ├── TEMPLATE.yaml
│   ├── open/.gitkeep
│   └── closed/.gitkeep
├── public_summary/                               # 新增
│   ├── README.md
│   └── SCORECARD.md                              # 首版空壳
└── policies/                                     # 新增
    ├── DATA_ISOLATION_POLICY.md
    ├── PUBLIC_CLAIMS_POLICY.md
    └── FEEDBACK_TO_FIXTURE_POLICY.md

scripts/
└── self_check.py                                 # 新增

requirements-benchmark.txt                        # 新增
```

---

## 11. Build Gate 检查表（Phase B 开跑前必须全绿）

- [x] 落地本 Addendum
- [x] `requirements-benchmark.txt` 新增
- [x] `requirements-core.txt` **未新增**任何 M4 开发/测试依赖（M3 已在的 jsonschema 不受本约束）
- [x] 4 个新目录到位（internal/failures/public_summary/policies）
- [x] 3 份 policies 到位
- [x] `scripts/self_check.py` 到位（不调 Ark）
- [x] `failures/SCHEMA.md` + `TEMPLATE.yaml`
- [x] `SCORECARD.md` 空壳
- [x] CI 新增「生产代码硬编码 sample_id 扫描」步
- [x] `kb_ingest.py` 显式拒绝 `benchmarks/**` 路径
- [x] 主入口/SKILL.md 引用文件白名单审计（不含 benchmarks/）
- [x] `pytest 44/44` 保持零回归
- [x] DOCX v1.5.0 sha 保持零回归
- [ ] 上述所有变更单一 commit 提交（**待用户确认后 push**）

---

## 12. M4 最终业务定位（固化）

> 一套供开发者使用的论文质检质量保障体系。它通过固定样本、正负锚点、自动跑分、版本差异、缺陷整改和发布门禁，确保新版本不会丢失原有能力、增加严重误判或出现明显性能退化。同时，它以简化质量摘要、版本信息和轻量自检向普通用户传递可信度，但不会增加普通用户的使用和安装负担。

**最终六原则**：

1. 开发者负责运行 M4，普通用户享受 M4 带来的稳定性。
2. 测试论文是考试题，不是训练数据。
3. M4 发现问题，但不会自动修复问题。
4. Benchmark 可以专业，但不能让基础 Skill 变重。
5. 质量结果可以公开，但不得夸大证明范围。
6. 用户反馈应转化为可复用测试夹具，而不是直接沉淀完整私有论文。
