# benchmarks/failures/ 目录

**约束级别**：硬红线
**上游**：`plans/M4_BUILD_GATE_ADDENDUM.md` §5

---

## 目录结构

```
failures/
├── SCHEMA.md          # 本文件
├── TEMPLATE.yaml      # 空模板
├── open/              # 未闭环失败（阻断发布）
│   └── F-YYYYMMDD-NNN.yaml
└── closed/            # 已闭环失败（历史归档）
    └── F-YYYYMMDD-NNN.yaml
```

---

## 12 必填字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `failure_id` | string | 正则 `^F-\d{8}-\d{3}$` |
| `sample_id` | string | 引用 `benchmarks/documents/**/*.manifest.yaml` 中的 sample_id；夹具用 R/Q/V 前缀 |
| `evidence_locator` | string | 原文位置，如 `"p20, table 3"` 或 `"section 4.2, para 3"` |
| `failure_type` | enum | 见下 |
| `expected` | string | 预期结果的自然语言描述 |
| `actual` | string | 实际结果的自然语言描述 |
| `root_cause_module` | enum | rules / kb_a / kb_b / vision / parse / render / perf |
| `fix_owner` | string | 责任人（@user_id） |
| `fix_commit` | string | 关闭时填 commit sha |
| `before_after_diff` | string | 关闭时填对比文件路径或 inline snippet |
| `requires_changelog_entry` | bool | true / false |
| `promote_baseline_allowed` | bool | true → 允许晋升新 baseline；false → 阻断发布 |

**附加字段**：

- `opened_at` (ISO date) 必填
- `closed_at` (ISO date) 关闭时必填
- `notes` (string) 可选

---

## failure_type 十种（enum）

| 值 | 含义 |
|---|---|
| `missing_red` | 漏判红色硬伤 |
| `false_red` | 误判为红色 |
| `wrong_severity` | 判级错误（红/黄/绿/灰）非漏非误 |
| `wrong_evidence` | 证据引用错误（引错位置或内容） |
| `kb_a_mismatch` | KB-A 规范挂载错误 |
| `kb_b_bad_recall` | KB-B 范例召回错误（应召未召 / 不该召反召） |
| `vision_error` | 视觉识别错误（数字、符号、表头绑定等） |
| `docx_pdf_delta` | 同一论文 DOCX / PDF 两版结果不合理差异 |
| `perf_regression` | 性能退化（p95 相对 baseline > 阈值） |
| `render_error` | 报告渲染异常（docx/html 生成错误、格式问题） |

---

## Release Gate 联动

- `open/*.yaml` **中任一** `promote_baseline_allowed: false` → **阻断发布**
- `closed/*.yaml` 全部要求 `fix_commit` 与 `before_after_diff` 非空
- CHANGELOG 中每个 `Fixed` 条目应能对应回一个 `F-*.yaml`

---

## 使用流程

```bash
# 1) 新建 failure
cp benchmarks/failures/TEMPLATE.yaml \
   benchmarks/failures/open/F-$(date +%Y%m%d)-001.yaml
# 编辑字段

# 2) 修复后关闭
git mv benchmarks/failures/open/F-20260713-001.yaml \
       benchmarks/failures/closed/F-20260713-001.yaml
# 填 closed_at / fix_commit / before_after_diff / promote_baseline_allowed=true
```

---

## 禁止事项

- ❌ 未闭环的 open failure 直接发新版本
- ❌ 把"发现问题"自动等同于"问题已解决"
- ❌ 不填 `before_after_diff` 就关闭
- ❌ 根据 sample_id 硬编码修复逻辑（走 `DATA_ISOLATION_POLICY.md`）
