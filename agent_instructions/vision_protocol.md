# Vision Protocol · M3 v1.6.0 骨架

> **状态**：Phase 1 骨架，仅登记范围，具体规则在 Phase 4 完整填写。
> **前置**：M1 三层证据（`student_evidence` / `normative_basis` / `example_reference`）保持不变。
> **本文件目的**：占位 + 声明"视觉不改判级规则，只解决看得见看不见"。

---

## 1. 本文件范围

本文件规定视觉模块（M3）与经管论文智检 Skill 判断内核的**接口协议**。**不改动**：

- `rules/*.yaml` 判定规则
- `agent_instructions/evidence_requirement.md` 主体（§9ter 是本模块唯一新增章节，Phase 4 添加）
- `agent_instructions/issue_writing_protocol.md`
- `agent_instructions/semantic_check_protocol.md`
- `references/*.md`

只添加：
- 视觉证据在 `student_evidence` 中的**结构化表达**
- 视觉证据参与 KB-A / KB-B 的**门禁规则**（Phase 4 完整定义）
- 视觉结果参与判红/黄/灰的**门槛细则**（Phase 4 落到 evidence_requirement.md §9ter）

---

## 2. 三级运行模式

见主计划书 v0.2 §2。本骨架仅记录：

- Core 模式：视觉全关，PDF 分诊仍执行（不做 OCR）
- Local Vision：PaddleOCR PP-StructureV3
- Cloud Enhanced：火山方舟多模态 Provider

---

## 3. PDF 输入礼仪（Phase 4 完整实现）

**10 条核心规则**（追加补齐清单原文）：

1. Word 始终是推荐标准输入
2. PDF 属于支持格式，不因格式拒绝处理
3. 先分诊，再生成针对性提示
4. 提示说明能力边界，默认继续处理
5. Core / Local / Cloud 分别说明实际可用能力
6. 无法可靠识别的视觉内容必须降灰，**不得强行判红**
7. 报告显示 PDF 覆盖率、成功识别、未覆盖内容
8. Word + PDF：Word 用于内容解析，PDF 用于最终版视觉复核
9. Word 与 PDF 冲突时不得静默选择，必须提示用户确认
10. 礼貌提醒每任务原则上只出现一次

Phase 4 完整落地为 Agent 首回复模板 + 报告首页静态声明。

---

## 4. 视觉证据的结构化对象（Phase 4 完整实现）

**目标结构**（骨架预告）：

```json
{
  "source_type": "vision",
  "parsed_text": "...",
  "page_number": 12,
  "bbox": [...],
  "artifact_ref": "path or null",
  "provenance": {...},
  "quality_profile": {...},
  "requires_visual_review": true,
  "review_notice": "视觉解析结果，请核对原图"
}
```

**红线**：不得在 evidence 正文中硬编码警告语，只用 `review_notice` 字段承载，由报告渲染器展示。

---

## 5. KB-A / KB-B 门禁（走 `scripts/vision/knowledge_bridge.py`）

Phase 4 引入 `knowledge_bridge.py`，`build_reference_card.py` **0 改动**。

门禁字段（Phase 4 落地）：
- `kb_a_query_eligible`：所有 vision 结果均可用于 KB-A 查询
- `kb_a_evidence_eligible`：**只有高质量** vision 结果才能作为 issue 依据
- `kb_b_eligible`：高质量 vision 触发 KB-B；低质量不参与

---

## 6. 判级门槛（Phase 4 落到 evidence_requirement.md §9ter）

Phase 4 增补 §9ter 视觉证据强度规则：

- **红色**：`extraction_quality_score ≥ 0.90` + `critical_field_score=1.0` + `hard_gates_passed=true` + 两处独立可读 + 至少一处 DOCX / PDF 原生文本
- **黄色**：`extraction_quality_score ≥ 0.75` + `critical_field_score ≥ 0.7`
- **灰色**：视觉解析失败 / 单模型未验证 / 两处全 Vision / 未解决冲突

**M3.1 硬约束**：两处证据全 Vision 时 **不自动判红**。

---

## 7. 隐私授权（Phase 3 完整实现）

- 两级授权：`.env` 部署者门禁 + 用户会话首次同意
- 默认只上传 bbox 裁剪 + 少量上下文
- 整页上传：需 `ALLOW_FULL_PAGE_UPLOAD=true` + 用户再次授权
- 临时文件：正常模式响应后立即删除；Debug 模式 24h 内清理
- 海外 Provider：M3 不实现

---

## 8. 快照与回退

**基线 tag**：`v1.5.0-pre-m3`
**回退命令**：`git reset --hard v1.5.0-pre-m3`

---

**当前进度**：Phase 1 骨架 · 完整规则在 Phase 4 落地
**主计划书**：`plans/M3_多模型视觉计划书_v0.2.md`
**Build Gate 修订**：`plans/BUILD_GATE_ADDENDUM.md`
