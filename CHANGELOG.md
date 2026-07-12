# CHANGELOG

本文件按 [Keep a Changelog](https://keepachangelog.com/) 规范维护，从 **v1.5.0** 开始正式记录。

> ⚠️ v1.0 - v1.4 的详细变更历史仅在 Git commit 中留存，不在本文件中追认。如需完整追溯：
>
> ```bash
> git log --oneline
> git show <commit>
> ```

---

## [1.6.0-rc.3] - 2026-07-12 · M3 v0.3.1 轻量化重构

### 重大变更
- 取消三级运行模式（Core / Local Vision / Cloud Enhanced）
- 删除本地 PaddleOCR / paddlepaddle / mode_resolver / Docker
- 唯一视觉 Provider：火山方舟（OpenAI Compatible 接口）
- 依赖从 5 拆瞬身为 4 拆：core / kb / vision / dev
- 环境变量从 12 个瞬身为 6 个
- doctor.py 从 12 分组瞬身为 4 分组

### Removed
- `scripts/mode_resolver.py` (328 行)
- `scripts/vision/providers/paddle_provider.py` (117 行)
- `scripts/install_paddle.sh` (104 行)
- `requirements-vision-local.txt` · `constraints-py311.txt`
- `RUNTIME_MODE` / `LOCAL_VISION_ENABLED` / `LOCAL_MODEL_PATH` / `LOCAL_DEVICE` 等 “模式”相关变量

### Renamed
- `requirements-vision-cloud.txt` → `requirements-vision.txt`

### Added
- `requirements-core.txt` 新增 `pypdfium2` / `Pillow` / `jsonschema`（P0-2 / P1-13）
- `.env.example` 新增 `MAX_VISION_REGIONS_PER_DOCUMENT=40` / `VISION_REQUEST_TIMEOUT_SECONDS=30`（P0-7）
- `plans/M3_多模型视觉计划书_v0.3_轻量化.md`（513 行）
- `plans/M3_v0.3.1_修订与BUILD_GATE.md`（588 行 · 逐条回应 13 项 P0/P1 审阅意见）
- `ark_provider.py` 真实实现：openai SDK 唯一 · 提示注入防护硬编码 · M3.1 仅支持 OCR_REGION + TABLE_STRUCTURE
- `doctor.py` 三态视觉状态（未配置 ⚪ / 已配置未验证 🟡 / 已验证可用 ✅）+ `--smoke-test` 主动验证

### Fixed / Changed
- Ark Provider M3.1 任务收窄为 `OCR_REGION` + `TABLE_STRUCTURE`（P0-4）
- SDK 唯一方案：openai>=1.30（P0-5）
- Python 不再强制 3.11，回到 3.10+ 通行（P0-6）

### 未交付（待 Phase B/C/D）
- `scripts/vision/dispatcher.py` · 配额 + 内嵌 LRU + 超时（P0-7）
- `scripts/vision/upload_policy.py` · 扫描 PDF 不自动上传（P0-3）
- `scripts/prebuild_audit.py` · Phase A 首日产出审计报告（P0-12）
- `tests/vision/test_prompt_injection.py` · 提示注入对抗测试（P1-13）
- 报告包 artifact_id + 相对路径 + 单文件 base64（P0-9）
- 多样本验收集（扫描版 / 图表密集 / DOCX 基线）（P0-11）

### 回退保障
- `git tag v1.6.0-rc.2-legacy-frozen` 已创建
- 一行回退：`git reset --hard v1.6.0-rc.2-legacy-frozen`

---

## [Unreleased] - Phase 2 骨架进行中

### Added (Phase 2 骨架, v1.6.0-rc.2)
- **Provider 抽象层**：
  - `scripts/vision/providers/base.py` (163 行) · BaseVisionProvider + TaskKind + ProviderError + VisionRequest/Response
  - `scripts/vision/providers/paddle_provider.py` (骨架) · PP-StructureV3 探测就绪，`recognize()` 抛 NOT_INSTALLED
  - `scripts/vision/providers/ark_provider.py` (骨架) · 火山方舟多模态 探测就绪，`recognize()` 抛 NOT_CONFIGURED
  - `scripts/vision/providers/mock_provider.py` (166 行) · **单测/骨架用可运行 Provider**，支持全部 TaskKind
- **视觉输出统一 Schema**：
  - `scripts/vision/schemas/vision_output.schema.json` (JSON Schema draft-07)
  - 事实层 = `cells[]`（关键单元格含 row/col/span/text/normalized_value/stars/semantic_role/bbox/variable_column_flag）
  - `derived_views` 只作衍生视图（headers/rows/coefficients_matrix）
  - 公式 = LaTeX + bbox + symbols + image_hash + render_valid + variable_matches（**M3.1 不强制 MathML**）
  - 参考文献 = CSL-JSON 内层 + raw_text/page/bbox/parse_quality 外层
  - 全 Schema 含 schema_version + provenance
- **视觉链路模块**：
  - `scripts/vision/normalizer.py` (240 行) · Provider raw → 统一 Schema
  - `scripts/vision/quality_scorer.py` (330 行) · **系统结构校验产生 extraction_quality_score，禁模型自报 confidence**
  - `scripts/vision/knowledge_bridge.py` (240 行) · KB-A/KB-B 门禁 + student_evidence 结构化打包（`review_notice` 字段承载警告，禁硬编码到 parsed_text）
- **配置外置**：
  - `config/vision/document_triage.yaml` · 分诊阈值配置
  - `config/vision/kb_bridge.yaml` · KB 门禁阈值 + M3.1 硬约束（`pure_vision_evidence_can_be_red: false`）
- **安装脚本**：
  - `scripts/install_paddle.sh` · CPU/GPU 双模式 + `--check` 探测模式；Phase 2 保护模式，默认不自动 pip install
- **doctor 增强**：
  - local_vision / cloud_vision 分组接入 Provider 真实 describe()
- **端到端 pytest 冒烟**：
  - `tests/vision/test_pipeline_smoke.py` (10 用例，全通过)

### Verified (Phase 2 骨架)
- Python 3.12.3（宿主）与 Python 3.11.15（干净 venv）双环境 **10/10 pytest 通过**：
  - MockProvider → normalize → quality_scorer → knowledge_bridge 全链路
  - PaddleProvider / ArkProvider 未启用时正确抛 NOT_INSTALLED / NOT_CONFIGURED
  - student_evidence 结构合规（含 source_type / parsed_text / bbox / provenance / quality_profile / review_notice）
  - 低质量 profile 正确被 KB 门禁拒绝（`kb_a_evidence_eligible=False` / `kb_b_eligible=False`）
- `install_paddle.sh --check` 探测正常，未执行安装（骨架保护模式）

### Bounded Scope (Phase 2 骨架)
- ❌ 未装 paddleocr / paddlepaddle / opencv-python-headless
- ❌ 未装 volcengine-python-sdk
- ❌ Provider `recognize()` 未真跑（仅骨架抛 ProviderError）
- ❌ 未改判断内核（rules/ + agent_instructions 主体 + references/）
- ❌ 未改 build_reference_card / kb_query / kb_admin

---

## [1.6.0-rc.1] - 2026-07-12 (Phase 1 骨架完成)

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

## [1.6.0] - 2026-07-12 · M3 Phase B/C/D 端到端闭环

### 视觉链路真实落地
- **首次真实 Ark 视觉调用成功**：模型 `doubao-seed-2-0-mini-260428`，OpenAI Compatible 接口
- 张弘济初稿 p20 主回归表：pdfplumber 抓乱字符 → Ark 视觉识别 10×3 · 30/30 cells 完美
  - Caption 完整：「表 3 主回归结果：LR对NIM的影响」
  - 变量 LR/NPL/CAR/SIZE/CIR/Constant · 系数+显著性星号+t 统计量准确
  - 单次调用 15.3s · 5316 tokens · ≈ 0.008 元
- 提示注入防护实测生效：confidence/level/red-yellow-gray 禁字段全部未出现

### 新增（Phase B）
- `scripts/vision_pipeline.py`：视觉主链路（PDF 页 → 渲染 → 识别 → normalize → score → knowledge_bridge → student_evidence）
- `scripts/build_end_to_end_report.py`：Phase C 报告构建（判断内核简化版 + 视觉证据挂载）

### 增强（Phase C）
- `scripts/render_report.py`：DOCX 支持视觉证据卡（模型/质量/KB-A 门禁 + 表格预览 + 缩略图插图）
- `scripts/render_report_html.py`：HTML 支持视觉证据块（内联 base64 缩略图 + 表格 + 元信息条 + notice）
- `scripts/vision/normalizer.py`：`_normalize_table` 补 `caption/n_rows/n_cols` 字段

### 端到端验证（Phase D）
- 分支 A（未配 Ark） vs 分支 B（配 Ark）两分支跑通
- **判断内核 diff = 0**：去除视觉证据后两分支完全一致
- **判级一致**：两分支 overall_risk 均"低-中"、issues 主键 `Y-01` 一致
- 分支 B 多出 `G-V20` 视觉灰色 issue（仅供人工核对，不改判级）
- pytest 14/14 全过

### 约束守住
- 判断内核 0 改动（rules/ + agent_instructions/ + references/）
- KB-A/KB-B 0 改动
- Provider 契约：只识别不评分不裁剪不缓存不自报 confidence
- 视觉不作红色唯一依据

## [1.6.1] - 2026-07-12 · M3 收尾 (Round A/B/C/D)

### Round A · 声明层重写
- `SKILL.md § 9`：改写 KB 状态说明（KB-A 18 条已上线 · 三层证据表格化）
- `SKILL.md § 10`：新增视觉辅助识别章节（三态判断 · 硬约束 7 条 · 端到端管线示意）
- `agent_instructions/vision_protocol.md`：从 119 行骨架扩到 339 行完整版
  - § 2 单一运行流程（无模式概念）
  - § 3 PDF 输入礼仪 10 条（含纯扫描 PDF 特殊处理）
  - § 4 视觉证据的结构化对象（source_type=vision/vision_failed）
  - § 5 KB-A/KB-B 门禁三个字段与判定表
  - § 6 判级门槛（含 pure_vision_evidence_can_be_red=false）
  - § 7 隐私授权两级
  - § 8-11 主链路接入 / 快照回退 / 测试 / 参考
- `agent_instructions/evidence_requirement.md § 9ter`：新增 5 小节视觉证据强度规则

### Round B · 工程闭环
- `scripts/vision_pipeline.py`：挂接 `upload_policy`
  - 纯扫描 PDF 全篇降灰（`scan_recommendation`）
  - 图像尺寸/字节数硬阈值校验（`decide_upload`）
  - `--no-full-page-upload` CLI 参数 · `--document-type` 传导
  - 未授权/被拒 → 降灰 `vision_failed`，不消耗 quota
- `tests/vision/test_ark_mock_openai.py`：新增 15 项 Ark Provider Mock 测试
  - 幂等 hash / 系统提示锚定 / M3.1 任务收窄
  - 错误映射 4 类（RateLimit/Auth/Timeout/Connection）
  - JSON 解析兜底 3 场景（```json 包裹 / 垃圾内容 / 空 content）
  - 无 confidence/level/red-yellow 禁字段
- `constraints-tested.txt`：61 行版本锁清单（openai==1.109.1 / pydantic-core==2.46.4 / pypdfium2==5.7.1 等）

### Round C · 归档 & 收尾
- `plans/M3_多模型视觉计划书_v0.3_轻量化.md` → `plans/archive/`（被 v0.3.1 覆盖）
- `plans/M3_v0.3_prebuild_audit.md` → `plans/archive/`
- `scripts/vision/document_triage.py`：删除"推荐模式：core"等 v0.2 遗留字样
  - `recommended_mode` 从 core/local_vision/cloud_enhanced → text_only/vision_optional/vision_recommended/vision_required
  - 页级 coverable_by_mode 同步改写

### Round D · v1.5.0 DOCX 基线 diff 验证
- git worktree 检出 `v1.5.0-pre-m3` 副本
- DOCX (176 KB / 161 units) 分别用 v1.5.0 和 v1.6.0 跑 parse_paper
- **paper_text.json sha256 完全一致**：`5bd30276...ad7e`
- v1.6.0 用 build_end_to_end_report + render_report/html 跑通同一 DOCX 无异常
- 结论：DOCX 全流程 M3 未回归

### 测试
- pytest 29/29 全过（14 老 + 15 新 Ark Mock）

### 约束守住
- 判断内核 0 改动
- KB-A/KB-B 0 改动
- Provider 契约完全守住
- DOCX 全流程零回归（sha256 一致）
