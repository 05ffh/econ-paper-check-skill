#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doctor.py · M3 v1.6.0 环境自检工具

Phase 1 骨架：只做 basic + configuration + storage + secret_scan 四组。
Phase 2/3 陆续接入 local_vision / cloud_vision / model_files / benchmark 等分组。

设计原则（v0.2 §12 + BUILD_GATE_ADDENDUM 修订 3）：
- doctor **只做环境检查**，不选择模式（模式由 mode_resolver 决定）
- **默认不发起收费模型调用**
- `doctor --online` 时才用**合成图片**测试云端连接（本 Phase 未实现）
- JSON 输出必含：requested_mode / effective_mode / degradation_reason / privacy / benchmark_status
- 状态语义：requested == effective 时 healthy；降级即 degraded；连 core 都跑不起来 failed

CLI：
    python scripts/doctor.py           # 人类可读
    python scripts/doctor.py --json    # 机器可读
    python scripts/doctor.py --online  # Phase 3+ 支持云端连接测试
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# 允许作为独立脚本运行
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from mode_resolver import resolve_mode, ModeResolution
except ImportError as e:
    print(f"[FATAL] 无法导入 mode_resolver：{e}", file=sys.stderr)
    sys.exit(2)


SKILL_ROOT = SCRIPT_DIR.parent

# 疑似 Key 模式（供 secret_scan 使用）
SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "OpenAI/Anthropic style API key"),
    (re.compile(r"\bak-[A-Za-z0-9]{20,}\b"), "Ark style API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
]


# ============================================================================
# 检查项
# ============================================================================

def _check_basic() -> dict:
    """基础环境检查：Python 版本、平台、Skill 根目录、必备依赖。"""
    checks = {}

    # Python 版本
    py_ver = tuple(sys.version_info[:2])
    checks["python_version"] = {
        "status": "pass" if py_ver >= (3, 10) else "warn",
        "value": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "note": None if py_ver >= (3, 10) else "建议 Python 3.10+",
    }

    # 平台
    checks["platform"] = {
        "status": "pass",
        "value": f"{platform.system()} {platform.release()} ({platform.machine()})",
    }

    # Skill 根目录
    checks["skill_root"] = {
        "status": "pass",
        "value": str(SKILL_ROOT),
    }

    # 核心依赖（软探测）
    for pkg, mod in [
        ("python-docx", "docx"),
        ("pypdf", "pypdf"),
        ("pdfplumber", "pdfplumber"),
        ("pyyaml", "yaml"),
        ("jinja2", "jinja2"),
        ("lxml", "lxml"),
    ]:
        try:
            __import__(mod)
            checks[f"dep_{pkg}"] = {"status": "pass"}
        except ImportError:
            checks[f"dep_{pkg}"] = {"status": "missing", "note": f"pip install {pkg}"}

    # M1 知识库存在性
    kb_a_dir = SKILL_ROOT / "knowledge_base" / "norms"
    kb_a_citation = kb_a_dir / "citation" / "gb_t_7714_2015.yaml"
    kb_a_methods = kb_a_dir / "methods" / "wooldridge_econometrics.yaml"
    kb_b_active = SKILL_ROOT / "knowledge_base" / "vector_db" / "active"

    checks["kb_a_citation"] = {
        "status": "pass" if kb_a_citation.exists() else "missing",
        "value": str(kb_a_citation.relative_to(SKILL_ROOT)),
    }
    checks["kb_a_methods"] = {
        "status": "pass" if kb_a_methods.exists() else "missing",
        "value": str(kb_a_methods.relative_to(SKILL_ROOT)),
    }
    checks["kb_b_active_dir"] = {
        "status": "pass" if kb_b_active.exists() else "missing",
        "value": str(kb_b_active.relative_to(SKILL_ROOT)),
    }

    # 判断内核
    for f in ["SKILL.md", "arkclaw.yaml"]:
        p = SKILL_ROOT / f
        checks[f"core_file_{f}"] = {
            "status": "pass" if p.exists() else "missing",
        }

    return checks


