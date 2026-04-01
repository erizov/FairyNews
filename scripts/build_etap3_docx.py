#!/usr/bin/env python3
"""Собирает Word-отчёт этапа 3 из ``etap3.md`` (через pandoc, если есть)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "etap3.md"
OUT = ROOT / "docs" / "etap3_report.docx"


def main() -> int:
    if not SRC.is_file():
        print("Not found:", SRC, file=sys.stderr)
        return 1
    pandoc = shutil.which("pandoc")
    if not pandoc:
        print(
            "Установите Pandoc: https://pandoc.org/installing.html\n"
            "Затем: pandoc etap3.md -o docs/etap3_report.docx",
            file=sys.stderr,
        )
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        pandoc,
        str(SRC),
        "-o",
        str(OUT),
        "--from=markdown",
        "--to=docx",
    ]
    subprocess.run(cmd, check=True)
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
