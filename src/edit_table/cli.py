"""Command-line interface.

  edit-table analyze <screenplay> [--tenant ID] [--target-runtime 150] [--mock] [--stage 1|full]
  edit-table tenant list|create|delete ...
  edit-table serve [--port 7100] [--tenants-file tenants.json]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .config import load_settings
from .orchestrator import run_analysis
from .report import save_outputs
from .tenants import DEFAULT_TENANTS_FILE, TenantRegistry


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="edit-table",
                                     description="Agentic film-editing screenplay analysis (multi-tenant)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_an = sub.add_parser("analyze", help="Analyze a screenplay (.txt/.md/.pdf/.fountain)")
    p_an.add_argument("screenplay", help="Path to the screenplay file")
    p_an.add_argument("--tenant", default="default",
                      help="Tenant ID to run as (settings + report isolation)")
    p_an.add_argument("--tenants-file", default=DEFAULT_TENANTS_FILE,
                      help="Path to tenants.json")
    p_an.add_argument("--target-runtime", type=float, default=None,
                      help="Target runtime in minutes")
    p_an.add_argument("--out", default="reports", help="Output directory root")
    p_an.add_argument("--mock", action="store_true",
                      help="Offline heuristic mode — tests the pipeline without an API key")
    p_an.add_argument("--stage", choices=["1", "full"], default="full",
                      help="'1' = solo single-agent mode; 'full' = complete swarm (stages 1+2+3)")

    p_t = sub.add_parser("tenant", help="Manage tenants")
    t_sub = p_t.add_subparsers(dest="tenant_command", required=True)
    t_sub.add_parser("list", help="List tenants")
    p_c = t_sub.add_parser("create", help="Create a tenant")
    p_c.add_argument("tenant_id")
    p_c.add_argument("display_name")
    p_c.add_argument("--llm-api-key", default=None, help="Tenant's own LLM key (optional)")
    p_c.add_argument("--llm-model", default=None)
    p_c.add_argument("--llm-base-url", default=None)
    p_d = t_sub.add_parser("delete", help="Delete a tenant")
    p_d.add_argument("tenant_id")
    p_t.add_argument("--tenants-file", default=DEFAULT_TENANTS_FILE)

    p_srv = sub.add_parser("serve", help="Start the multi-tenant web UI")
    p_srv.add_argument("--port", type=int, default=7100)
    p_srv.add_argument("--tenants-file", default=DEFAULT_TENANTS_FILE)

    args = parser.parse_args(argv)

    if args.command == "analyze":
        registry = TenantRegistry(args.tenants_file)
        tenant = registry.get(args.tenant) if args.tenant != "default" else None
        if args.tenant != "default" and tenant is None:
            sys.exit(f"Unknown tenant '{args.tenant}'. Known: "
                     f"{[t.tenant_id for t in registry.list()] or 'none'}")
        try:
            settings = load_settings(mock=args.mock, tenant=tenant)
        except RuntimeError as e:
            sys.exit(str(e))
        settings.tenant_id = args.tenant  # keep the ID even for the default tenant
        stages = (1,) if args.stage == "1" else (1, 2, 3)
        print(f"Analyzing {args.screenplay} as tenant '{args.tenant}' "
              f"({'MOCK mode' if args.mock else settings.model}, stage={'1' if stages == (1,) else 'full'})...")
        result = asyncio.run(run_analysis(args.screenplay, settings,
                                          target_runtime=args.target_runtime, stages=stages))
        md, js = save_outputs(result, args.out)
        print(f"\n✔ Report:  {md}")
        print(f"✔ Data:    {js}")
        print(f"✔ Scenes analyzed: {len(result.scene_analyses)} | "
              f"genre findings: {len(result.genre_findings)} | "
              f"conflicts resolved: {len(result.conflicts)}")

    elif args.command == "tenant":
        registry = TenantRegistry(args.tenants_file)
        if args.tenant_command == "list":
            tenants = registry.list()
            if not tenants:
                print("No tenants. Create one: edit-table tenant create studio-a \"Studio A\"")
            for t in tenants:
                key = "own LLM key" if t.has_own_llm() else "server default"
                print(f"- {t.tenant_id} ({t.display_name}) · {key} · model={t.llm_model or 'inherit'}")
                print(f"    api_token: {t.api_token}")
        elif args.tenant_command == "create":
            t = registry.create(args.tenant_id, args.display_name,
                                llm_api_key=args.llm_api_key, llm_model=args.llm_model,
                                llm_base_url=args.llm_base_url)
            print(f"Created tenant '{t.tenant_id}' — api_token: {t.api_token}")
            print("Share the token with the tenant; they present it as X-API-Key (web) or use --tenant (CLI).")
        elif args.tenant_command == "delete":
            print("Deleted." if registry.delete(args.tenant_id)
                  else f"Tenant '{args.tenant_id}' not found.")

    elif args.command == "serve":
        try:
            import uvicorn
        except ImportError:
            sys.exit("uvicorn not installed — run: pip install -r requirements.txt")
        from .server import create_app
        app = create_app(tenants_file=args.tenants_file)
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
