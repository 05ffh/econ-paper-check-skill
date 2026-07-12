#!/usr/bin/env bash
# install_paddle.sh · M3 v1.6.0 · Phase 2.5+
#
# 单独安装 PaddleOCR 3.x（CPU-only 默认）。
# 因 paddlepaddle 依赖复杂且体积大，不放入 requirements-vision-local.txt。
#
# 用法：
#   ./scripts/install_paddle.sh           # CPU-only 默认
#   ./scripts/install_paddle.sh --gpu     # GPU 版本（需 CUDA 11.7+）
#   ./scripts/install_paddle.sh --check   # 只检查环境，不安装
#
# 安装位置：当前 Python 环境（建议先激活独立 venv）。
#
# ⚠️ Phase 2 骨架：本脚本仅提供**探测 + 打印步骤**，不实际执行 pip install
# ⚠️ Phase 2.5：完整实施安装（用户显式运行）
#
# 参考：https://github.com/PaddlePaddle/PaddleOCR （3.x 分支）

set -euo pipefail

# ---------- 参数
MODE="cpu"
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --gpu) MODE="gpu" ;;
    --check) CHECK_ONLY=1 ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "未知参数: $arg" >&2
      exit 1 ;;
  esac
done

# ---------- 检测 Python 版本
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[info] Python: $PY_VER"

# PaddleOCR 3.x 官方支持 Python 3.8-3.11
if [[ "$PY_VER" != "3.8" && "$PY_VER" != "3.9" && "$PY_VER" != "3.10" && "$PY_VER" != "3.11" ]]; then
  echo "[warn] PaddleOCR 3.x 官方支持 Python 3.8-3.11，当前 $PY_VER 可能有兼容问题"
fi

# ---------- 检测 pip
if ! python3 -m pip --version > /dev/null 2>&1; then
  echo "[error] 当前 Python 环境未装 pip" >&2
  exit 1
fi
PIP_INDEX="${PIP_INDEX_URL:-https://mirrors.ivolces.com/pypi/simple/}"
PIP_HOST="${PIP_TRUSTED_HOST:-mirrors.ivolces.com}"
echo "[info] pip index: $PIP_INDEX"

# ---------- 检测 GPU
if [[ "$MODE" == "gpu" ]]; then
  if ! command -v nvidia-smi > /dev/null 2>&1; then
    echo "[error] --gpu 但未检测到 nvidia-smi，可能无 GPU" >&2
    exit 1
  fi
  nvidia-smi | head -3
fi

# ---------- 计划输出
echo ""
echo "===== 安装计划 ====="
if [[ "$MODE" == "cpu" ]]; then
  cat <<EOF
1) pip install paddlepaddle==3.0.0             # CPU-only
2) pip install -r requirements-vision-local.txt  # paddleocr[doc-parser] 等
3) python -c "from paddleocr import PaddleOCR; PaddleOCR()"   # 首次会下载模型
EOF
else
  cat <<EOF
1) pip install paddlepaddle-gpu==3.0.0.post117  # GPU（CUDA 11.7）
2) pip install -r requirements-vision-local.txt
3) python -c "from paddleocr import PaddleOCR; PaddleOCR(use_gpu=True)"
EOF
fi

# ---------- Check only
if [[ "$CHECK_ONLY" == "1" ]]; then
  echo ""
  echo "[check-only] 环境探测完成，未执行安装。"
  exit 0
fi

# ---------- Phase 2 骨架保护：默认不执行实际安装
echo ""
echo "===== Phase 2 骨架保护 ====="
cat <<EOF
本 Skill 目前是 v1.6.0-rc.x（Phase 1/2 骨架期），**PaddleOCR 尚未验证**。

如需手动安装（自担风险），请：
1. 激活独立虚拟环境
2. 运行：
   python -m pip install --index-url "$PIP_INDEX" --trusted-host "$PIP_HOST" \\
       paddlepaddle==3.0.0
   python -m pip install --index-url "$PIP_INDEX" --trusted-host "$PIP_HOST" \\
       -r requirements-vision-local.txt
3. 在 .env 中设置 LOCAL_VISION_ENABLED=true

Phase 2.5 起本脚本会切换到自动执行模式。
EOF
