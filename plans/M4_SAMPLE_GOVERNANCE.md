# M4 · Sample Governance（样本治理规范）

**版本**：v0.2-draft-1
**约束级别**：**硬红线**（违反 = Release Gate 阻止发布）
**引用**：v0.2 主计划书 §3 · P0-7

---

## 一、根本原则

> **"公开可访问 ≠ 可抓取、可入库、可分发、可上传第三方模型"**

无论论文是否可在网上找到，Benchmark 样本必须走**授权 / 合成 / 明确开源许可**三条正式通道之一。**默认禁止**从 CNKI、万方、维普、EBSCO、SSRN、CORE.ac.uk、公开学校数据库等平台自动抓取全文用于 Benchmark。

---

## 二、三种合法样本通道

### 通道 A：用户明确授权提供

**要求**：
- 论文作者本人或经作者书面授权的持有者提供原始文件
- 用户在 `sample_manifest.yaml` 中签名（`owner_or_source` + `license_or_consent_ref`）
- 授权文档留存至 `docs/consent/{sample_id}.consent.md`（Git 忽略，本地保存）
- 明确列出 `allowed_uses`（Benchmark / 云 vision / Git 分发 / 公开 demo）

**默认**：私有真实论文**不入 Git**，只入 `sample_manifest.yaml` + sha256。

### 通道 B：团队自建的合成 / 半合成样本

**要求**：
- 由 ArkClaw + 用户合作生成
- 可以以真实论文为**结构模板**（章节顺序、表格布局），但：
  - **换主题**（如金融→零售、DID→PSM）
  - **换数据**（重新生成数值 / 变量名 / 引用）
  - **换作者名 / 校名 / 学号**
- 生成过程记录到 `sample_manifest.yaml.synthesis_note`
- 可自由入 Git 分发（`allowed_uses.git_distribution: true`）

**用途**：主要用于规则夹具（R001-R010）和 KB 查询夹具（Q001-Q010）。

### 通道 C：明确开放许可样本

**要求**：
- 原始来源公开声明 CC-BY / CC0 / MIT / arXiv 等允许再利用的许可
- 保留许可证明副本至 `docs/licenses/{sample_id}.license.md`
- 在 `sample_manifest.yaml.license_or_consent_ref` 中引用
- 校验点：**许可需明确覆盖"再分发"和"衍生作品"两项**

**注意**：中国境内多数硕博论文的"公开"仅指访问，不含再分发权，不属于通道 C。

---

## 三、sample_manifest.yaml 契约

```yaml
sample_id: "S02_zhc_pdf"
source_type: authorized_private  # authorized_private | synthetic | open_license
owner_or_source: "张弘济（作者本人）"
license_or_consent_ref: "docs/consent/S02_zhc_pdf.consent.md"

allowed_uses:
  benchmark:            true    # 允许作为 Benchmark 样本
  cloud_vision:         false   # 允许上传 Ark 视觉调用（PDF 视觉辅助）
  git_distribution:     false   # 允许入 Git 分发
  public_demo:          false   # 允许作为公开演示

contains_personal_data: false
deidentified_by: "ArkClaw v1.6.2"
deidentification_reviewed_by: "user"
retention_policy: local_only    # local_only | git_public | git_lfs

input_sha256: "<sha256 of source file>"
file_bytes: 1500000
page_count: 24

# 合成样本额外字段
synthesis_note: null   # 或："以张弘济为模板，换主题为绿色债券，换数据 2018-2023 …"

# 追踪与治理
added_at: "2026-07-13"
last_reviewed_at: "2026-07-13"
next_review_at: "2026-10-13"   # 3 个月复审
governance_owner: "user"
```

**必填字段**：`sample_id`, `source_type`, `owner_or_source`, `license_or_consent_ref`, `allowed_uses` (全 4 项), `input_sha256`, `retention_policy`。

---

## 四、张弘济样本（S01/S02）当前状态

| 字段 | 值 |
|---|---|
| sample_id | S01_zhc_docx / S02_zhc_pdf |
| source_type | ⚠️ **待用户确认**：`authorized_private` 还是其它 |
| owner_or_source | 张弘济（广东金融学院本科生） |
| license_or_consent_ref | ⚠️ **待用户签署** `docs/consent/S01_zhc.consent.md` |
| allowed_uses.benchmark | ⚠️ 待确认（默认建议 true） |
| allowed_uses.cloud_vision | ⚠️ 待确认（M3 已实际调用过 Ark，需 retro 授权） |
| allowed_uses.git_distribution | ⚠️ 强烈建议 false（原始 PDF 不入 Git） |
| allowed_uses.public_demo | ⚠️ 待确认 |
| retention_policy | 建议 `local_only` |
| input_sha256 | S02 已知：见 Pre-Build Audit |

**行动项**：用户明确 4 项 `allowed_uses` 后，ArkClaw 自动生成 `sample_manifest.yaml` 与 consent 模板。

