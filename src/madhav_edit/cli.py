"""Command-line interface.

  madhav-edit analyze <screenplay> [--target-runtime 150] [--mock] [--stage 1|full]
  madhav-edit serve [--port 7100]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .config import load_settings
from .orchestrator import run_analysis
from .report import save_outputs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="madhav-edit",
                                     description="Agentic film-editing screenplay analysis")
    sub = parser.add_subparsers(dest="command", required=True)

    p_an = sub.add_parser("analyze", help="Analyze a screenplay (.txt/.md/.pdf/.fountain)")
    p_an.add_argument("screenplay", help="Path to the screenplay file")
    p_an.add_argument("--target-runtime", type=float, default=None,
                      help="Target runtime in minutes")
    p_an.add_argument("--out", default="reports", help="Output directory")
    p_an.add_argument("--mock", action="store_true",
                      help="Offline heuristic mode — tests the pipeline without an API key")
    p_an.add_argument("--stage", choices=["1", "full"], default="full",
                      help="'1' = solo single-agent mode; 'full' = complete swarm (stages 1+2+3)")

    p_srv = sub.add_parser("serve", help="Start the web UI")
    p_srv.add_argument("--port", type=int, default=7100)

    args = parser.parse_args(argv)

    if args.command == "analyze":
        settings = load_settings(mock=args.mock)
        stages = (1,) if args.stage == "1" else (1, 2, 3)
        print(f"Analyzing {args.screenplay} "
              f"({'MOCK mode' if args.mock else settings.model}, stage={'1' if stages == (1,) else 'full'})...")
        result = asyncio.run(run_analysis(args.screenplay, settings,
                                          target_runtime=args.target_runtime, stages=stages))
        md, js = save_outputs(result, args.out)
        print(f"\n✔ Report:  {md}")
        print(f"✔ Data:    {js}")
        print(f"✔ Scenes analyzed: {len(result.scene_analyses)} | "
              f"genre findings: {len(result.genre_findings)} | "
              f"conflicts resolved: {len(result.conflicts)}")
    elif args.command == "serve":
        try:
            import uvicorn
        except ImportError:
            sys.exit("uvicorn not installed — run: pip install -r requirements.txt")
        from .server import app
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
