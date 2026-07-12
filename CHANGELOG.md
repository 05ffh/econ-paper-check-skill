# CHANGELOG

本文件按 [Keep a Changelog](https://keepachangelog.com/) 规范维护，从 **v1.5.0** 开始正式记录。

> ⚠️ v1.0 - v1.4 的详细变更历史仅在 Git commit 中留存，不在本文件中追认。如需完整追溯：
>
> ```bash
> git log --oneline
> git show <commit>
> ```

---

## [Unreleased] - Phase 1 骨架进行中

### Added
- Phase 1 骨架完成（v1.6.0-rc.1）：
  - `scripts/mode_resolver.py`：三级模式解析器，含 requested/effective 双字段
  - `scripts/doctor.py`：环境自检工具（basic/configuration/storage/pdf_runtime/security/secret_scan/privacy 分组）
  - `scripts/vision/document_triage.py`：PDF 页级分诊器（Core 模式即可执行，不做 OCR）
  - `agent_instructions/vision_protocol.md`：视觉协议骨架
  - `.env.example`：三级模式配置示例（含隐私开关与 Debug 模式开关）
  - `.gitignore`：补 `.env` / `.cache/` / `*.bundle` 等 M3 相关排除
- 依赖五拆：
  - `requirements-core.txt`（DOCX + PDF 文本层，零视觉零向量库）
  - `requirements-kb.txt`（Chroma + sentence-transformers，KB-B 可选启用）
  - `requirements-vision-local.txt`（PaddleOCR 3.x，Phase 2 才装）
  - `requirements-vision-cloud.txt`（火山方舟 SDK，Phase 3 才装）
  - `requirements-dev.txt`
- `constraints-py311.txt`：**由 Python 3.11.15 真实虚拟环境安装通过后生成**（uv 生成）
- 目录结构新增：`scripts/vision/` `config/vision/` `policies/` `tests/vision/`
- 计划书与治理：
  - `plans/M3_多模型视觉计划书_v0.2.md`（1422 行，59KB）
  - `plans/BUILD_GATE_ADDENDUM.md`（六项 Build Gate 修订）
  - `plans/prebuild_baseline_report.md`（Build 前基线登记）

### Snapshots
- Git tag `v1.5.0-pre-m3` 作为 M3 Build 回退基线
- rsync 全量目录快照：`snapshots/econ-paper-check-skill_v1.5.0-pre-m3_20260712T153944/`（55MB）
- Git bundle：`snapshots/econ-paper-check-skill_v1.5.0-pre-m3.bundle`（187KB）
- KB-B 向量库快照：`snapshot_v1.5.0-pre-m3_20260712T074001Z`（18MB）

### Verified
- Python 3.11.15 干净虚拟环境安装 requirements-core.txt 成功
- Core 模式冒烟测试全部通过：
  - `mode_resolver.py`：requested=core → effective=core → status=healthy
  - `mode_resolver.py`：requested=cloud_enhanced 无 Key → status=degraded + 明确降级原因
  - `doctor.py --json`：输出全部 12 检测分组
  - `document_triage.py`：正确分类 text/mixed 页并输出文档级 recommended_mode
  - `parse_docx.py` / `parse_pdf.py`：M1 原生解析在 Core 依赖下完整可用

### Bounded Scope (Phase 1)
Phase 1 严格边界：
- ❌ 未引入 PaddleOCR / paddlepaddle
- ❌ 未引入 volcengine SDK
- ❌ 未改动 `rules/` / `references/`
- ❌ 未改动 `evidence_requirement.md`（§9ter 增补留 Phase 4）
- ❌ 未改动 `build_reference_card.py` / `kb_query.py` / `kb_admin.py`
- ✅ 仅新增 `vision_protocol.md` 骨架

---

## [1.5.0] - 2026-07-11

### Added
- M1 知识库模块收尾完成
- `scripts/kb_admin.py`（507 行）· 8 子命令 CRUD/快照/回滚/verify
  - `status` / `list` / `show` / `delete` / `snapshot` / `snapshots` / `rollback` / `verify`
  - 破坏性操作强制 `--yes`；rollback 前自动 pre-rollback 快照
- KB-A 规范层首批录入：
  - `knowledge_base/norms/citation/gb_t_7714_2015.yaml`（9 条国标，8 red + 1 yellow）
  - `knowledge_base/norms/methods/wooldridge_econometrics.yaml`（9 条教材，全 yellow_soft）
- `scripts/kb_query.py` A 路由实现：
  - 字符 2-gram 匹配 + stopword_bigrams 二次过滤
  - `min_score >= 2` 门槛
- `scripts/build_reference_card.py` 增加 `search_norm_basis` + `build_norm_basis_md`
  - ISSUE_TYPE_TO_KBA_DOMAIN 白名单机制（反常识过滤）
- `scripts/e2e_demo.py` v2：5 mock issue 端到端演示

### Changed
- `arkclaw.yaml`：1.4.0 → 1.5.0

### Verified
- KB-B verify：ledger 20 篇 · chroma 2198 chunks · 0 issues
- e2e_demo v2：4/5 命中正确条款 + 1 正确拒绝（反常识过滤生效）

### Commits
- `7286998` feat(v1.5): M1 收尾 · kb_admin CRUD/快照/回滚 + KB-A 首批规范录入 + A 路由实现

---