---

## 五、脱敏红线（沿用 M1 KB-B 规范 + 强化）

### 5.1 必须脱敏

| 字段 | 处理 |
|---|---|
| 学生姓名 | 替换为 `AUTHOR_{sample_id}` |
| 学校名称 | 替换为 `SCHOOL_{sample_id}` |
| 学号 | 完全删除 |
| 导师姓名 | 替换为 `ADVISOR_{sample_id}` |
| 邮箱 / 手机 / 地址 | 完全删除 |
| 具体地区代码 / 公司代码（附录） | 抽样保留 5-10 条，删除其余 |
| 未发表的第三方数据源联系人 | 完全删除 |

### 5.2 保留

| 字段 | 理由 |
|---|---|
| 论文题目 | Q-C：保留（M1 已决） |
| 参考文献作者名 | Q-A：保留（学术引用中的作者名保留） |
| 公开的政府/学术引用 | 保留 |
| 方法论描述 / 变量定义 | 保留 |

### 5.3 视觉裁剪特别规则

- 只保留表格 / 图 / 公式本身
- **裁掉页眉页脚**（避免暴露学校 / 学号 / 页码水印）
- **裁掉表格上下文**如果暴露具体地区/公司名单
- 每个 vision_crop 单独走 `manifest.yaml`，独立授权

---

## 六、仓库分发策略

### 6.1 可入 Git 分发

- ✅ 合成样本（synthesis）
- ✅ 明确开源许可样本（open_license）
- ✅ 全部 `sample_manifest.yaml`
- ✅ 全部 `expected.yaml`
- ✅ 全部 sha256

### 6.2 不入 Git（仅 `.workdir/` 或本地）

- ❌ 私有真实论文原始文件
- ❌ 私有论文完整 canonical_result.json（可能含正文）
- ❌ 未脱敏的视觉裁剪
- ❌ 云模型完整原始响应（可能含正文回读）
- ❌ `.env.local`
- ❌ Ark API Key / GitHub token

### 6.3 `.gitignore` 强化

Phase A 落地：
```
benchmarks/documents/private_local_manifest/*/source/
benchmarks/documents/private_local_manifest/*/canonical_result.json
benchmarks/runs/*/artifacts/full/
docs/consent/*.consent.md
```

---

## 七、云调用（Ark 视觉）额外约束

**只有 `allowed_uses.cloud_vision: true` 的样本可上传 Ark**。

流程：
```
1. run_single.py 读取 sample_manifest.yaml
2. 如需 vision 且 allowed_uses.cloud_vision == false → 报错，拒绝运行
3. 允许云调用 → 走 upload_policy 校验（4MB / 3000×4000 px）
4. 云调用日志中不含正文（M3 已实现）
```

**违规 = Release Gate 硬阻止**（对应 §10.1 "私有论文进入 CI artifact"）。

---

## 八、审计与复审

- **每 3 个月**：`benchmarks/documents/*/sample_manifest.yaml.next_review_at` 触发复审
- **每次 baseline 晋升**：检查所有活跃样本的 `allowed_uses` 是否仍然有效
- **样本退役**：设置 `retention_policy: retired`，从 baseline 排除，manifest 保留归档

---

## 九、违规响应

| 情形 | 响应 |
|---|---|
| 未签署 consent 就跑 Benchmark | run_single.py 拒绝执行 |
| 未授权就云调用 | run_single.py 拒绝，records failure |
| 私有论文文件被误 commit | pre-commit hook 阻拦 + Release Gate |
| Ark Key / token 泄露到日志 | 日志脱敏 filter + CI 密钥扫描 |
| CI artifact 含正文 | artifact 上传前扫敏 + PR 阻止 |

---

## 十、快速判定表（用户/ArkClaw 决策辅助）

**"这份论文能加入 Benchmark 吗？"**

| 你是谁 | 论文来源 | 判定 |
|---|---|---|
| 论文作者本人 | 自己写的 | ✅ 通道 A：填 consent 后可 |
| 老师 | 学生的作业 | ⚠️ 需学生书面同意，走通道 A |
| 用户 | 从 CNKI 下载的 | ❌ 通道 C 不成立（CNKI 无再分发权） |
| 用户 | 从 arXiv 下载的 | ⚠️ 视具体作者授权（多数 arXiv 是 CC-BY） |
| 团队 | ArkClaw 合成 | ✅ 通道 B：填 synthesis_note 后可 |
| 任何人 | 从贴吧、微博等公开渠道 | ❌ 无授权 |

---

**首版 v0.2 Definition of Done**：
- [ ] `sample_manifest.schema.yaml` 落地 `benchmarks/schema/`
- [ ] S01/S02 完成 consent 签署（用户）
- [ ] 至少 1 个合成样本（D01）落地
- [ ] pre-commit hook 拦截私有论文文件
- [ ] CI 密钥扫描通过
