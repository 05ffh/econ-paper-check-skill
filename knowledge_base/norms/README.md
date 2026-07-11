# KB-A 规范层 · 说明

> **状态**：v1（v1.4+ 起草，随 KB-B 一同上线）
> **定位**：判红黄绿的**权威依据来源**，与 KB-B 范例层严格分离
> **对齐**：补齐清单 P0-3 严格分层 · 原则 1 范例不作错误依据

---

## 1. KB-A vs KB-B（红线区分）

| 维度 | KB-A 规范层 | KB-B 范例层 |
|---|---|---|
| 位置 | `knowledge_base/norms/` + `rules/` | `knowledge_base/vector_db/active/`（Chroma）|
| 内容 | 学校模板 / 国标 / 权威教材 / 已审核规则库 | 20 篇顶刊脱敏论文 chunk |
| 用途 | **判红黄绿的权威依据** | **仅供改进方向参照** |
| 出现在 issue 的字段 | `evidence` / `normative_basis` | `改进参照卡片`（可选） |
| 能否作为错误判定唯一依据 | ✅ 可以 | ❌ 不可以（5 红线之一） |

---

## 2. v1 规范来源登记（KB-A v1）

见 `registry/norm_sources.yaml`。

**v1 已登记来源**：
1. **Skill 已审核规则库**（内置，作者审核，随 Skill 版本管理）
   - `rules/rule_registry.yaml`（v1.1）
   - `rules/non_model_rules.yaml`（结构/规范类）
   - `rules/model_rules.yaml`（方法/模型类）

**v1 暂缺来源**（后续补充）：
- ⏳ 学校学位论文模板 / 撰写规范
- ⏳ 国标 GB/T 7714 参考文献格式
- ⏳ 权威经管方法学教材（如伍德里奇《计量经济学》）
- ⏳ 期刊格式规范（《经济研究》等）

**禁用来源**（严格禁止列为 KB-A 源）：
- ❌ "教育部规范"/"归纳"/"优秀论文总结" 等笼统表述
- ❌ AI 自主生成的规则（必须人工审核后才能列入）
- ❌ 单一学生论文的做法（学生做法不是规范）

---

## 3. 目录规划

```
knowledge_base/norms/
├── README.md              ← 本文件
├── registry/
│   └── norm_sources.yaml  ← 规范源登记表
├── writing/               ← ⏳ 写作规范（学校模板 / 权威教材）
├── citation/              ← ⏳ 引用与参考文献规范（GB/T 7714）
├── methods/               ← ⏳ 方法章节规范（权威教材摘要）
├── figures_tables/        ← ⏳ 图表规范（学校模板 + 期刊格式）
└── summary/               ← ⏳ 摘要规范（学校模板 + 期刊格式）
```

v1 只建目录 + 登记表；实际规范内容 v1.5+ 逐条录入并附**来源信息**（source_type / source_name / source_version / source_locator）。

---

## 4. 每条规范必备的元数据（v1.5+ 录入时强制）

- `norm_id`：全局唯一
- `source_type`：`school_template` | `national_standard` | `authoritative_textbook` | `journal_style` | `skill_audited_rule`
- `source_name`：来源全称（如"GB/T 7714—2015"）
- `source_version`：版本或年份
- `source_locator`：定位（章节号/条款/页码）
- `applicable_scope`：适用范围（本科/硕士/博士 × 论文类型）
- `authority_level`：`red_hard` | `yellow_soft` | `green_suggest`（决定能否判红）
- `copyright_mode`：`public` | `internal_summary`（学校模板通常 internal_summary 只做要点摘录）
- `review_status`：`approved` | `pending`（未审核不上线）

---

## 5. 检索接入

KB-A 检索由 `scripts/kb_query.py` 的 A 路由承载。v1 阶段 A 路由返回空，自动 fallback 到 B（KB-B 范例）。

v1.5+ 起，A 路由查询到规范条款时：
- Route = "A"
- Notice = "规范层结果可作为红黄绿判定依据"
- results 结构与 KB-B 保持一致

---

## 6. 起草时序

- **v1（当前）**：目录 + registry + 声明 rules/ 是已审核规则库，A 路由暂空
- **v1.5**：录入 GB/T 7714 关键条款 → citation/
- **v1.6**：录入学校模板要点（用户提供）→ writing/ + summary/
- **v1.7**：A 路由检索代码实现（结构化条款优先，向量为辅）
- **v2**：与真实报告串通（学生 issue → A 判红 → 引 normative_basis 条款号）
