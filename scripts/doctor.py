#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doctor.py · M3 v1.6.0-rc.3 · v0.3.1 轻量化

**4 分组结构**（v0.3.1 P0-10 / 第 7 节）：
  [1] 基础依赖         python-docx / pypdf / pdfplumber / pypdfium2 / jinja2 / pyyaml / jsonschema
  [2] 知识库           KB-A(18 条规范) · KB-B(20 篇 · 2198 chunks · 可选)
  [3] 报告组件         render_report / render_report_html / build_reference_card
  [4] 视觉辅助         三态：未配置 ⚪ / 已配置未验证 🟡 / 已验证可用 ✅

设计原则：
- doctor 默认**不联网**（--smoke-test 才发起真实 Ark 调用）
- 未装 vision / kb 依赖不算错误，只是能力缺失
- 输出**用户可见的能力矩阵**，不暴露"模式"术语

CLI：
    python scripts/doctor.py           # 人类可读
    python scripts/doctor.py --json    # 机器可读
    python scripts/doctor.py --smoke-test  # 主动跑一次 Ark 视觉调用
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKDIR = _REPO_ROOT / ".workdir"
_VISION_LAST_VERIFIED = _WORKDIR / ".vision_last_verified"
_SMOKE_FIXTURE = _REPO_ROOT / "tests" / "vision" / "fixtures" / "smoke_synthetic_table.png"
_VERIFIED_WINDOW_SECONDS = 30 * 86400  # 30 天

# ============================================================================
# 工具
# ============================================================================

def _try_import(module_name: str) -> tuple[bool, str]:
    try:
        m = __import__(module_name)
        # Prefer importlib.metadata for canonical version (jsonschema deprecates __version__)
        pkg_name = {
            "docx": "python-docx",
            "yaml": "pyyaml",
            "PIL": "Pillow",
        }.get(module_name, module_name)
        try:
            import importlib.metadata as _im
            ver = _im.version(pkg_name)
        except Exception:
            ver = getattr(m, "__version__", "?")
        return True, str(ver)
    except ImportError:
        return False, ""


# ============================================================================
# [1] 基础依赖
# ============================================================================

def check_core() -> dict:
    checks = {
        "python-docx": _try_import("docx"),
        "pypdf": _try_import("pypdf"),
        "pdfplumber": _try_import("pdfplumber"),
        "lxml": _try_import("lxml"),
        "pyyaml": _try_import("yaml"),
        "jinja2": _try_import("jinja2"),
        "markdown": _try_import("markdown"),
        "pypdfium2": _try_import("pypdfium2"),
        "PIL(Pillow)": _try_import("PIL"),
        "jsonschema": _try_import("jsonschema"),
    }
    missing = [k for k, (ok, _) in checks.items() if not ok]
    status = "ok" if not missing else "fail"
    return {
        "group": "基础依赖",
        "status": status,
        "items": checks,
        "missing": missing,
    }


# ============================================================================
# [2] 知识库
# ============================================================================

