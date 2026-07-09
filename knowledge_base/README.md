# 知识库对接（第二阶段）

本目录用于存放论文规范源文件，供在 ArkClaw / OpenClaw 平台导入成知识库后，
由 skill 在判断阶段通过 `@知识库名` 检索引用。

## 计划纳入的规范源文件

- `paper_writing_norms.md` —— 本科论文结构、摘要、关键词、图表规范
- `gbt7714_citation.md` —— GB/T 7714 参考文献著录格式
- `empirical_method_norms.md` —— 面板/回归/DID/中介/熵值法各自应交代的要点
- `school_template.md` —— 学院论文模板与格式要求

## ArkClaw / OpenClaw 生态对接方案

按可用性优先级选择：

### 方案 1：byted-knowledge-center-aisearch（推荐）

字节内网环境已内置的智能检索 skill，覆盖 Viking 知识库、飞书文档、钉钉、
数据库多源检索。使用方式：

1. 在 Viking 知识库控制台新建"经管论文写作规范"知识库，上传本目录 md 文件
2. 在 SKILL.md 判断阶段命中"参考文献格式核对"或"方法规范核对"时，调用
   `byted-knowledge-center-aisearch` skill，query 传入具体需求
3. 检索结果作为 evidence 的补充证据（不覆盖论文原文证据，仅作规范对照）

### 方案 2：lark-wiki

若在飞书生态下运行，可把规范源文件建成飞书 Wiki，通过 `lark-wiki` skill 检索。

### 方案 3：自建 RAG（离线场景）

不方便对接云端知识库时，可用本目录 md + 本地向量库（如 chroma / faiss）构建
最小 RAG，配合 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 之类
的轻量嵌入模型。这一分支保留为长期路线，第一版不强制。

## 迁移说明

云端知识库无法随 zip 打包。拿到本 skill 包的人，按上述方案之一自行导入本目录
源文件即可，不会出现断链引用。第一版检测规则已内置于 `rules/`，无知识库也能
完整运行。