def _check_configuration() -> dict:
    """配置文件与 .env 状态。"""
    checks = {}

    # .env.example
    env_example = SKILL_ROOT / ".env.example"
    checks["env_example"] = {
        "status": "pass" if env_example.exists() else "missing",
    }

    # .env 是否存在（不 fatal，Phase 1 允许无 .env）
    env_file = SKILL_ROOT / ".env"
    checks["env_file"] = {
        "status": "pass" if env_file.exists() else "info",
        "note": None if env_file.exists() else "未创建 .env（Phase 1 Core 模式无需）",
    }

    # config/default.yaml（Phase 1 未创建）
    default_yaml = SKILL_ROOT / "config" / "default.yaml"
    checks["default_yaml"] = {
        "status": "pass" if default_yaml.exists() else "info",
        "note": None if default_yaml.exists() else "Phase 2 创建",
    }

    # 关键运行开关（读环境变量，展示配置状态）
    checks["runtime_mode_env"] = {
        "status": "info",
        "value": os.getenv("RUNTIME_MODE", "core (默认)"),
    }

    return checks


def _check_storage() -> dict:
    """存储可写性检查。"""
    checks = {}

    # 各关键目录
    for d in [
        SKILL_ROOT,
        SKILL_ROOT / "knowledge_base",
        SKILL_ROOT / "knowledge_base" / "logs",
    ]:
        try:
            testfile = d / ".doctor_write_test"
            testfile.write_text("ok", encoding="utf-8")
            testfile.unlink()
            checks[f"writable_{d.name}"] = {"status": "pass"}
        except Exception as e:
            checks[f"writable_{d.name}"] = {"status": "fail", "note": str(e)}

    # 磁盘剩余空间（软探测）
    try:
        st = os.statvfs(str(SKILL_ROOT))
        free_gb = (st.f_bavail * st.f_frsize) / (1024**3)
        checks["disk_free_gb"] = {
            "status": "pass" if free_gb > 2 else "warn",
            "value": f"{free_gb:.1f} GB",
            "note": None if free_gb > 2 else "剩余空间偏低",
        }
    except Exception:
        checks["disk_free_gb"] = {"status": "info", "value": "unknown"}

    return checks


def _check_privacy() -> dict:
    """隐私开关状态。"""
    return {
        "allow_cloud_upload": (
            os.getenv("ALLOW_CLOUD_UPLOAD", "false").lower() == "true"
        ),
        "allow_full_page_upload": (
            os.getenv("ALLOW_FULL_PAGE_UPLOAD", "false").lower() == "true"
        ),
        "allow_overseas_provider": (
            os.getenv("ALLOW_OVERSEAS_PROVIDER", "false").lower() == "true"
        ),
        "delete_temp_visual_files": (
            os.getenv("DELETE_TEMP_VISUAL_FILES", "true").lower() == "true"
        ),
        "visual_artifact_retention_hours": int(
            os.getenv("VISUAL_ARTIFACT_RETENTION_HOURS", "0") or "0"
        ),
        "debug_keep_raw_response": (
            os.getenv("DEBUG_KEEP_RAW_RESPONSE", "false").lower() == "true"
        ),
    }


