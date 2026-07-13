# Benchmark 数据隔离策略（M4）

**约束级别**：硬红线 · Phase B 起生效
**上游**：`plans/M4_BUILD_GATE_ADDENDUM.md` §3

---

## 一、三个隔离层

### 1.1 目录隔离

| 数据类别 | 目录 | 允许被谁读 |
|---|---|---|
| Benchmark 样本（真实私有） | `benchmarks/documents/private_local_manifest/*` + `benchmarks/internal/` | 只读 by runners/ |
| Benchmark 夹具（合成/开源） | `benchmarks/fixtures/` + `benchmarks/documents/public_synthetic/` + `benchmarks/documents/open_license/` | 可公开分发 |
| KB-A 规范 | `knowledge_base/norms/` | Skill 生产链路 + runners/ 只读 |
| KB-B 范例 | `knowledge_base/examples/` | Skill 生产链路 + runners/ 只读 |

### 1.2 入库脚本互斥

`scripts/kb_ingest.py` 必须显式拒绝任何 `benchmarks/` 路径。已由 CI grep 断言保护。

### 1.3 生产代码去污染

**禁止**在 `scripts/`、`rules/`、`agent_instructions/`、`references/` 中出现：
- 硬编码 `sample_id`（如 `S01`, `S02`, `R001`）
- 硬编码测试论文标题、作者名（张弘济、金融学院等）
- 根据文件名的 if 分支特殊逻辑

**CI 断言**（`.github/workflows/benchmark-offline.yml`）：
```bash
grep -RnE '(sample_id\s*==\s*"[SDRQV][0-9]{2,3}|张弘济|_zhc_)' \
     scripts/ rules/ agent_instructions/ references/
```
命中 → RED，PR 不得合并。

---

## 二、Benchmark 样本禁止用途

以下用途默认全部禁止，除非用户书面二次授权：

- ❌ 自动进入 KB-A / KB-B
- ❌ 用作 KB-B 优秀论文范例
- ❌ 用于 Ark 模型微调 / 提示词训练
- ❌ 用于公开演示 / 火山杯 PPT / 对外宣传（除非脱敏后的问题片段）
- ❌ 打包进公开 Skill 交付物 zip

---

## 三、审计流程

- 每次合并到 main 前，CI 自动执行 §1.3 grep 断言
- 每次 Benchmark 样本入库前，`sample_manifest.yaml` 必须完成，`allowed_uses` 明确布尔值
- 每半年一次人工审计 `knowledge_base/examples/metadata/*.yaml` 与 `benchmarks/documents/*` 目录差集
- 授权撤销时：删除私有原文 + Benchmark 中相关 fingerprint + KB-B 中相关条目

---

## 四、违规处置

- 发现"生产代码根据 sample_id 输出特殊结果"：视为 **测试集污染**，回退该 commit，CHANGELOG 记录事件
- 发现 Benchmark 私有论文进入 Git 公开仓库：立即 `git rm` + `git rebase` + 强推清理历史 + 联系 GitHub 支持
- 发现 Benchmark 样本被用作 KB-B：审查是否有独立授权，无 → 从 KB-B 撤下

---

## 五、判定原则

> **Benchmark 是给 Skill 出的考试题，不是 Skill 学习的教科书。**
> 考试题不能被学生看到，教科书才可以。当二者被混用，考试就失去意义。
