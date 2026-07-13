# benchmarks/internal/

**用途**：完整私有论文样本的**本地挂载点**，不进公开包。

## 硬约束

- ❌ 目录内所有文件**不入 Git**（已在 `.gitignore`）
- ❌ 不被打包进公开 Skill 交付物 zip
- ❌ 不得从此目录自动入库到 KB-A / KB-B
- ✅ 只能被 `benchmarks/runners/*` 通过 `sample_manifest.yaml` 的 `input_sha256` 引用

## 目录约定

```
benchmarks/internal/
├── S01_zhc_docx/
│   ├── source.docx          # 原始文件（gitignore）
│   └── canonical_result.json # baseline 判定结果（gitignore）
└── S02_zhc_pdf/
    ├── source.pdf
    └── canonical_result.json
```

## 授权链

每个子目录必须对应 `docs/consent/<sample_id>.consent.md`（也 gitignore）。
授权撤销时：
```bash
rm -rf benchmarks/internal/<sample_id>/
# 同步移除 benchmarks/documents/private_local_manifest/<sample_id>.manifest.yaml
```

## 参考

- `plans/M4_BUILD_GATE_ADDENDUM.md` §3
- `benchmarks/policies/DATA_ISOLATION_POLICY.md`
- `benchmarks/policies/FEEDBACK_TO_FIXTURE_POLICY.md`