def _check_security() -> dict:
    """安全检查：.env 是否被 git 跟踪、日志开关。"""
    checks = {}

    # .env 是否被 git 跟踪
    try:
        r = subprocess.run(
            ["git", "-C", str(SKILL_ROOT), "ls-files", ".env"],
            capture_output=True, text=True, timeout=5,
        )
        checks["env_gitignored"] = {
            "status": "pass" if not r.stdout.strip() else "fail",
            "note": "✅ .env 未被 git 跟踪" if not r.stdout.strip()
                    else "⚠️ .env 被 git 跟踪，立即从 index 移除",
        }
    except Exception as e:
        checks["env_gitignored"] = {"status": "info", "note": str(e)}

    # 日志设置
    checks["log_full_model_response"] = {
        "status": "pass" if os.getenv(
            "LOG_FULL_MODEL_RESPONSE", "false"
        ).lower() == "false" else "warn",
        "value": os.getenv("LOG_FULL_MODEL_RESPONSE", "false"),
    }

    # 临时文件删除开关
    checks["delete_temp_visual_files"] = {
        "status": "pass" if os.getenv(
            "DELETE_TEMP_VISUAL_FILES", "true"
        ).lower() == "true" else "warn",
        "value": os.getenv("DELETE_TEMP_VISUAL_FILES", "true"),
    }

    return checks


def _check_secret_scan() -> dict:
    """扫描代码目录中疑似 API Key 的模式。"""
    hits = []
    scan_dirs = [SKILL_ROOT / "scripts", SKILL_ROOT / "config"]
    for d in scan_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in (".py", ".yaml", ".yml", ".json", ".md", ".sh"):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat, desc in SECRET_PATTERNS:
                for m in pat.finditer(content):
                    hits.append({
                        "file": str(f.relative_to(SKILL_ROOT)),
                        "type": desc,
                        "match_preview": m.group(0)[:8] + "…",
                    })
    return {
        "status": "pass" if not hits else "fail",
        "hits": hits,
        "scanned_dirs": [str(d.relative_to(SKILL_ROOT)) for d in scan_dirs if d.exists()],
    }


# Phase 2+ 才实现的检查（占位）

def _check_local_vision() -> dict:
    """Local Vision 检查（Phase 2 完整实现）。"""
    return {
        "status": "not_implemented",
        "note": "Phase 2 启用",
    }


def _check_cloud_vision(online: bool) -> dict:
    """Cloud Vision 检查（Phase 3 完整实现）。"""
    checks = {
        "ark_api_key": {"status": "pass" if os.getenv("ARK_API_KEY") else "missing"},
        "ark_base_url": {"status": "pass" if os.getenv("ARK_BASE_URL") else "missing"},
        "ark_vision_model_id": {"status": "pass" if os.getenv("ARK_VISION_MODEL_ID") else "missing"},
    }
    if online:
        checks["online_ping"] = {
            "status": "not_implemented",
            "note": "Phase 3+ 实现（合成图片测试连接，不上传学生论文）",
        }
    return checks


def _check_pdf_runtime() -> dict:
    """PDF 运行时检查。"""
    checks = {}
    try:
        import pdfplumber  # noqa
        checks["pdfplumber"] = {"status": "pass"}
    except ImportError:
        checks["pdfplumber"] = {"status": "missing"}
    try:
        import pypdf  # noqa
        checks["pypdf"] = {"status": "pass"}
    except ImportError:
        checks["pypdf"] = {"status": "missing"}
    return checks


def _check_model_files() -> dict:
    """模型文件检查（Phase 2 生效）。"""
    return {"status": "not_implemented", "note": "Phase 2 生效"}


def _check_benchmark() -> dict:
    """Benchmark 状态检查（Phase 5 生效）。"""
    fixtures = SKILL_ROOT / "tests" / "vision" / "fixtures"
    return {
        "status": "pass" if fixtures.exists() else "info",
        "fixtures_dir_exists": fixtures.exists(),
        "last_run": None,
        "note": "Phase 5 完整生效",
    }


def _check_dependency_conflicts() -> dict:
    """依赖冲突检查（pip check）。"""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True, text=True, timeout=30,
        )
        ok = (r.returncode == 0)
        return {
            "status": "pass" if ok else "warn",
            "output": (r.stdout + r.stderr).strip()[:500],
        }
    except Exception as e:
        return {"status": "info", "note": str(e)}


# ============================================================================
# 主流程
# ============================================================================

