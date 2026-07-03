#!/usr/bin/env python3
"""
create_pptx.py  –  Build a styled PPTX from a JSON slide plan.

Usage:
  python create_pptx.py plan.json output.pptx [source.pdf]

Delegates to text2speech.pptx_builder when the package is installed,
otherwise falls back to its own bundled implementation.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path


def _main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    plan_path = Path(sys.argv[1])
    out_path  = Path(sys.argv[2])
    pdf_path  = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    plan      = json.loads(plan_path.read_text())

    try:
        from text2speech.pptx_builder import build_pptx
    except ImportError:
        # Fallback: load the implementation bundled alongside this script
        import importlib.util, os
        spec = importlib.util.spec_from_file_location(
            "_pptx_impl",
            os.path.join(os.path.dirname(__file__), "_pptx_impl.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        build_pptx = mod.build_pptx

    build_pptx(plan, out_path, pdf_path)


if __name__ == "__main__":
    _main()