def check_kb() -> dict:
    kb_root = _REPO_ROOT / "knowledge_base"
    norms_root = kb_root / "norms"

    # KB-A · 数纯 YAML 条款
    kba_norms = 0
    kba_domains: list[str] = []
    if norms_root.exists():
        for yf in norms_root.rglob("*.yaml"):
            if yf.parent.name == "registry":
                continue
            try:
                import yaml
                with yf.open("r", encoding="utf-8") as fp:
                    data = yaml.safe_load(fp)
                if isinstance(data, dict) and "norms" in data:
                    kba_norms += len(data["norms"] or [])
                    kba_domains.append(yf.parent.name)
            except Exception:
                pass

    kba_status = "ok" if kba_norms > 0 else "missing"

    # KB-B · Chroma 可选
    kbb_available = False
    kbb_reason = ""
    kbb_papers = 0
    try:
        import chromadb  # noqa: F401
        kbb_available = True
        ledger = kb_root / "vector_db" / "active" / "_source_sha_ledger.json"
        if ledger.exists():
            try:
                data = json.loads(ledger.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    kbb_papers = len(data)
            except Exception:
                pass
    except ImportError:
        kbb_reason = "chromadb 未安装（可选：pip install -r requirements-kb.txt）"

    return {
        "group": "知识库",
        "status": "ok" if kba_status == "ok" else "warn",
        "kb_a": {
            "status": kba_status,
            "norms_count": kba_norms,
            "domains": sorted(set(kba_domains)),
        },
        "kb_b": {
            "available": kbb_available,
            "reason": kbb_reason,
            "papers_count": kbb_papers,
        },
    }


# ============================================================================
# [3] 报告组件
# ============================================================================

def check_report() -> dict:
    scripts_dir = _REPO_ROOT / "scripts"
    files = {
        "parse_paper.py": scripts_dir / "parse_paper.py",
        "parse_docx.py": scripts_dir / "parse_docx.py",
        "parse_pdf.py": scripts_dir / "parse_pdf.py",
        "render_report.py": scripts_dir / "render_report.py",
        "render_report_html.py": scripts_dir / "render_report_html.py",
        "build_reference_card.py": scripts_dir / "build_reference_card.py",
        "kb_query.py": scripts_dir / "kb_query.py",
        "kb_admin.py": scripts_dir / "kb_admin.py",
    }
    present = {k: v.exists() for k, v in files.items()}
    missing = [k for k, ok in present.items() if not ok]
    return {
        "group": "报告组件",
        "status": "ok" if not missing else "fail",
        "items": present,
        "missing": missing,
    }


# ============================================================================
# [4] 视觉辅助（三态）
# ============================================================================

def _last_verified_age_seconds() -> Optional[float]:
    if not _VISION_LAST_VERIFIED.exists():
        return None
    try:
        ts = float(_VISION_LAST_VERIFIED.read_text(encoding="utf-8").strip())
        return time.time() - ts
    except Exception:
        return None


def check_vision(smoke_test: bool = False) -> dict:
    reasons: list[str] = []

    vision_enabled = os.getenv("VISION_ENABLED", "false").lower() == "true"
    api_key_set = bool(os.getenv("ARK_API_KEY"))
    model_id = os.getenv("ARK_VISION_MODEL_ID", "")
    base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    if not vision_enabled:
        reasons.append("VISION_ENABLED != true")
    if not api_key_set:
        reasons.append("ARK_API_KEY 未配置")
    if not model_id:
        reasons.append("ARK_VISION_MODEL_ID 未配置")

    # openai SDK
    openai_ok, openai_ver = _try_import("openai")
    if not openai_ok:
        reasons.append("openai SDK 未安装（可选：pip install -r requirements-vision.txt）")

    configured = len(reasons) == 0

    # 三态判定
    if not configured:
        state = "unconfigured"
        icon = "⚪"
        label = "未配置"
    else:
        age = _last_verified_age_seconds()
        if age is not None and age <= _VERIFIED_WINDOW_SECONDS:
            state = "verified"
            icon = "✅"
            label = "已验证可用"
        else:
            state = "configured_unverified"
            icon = "🟡"
            label = "已配置但未验证"

    result = {
        "group": "视觉辅助",
        "status": "ok" if state != "unconfigured" else "info",
        "state": state,
        "icon": icon,
        "label": label,
        "reasons": reasons,
        "config": {
            "vision_enabled": vision_enabled,
            "ark_api_key_set": api_key_set,
            "ark_vision_model_id_set": bool(model_id),
            "ark_base_url": base_url,
            "openai_sdk": openai_ver if openai_ok else None,
            "max_regions_per_document": int(os.getenv("MAX_VISION_REGIONS_PER_DOCUMENT", "40")),
            "timeout_seconds": int(os.getenv("VISION_REQUEST_TIMEOUT_SECONDS", "30")),
        },
    }

    # smoke_test
    if smoke_test:
        if state == "unconfigured":
            result["smoke_test"] = {
                "run": False,
                "skip_reason": "视觉未配置，跳过 smoke_test",
            }
        else:
            result["smoke_test"] = _run_smoke_test()
            # 更新状态
            if result["smoke_test"].get("ok"):
                _WORKDIR.mkdir(parents=True, exist_ok=True)
                _VISION_LAST_VERIFIED.write_text(str(time.time()), encoding="utf-8")
                result["state"] = "verified"
                result["icon"] = "✅"
                result["label"] = "已验证可用"

    return result


def _run_smoke_test() -> dict:
    """用固定合成 PNG 发一次 TABLE_STRUCTURE。"""
    if not _SMOKE_FIXTURE.exists():
        return {
            "run": False,
            "ok": False,
            "error": f"合成 fixture 缺失: {_SMOKE_FIXTURE}",
        }

    # 走 Provider
    try:
        sys.path.insert(0, str(_REPO_ROOT / "scripts" / "vision" / "providers"))
        from ark_provider import ArkCloudProvider
        from base import TaskKind, VisionRequest
    except Exception as e:
        return {"run": False, "ok": False, "error": f"Provider 加载失败: {e}"}

    provider = ArkCloudProvider()
    req = VisionRequest(
        artifact_ref=str(_SMOKE_FIXTURE),
        task_kind=TaskKind.TABLE_STRUCTURE,
        page_number=None,
        bbox=None,
        timeout_seconds=30.0,
    )
    t0 = time.time()
    try:
        resp = provider.recognize(req)
        return {
            "run": True,
            "ok": True,
            "latency_ms": resp.latency_ms,
            "raw_hash": resp.raw_response_hash[:12],
            "n_cells": len(resp.raw.get("cells", [])) if isinstance(resp.raw, dict) else 0,
        }
    except Exception as e:
        return {
            "run": True,
            "ok": False,
            "error": str(e),
            "elapsed_ms": int((time.time() - t0) * 1000),
        }


# ============================================================================
# 汇总输出
# ============================================================================

def render_human(result: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("经管论文智检 Skill · 环境自检 (v1.6.1)")
    lines.append("=" * 60)
    lines.append("")

    # [1]
    c = result["core"]
    icon = "✅" if c["status"] == "ok" else "❌"
    lines.append(f"[1] 基础依赖         {icon} {'全部就绪' if c['status'] == 'ok' else '缺失: ' + ', '.join(c['missing'])}")

    # [2]
    kb = result["kb"]
    kba_icon = "✅" if kb["kb_a"]["status"] == "ok" else "❌"
    kbb_icon = "✅" if kb["kb_b"]["available"] else "⚪"
    kba_line = f"KB-A {kba_icon} {kb['kb_a']['norms_count']} 条规范 · 域: {', '.join(kb['kb_a']['domains']) or '空'}"
    kbb_line = f"KB-B {kbb_icon} " + (
        f"{kb['kb_b']['papers_count']} 篇范例" if kb["kb_b"]["available"] else "未启用（pip install -r requirements-kb.txt 可开启）"
    )
    lines.append(f"[2] 知识库           {kba_line}")
    lines.append(f"                     {kbb_line}")

    # [3]
    r = result["report"]
    icon = "✅" if r["status"] == "ok" else "❌"
    lines.append(f"[3] 报告组件         {icon} {'全部就绪' if r['status'] == 'ok' else '缺失: ' + ', '.join(r['missing'])}")

    # [4]
    v = result["vision"]
    lines.append(f"[4] 视觉辅助         {v['icon']} {v['label']}")
    if v["state"] == "unconfigured":
        for reason in v["reasons"]:
            lines.append(f"                     · {reason}")
    else:
        lines.append(f"                     · Ark model: {os.getenv('ARK_VISION_MODEL_ID', '?')[:20]}…")
        lines.append(f"                     · 单文档配额: {v['config']['max_regions_per_document']} 区域")
        lines.append(f"                     · 单次超时: {v['config']['timeout_seconds']}s")
        if v["state"] == "configured_unverified":
            lines.append("                     · 建议运行: python scripts/doctor.py --smoke-test")

    if "smoke_test" in v:
        st = v["smoke_test"]
        if st.get("ok"):
            lines.append(f"                     · smoke_test: ✅ 通过 ({st['latency_ms']}ms · {st['n_cells']} cells)")
        elif st.get("run"):
            lines.append(f"                     · smoke_test: ❌ {st.get('error', '未知错误')}")

    lines.append("")
    lines.append("=" * 60)

    # 总结
    can_basic = c["status"] == "ok" and kb["kb_a"]["status"] == "ok" and r["status"] == "ok"
    can_kbb = kb["kb_b"]["available"]
    can_vision = v["state"] in ("configured_unverified", "verified")

    lines.append(f"基础论文质检:        {'✅ 可用' if can_basic else '❌ 缺依赖'}")
    lines.append(f"KB-B 范例参照:       {'✅ 可用' if can_kbb else '⚪ 未启用'}")
    lines.append(f"PDF 视觉辅助识别:    {'✅ 可用' if can_vision else '⚪ 未启用（图片区域将降灰）'}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="经管论文智检 Skill · 环境自检 (v0.3.1)")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--smoke-test", action="store_true", help="主动运行 Ark 视觉 smoke test（会真实调用 API）")
    args = ap.parse_args()

    result = {
        "version": "v1.6.1",
        "core": check_core(),
        "kb": check_kb(),
        "report": check_report(),
        "vision": check_vision(smoke_test=args.smoke_test),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_human(result))


if __name__ == "__main__":
    main()