def run_doctor(online: bool = False, requested_mode: Optional[str] = None) -> dict:
    checks = {
        "basic": _check_basic(),
        "configuration": _check_configuration(),
        "storage": _check_storage(),
        "pdf_runtime": _check_pdf_runtime(),
        "local_vision": _check_local_vision(),
        "cloud_vision": _check_cloud_vision(online=online),
        "model_files": _check_model_files(),
        "benchmark": _check_benchmark(),
        "security": _check_security(),
        "secret_scan": _check_secret_scan(),
        "dependency_conflicts": _check_dependency_conflicts(),
        "privacy": _check_privacy(),
    }

    # 模式解析
    resolution = resolve_mode(requested_mode=requested_mode)

    # 顶层状态：doctor 复用 mode_resolver 的 status
    overall = resolution.status

    warnings = []
    suggestions = []
    for group, group_checks in checks.items():
        if group == "privacy":
            continue
        if isinstance(group_checks, dict) and group_checks.get("status") == "fail":
            warnings.append(f"[{group}] {group_checks.get('note', '')}")
            continue
        if isinstance(group_checks, dict):
            for name, item in group_checks.items():
                if not isinstance(item, dict):
                    continue
                if item.get("status") == "fail":
                    warnings.append(f"[{group}.{name}] {item.get('note', '')}")
                elif item.get("status") == "missing":
                    suggestions.append(f"[{group}.{name}] {item.get('note') or '缺失'}")

    result = {
        "status": overall,
        "requested_mode": resolution.requested_mode,
        "effective_mode": resolution.effective_mode,
        "degradation_reason": resolution.degradation_reason,
        "available_modes": resolution.available_modes,
        "recommended_mode": resolution.effective_mode,
        "checks": checks,
        "warnings": warnings,
        "suggestions": suggestions,
        "benchmark_status": {
            "last_version": None,
            "note": "Phase 5 生效",
        },
    }
    return result


def _format_human(res: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("经管论文智检 Skill · 环境自检 (M3 v1.6.0)")
    lines.append("=" * 60)
    lines.append(f"整体状态：{res['status']}")
    lines.append(f"请求模式：{res['requested_mode']}")
    lines.append(f"实际模式：{res['effective_mode']}")
    if res.get("degradation_reason"):
        lines.append(f"降级原因：{res['degradation_reason']}")
    lines.append(f"可用模式：{res['available_modes']}")
    lines.append("")
    lines.append("--- 检查详情 ---")
    for group, items in res["checks"].items():
        lines.append(f"\n[{group}]")
        if isinstance(items, dict):
            for k, v in items.items():
                if isinstance(v, dict):
                    st = v.get("status", "?")
                    icon = {"pass": "✅", "warn": "⚠️", "fail": "❌",
                            "missing": "❌", "info": "ℹ️", "not_implemented": "⏳"}.get(st, "•")
                    val = v.get("value", v.get("hits", ""))
                    note = v.get("note", "")
                    lines.append(f"  {icon} {k}: {st} {val} {note}".rstrip())
                else:
                    lines.append(f"  · {k}: {v}")
        else:
            lines.append(f"  {items}")
    if res.get("warnings"):
        lines.append("")
        lines.append("⚠️ Warnings:")
        for w in res["warnings"]:
            lines.append(f"  - {w}")
    if res.get("suggestions"):
        lines.append("")
        lines.append("💡 Suggestions:")
        for s in res["suggestions"][:10]:
            lines.append(f"  - {s}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="M3 Doctor · 环境自检")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--online", action="store_true",
        help="启用云端连接测试（Phase 3+）。合成图片，不上传学生论文。",
    )
    parser.add_argument("--mode", default=None, help="覆盖 RUNTIME_MODE 检查")
    args = parser.parse_args()

    res = run_doctor(online=args.online, requested_mode=args.mode)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(_format_human(res))

    sys.exit(0 if res["status"] != "failed" else 1)


if __name__ == "__main__":
    main()
