#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经管论文智检 Skill - 统一解析入口。

根据输入文件扩展名自动派发到 parse_docx.py 或 parse_pdf.py，
保证上层 agent 只需要一条命令，不用关心格式判断细节。

用法：
    python scripts/parse_paper.py 论文.docx --out paper_text.json
    python scripts/parse_paper.py 论文.pdf  --out paper_text.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="经管论文智检：DOCX/PDF 统一解析入口")
    parser.add_argument("input", help="论文文件路径（.docx 或 .pdf）")
    parser.add_argument("--out", "-o", help="输出 JSON 路径")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"错误：输入文件不存在：{input_path}", file=sys.stderr)
        return 2

    suffix = input_path.suffix.lower()
    argv = [str(input_path)]
    if args.out:
        argv += ["--out", args.out]

    if suffix == ".docx":
        from parse_docx import main as docx_main
        return docx_main(argv)
    if suffix == ".pdf":
        from parse_pdf import main as pdf_main
        return pdf_main(argv)

    print(
        f"错误：暂不支持的输入格式：{suffix}\n"
        "本 Skill 当前支持 .docx 与 .pdf；扫描件请先做 OCR 或另存为 Word。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    raise SystemExit(main())
