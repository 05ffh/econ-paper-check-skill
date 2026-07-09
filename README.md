# 经管论文智检 Skill

> 广东金融学院火山杯智能体创新大赛 · 方向二（科研工具与代码开发类 · 论文校对）参赛作品

面向**经管类本科论文提交前自检**的原生 Skill 包，兼容 ArkClaw / Claude Code / OpenClaw。学生上传 `.docx` 论文，Skill 自动识别论文类型与研究方法、条件触发检测规则、逐项语义判断问题，并生成一份正式的 `.docx` 质检报告。

它不是查重工具，也不是论文代写工具，而是一份帮助学生在提交前发现结构、数据、变量、模型与规范风险的"体检报告"。

---

## 核心设计理念

**脚本做 I/O，大模型做判断。** 这是本 Skill 与普通"关键词匹配脚本"的根本区别：

- 二进制 `.docx` 的解析与报告渲染，交给确定性的 Python 脚本；
- "研究问题是否清晰""中英文摘要是否一致""结论方向是否与回归表矛盾"这类需要理解力的判断，交给大模型，并由规则库、证据门禁和语义判断协议严格约束。

配套三项方法论保证质量：

1. **先画像，后触发**：先识别论文类型与已用方法，再条件触发规则。未用 DID 不查 DID，案例论文不强套回归，避免"硕博化"误判。
2. **证据门禁**：无原文证据不输出；弱证据转"需人工确认"；红色必改问题必须有强证据且可定位。
3. **红黄绿灰分级 + 强制判定标准**：硬伤一律判红不得降级，总体风险按阈值映射，尽量保证不同智能体对同一论文得出一致结论。

---

## 一句话流程

```
用户上传 DOCX
  → parse_docx.py 解析成带定位的 paper_text.json
  → 大模型（读 rules/ + references/ + agent_instructions/）
     生成论文画像 → 条件触发 → 五大诊断域语义判断 → diagnostic_result.json
  → render_report.py 渲染成 11 章节 DOCX 报告
  → 对话区展示结构化摘要 + 提供报告下载
```

## 五大诊断域

1. 选题与研究问题质检
2. 文献综述与理论链条质检
3. 数据、变量与口径质检
4. 方法模型与实证结果质检
5. 结构表达与学术规范质检

## 分级体系

| 等级 | 含义 | 门槛 |
|---|---|---|
| 🔴 红色 | 必改问题 | 强证据、可定位、影响核心质量 |
| 🟡 黄色 | 建议补充 | 有基础但说明不充分 |
| 🟢 绿色 | 优化提升 | 不影响核心，仅提升可读性/规范性 |
| ⚪ 灰色 | 需人工确认 | 证据不足 / 图片表格公式 / 导师判断范围 |

---

## 目录结构

```
econ-paper-check-skill/
├── SKILL.md                主入口：定位、边界、执行流程、触发词
├── metadata.json           skill 元信息
├── requirements.txt        唯一依赖 python-docx
├── references/             方法论 schema
│   ├── paper_profile_schema.md   论文画像结构
│   ├── diagnostic_domains.md     五大诊断域说明
│   ├── issue_schema.md           结构化结果 + 分级/风险映射规则
│   └── report_structure.md       11 章节报告结构
├── rules/                  规则库（YAML）
│   ├── rule_registry.yaml        规则注册表与触发顺序
│   ├── non_model_rules.yaml      非模型规则（选题/文献/数据/规范）
│   └── model_rules.yaml          模型规则（面板/DID/IV/中介/熵值法等，条件触发）
├── agent_instructions/     判断协议
│   ├── evidence_requirement.md   证据门禁 + 红色硬伤强制清单
│   ├── semantic_check_protocol.md 语义判断 + 强制交叉核对项
│   └── issue_writing_protocol.md  问题写作与反馈表达规范
├── scripts/                纯 I/O 脚本
│   ├── parse_docx.py             docx → 带定位的 paper_text.json
│   └── render_report.py          diagnostic_result.json → 11 章节 DOCX
├── knowledge_base/         第二阶段知识库源文件与导入说明
├── templates/              报告模板设计规范
└── examples/               示例论文设计规范
```

---

## 安装

```bash
pip install -r requirements.txt
```

唯一依赖 `python-docx`，保证可迁移性。

## 手动跑通（本地调试）

```bash
# 1. 解析论文为结构化 JSON
python scripts/parse_docx.py 论文.docx --out paper_text.json

# 2. 大模型据 paper_text.json + 规则库/协议，产出 diagnostic_result.json（判断层）

# 3. 渲染正式 DOCX 报告
python scripts/render_report.py diagnostic_result.json --out 报告.docx --source 论文.docx
```

## 在 ArkClaw / Claude Code 中使用

导入本 Skill 后，用自然语言触发，无需命令行：

> 请使用经管论文智检 Skill 检测这篇论文，并生成 DOCX 质检报告。

或更具体：

> 请基于经管论文智检 Skill，对这篇本科经管论文做提交前自检，重点检查选题、文献、数据变量、模型方法、结构表达和参考文献规范，最终输出 Word 质检报告。

同时把 `.docx` 论文一起上传。

---

## 边界与免责

- **仅支持 `.docx`**，不支持 PDF、扫描件、图片型论文、数据文件。
- **不做**：查重、论文代写、判断数据真实性、联网核验参考文献真伪。
- **不替代**导师、答辩委员或学校正式评审。
- 模型规则条件触发，**不因论文未使用 DID/IV/PSM 等高级模型而判错**。
- 表述克制：只说"论文中未报告/未呈现/需人工确认"，不说"作者一定没有做"。
- 无法可靠解析的表格、公式、图片一律标注为"需人工确认"，不直接判"缺失"。

---

## 已知限制

- **公式与图片是主要盲区**：`python-docx` 无法解析公式对象与图片型表格，这类内容会被标记为"需人工确认"。真实论文中大量核心方法（如熵值法公式、模型方程）常以公式对象呈现，是当前主要短板。
- **判断质量依赖底层模型**：语义判断由大模型完成，需确保平台使用足够强的模型（如 Claude 系列）以保证交叉核对类问题不被漏检。

## 知识库（第二阶段）

`knowledge_base/` 目录预留了知识库接口。计划纳入论文写作规范、GB/T 7714 引用格式、经管实证方法要点、学院模板等规范源文件，导入平台后由 Skill 通过 `@知识库名` 检索比对，使检测证据可追溯到规范条款。详见 `knowledge_base/README.md`。

---

## 团队协作说明

- 本仓库为团队共享的 Skill 源，成员通过 `git pull` 获取最新版本，无需每次重新打包 zip。
- 修改规则库（`rules/`）或判断协议（`agent_instructions/`）后提交推送，其他成员拉取即可。
- 建议在多个智能体（ArkClaw / Claude Code / OpenClaw）上交叉测试同一篇论文，用结论差异定位规则需收紧之处。
