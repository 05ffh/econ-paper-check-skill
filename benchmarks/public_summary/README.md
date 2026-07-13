# benchmarks/public_summary/

**用途**：面向普通用户和火山杯评委的**简化质量摘要**。

## 硬约束

- ❌ 不含学生原文、姓名、学号、学校、私有样本路径
- ❌ 不含模型原始响应、API Key、内部错误栈、账户费用
- ❌ 不做绝对准确率宣称（见 `benchmarks/policies/PUBLIC_CLAIMS_POLICY.md`）
- ✅ 只披露：版本号、样本量、覆盖场景、回归状态、耗时区间

## 文件

- `SCORECARD.md`：每次发布正式版时人工审核后更新
- 生成建议脚本（Phase D 落地）：`benchmarks/runners/build_public_summary.py`
  自动从 `benchmarks/baselines/<active>/` 读取，去除敏感字段后渲染

## 更新时机

- rc.1 阶段：Scorecard 为**空壳**，标注"候选版"
- v1.7.0 发布前：由用户人工审阅后填充数值 + 更新至最终版
- 后续每次 patch：只更新版本号 + 验证日期 + 回归状态，不重复描述能力
