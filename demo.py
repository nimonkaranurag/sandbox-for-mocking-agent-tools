from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.traceback import install as rich_traceback

rich_traceback(show_locals=False)
console = Console()

from utils import safe_mkdir
from type import Policy, Operation, OpenAPINormalized
from fixtures import FixtureStore
from recorder import Recorder
from api_ops_router import APIOperationsRouter
from data_generator import DataGenerator
from fixture_generator import FixtureGenerator
from sandbox import Sandbox
from adapter import Adapter


def read_spec_file(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Spec not found: {p}")

    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Spec file is empty: {p}")

    # Try JSON first, then YAML
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Spec is not valid JSON, and PyYAML is not installed. "
            "Install with `pip install pyyaml` or provide JSON."
        ) from e

    try:
        return yaml.safe_load(raw) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to parse YAML spec: {p}") from e


def _extract_result_schema(op: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    responses = op.get("responses") or {}
    # Pick the lowest 2xx code, else 200 semantics
    two_xx = []
    for k in responses.keys():
        if isinstance(k, int) and 200 <= k < 300:
            two_xx.append(k)
        elif isinstance(k, str) and k.isdigit():
            ki = int(k)
            if 200 <= ki < 300:
                two_xx.append(ki)
    target = str(min(two_xx)) if two_xx else "200"

    content = (responses.get(target) or {}).get("content") or {}
    if "application/json" in content:
        return (content["application/json"] or {}).get("schema")

    for mt, body in content.items():
        if isinstance(mt, str) and mt.endswith("+json"):
            sch = (body or {}).get("schema")
            if sch:
                return sch
    for mt, body in content.items():
        if isinstance(mt, str) and "json" in mt:
            sch = (body or {}).get("schema")
            if sch:
                return sch
    return None


def _build_param_schema(op: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coalesce path/query/header params + JSON body into a single input schema
    for demo purposes. This keeps MCP-ish shape: a single object args.
    """
    props: Dict[str, Any] = {}
    required: List[str] = []

    # parameters[]
    for param in op.get("parameters", []) or []:
        name = param.get("name") or "param"
        schema = (param.get("schema") or {"type": "string"})
        props[name] = schema
        if param.get("required"):
            required.append(name)

    # requestBody (JSON only, demo)
    rb = op.get("requestBody") or {}
    rb_content = rb.get("content") or {}
    rb_json = (rb_content.get("application/json") or {}).get("schema")
    if rb_json:
        props["body"] = rb_json
        if rb.get("required", False):
            required.append("body")

    out: Dict[str, Any] = {"type": "object", "properties": props}
    if required:
        out["required"] = sorted(set(required))
    return out


def register_ops_from_openapi(
    openapi: OpenAPINormalized, router: APIOperationsRouter
) -> None:
    paths = openapi.paths or {}
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            m = str(method).upper()
            if m not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue

            name = f"{m} {path}"
            desc = op.get("description") or op.get("summary") or ""
            param_schema = _build_param_schema(op)
            result_schema = _extract_result_schema(op) or {"type": "object"}

            router.register_op(
                Operation(
                    name=name,
                    param_schema=param_schema,
                    result_schema=result_schema,
                    description=desc,
                    version=str(op.get("x-version", "v1")),
                )
            )


def pick_demo_ops(all_ops: List[str], limit: int = 2) -> List[str]:
    gets = [o for o in all_ops if o.startswith("GET ")]
    rest = [o for o in all_ops if not o.startswith("GET ")]
    chosen = (gets + rest)[:limit] or all_ops[:limit]
    return chosen


def synth_args_for_path(op_name: str) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    # Extract {...} segments from the path portion of "METHOD /path"
    m = re.match(r"^[A-Z]+\s+(.+)$", op_name)
    path = m.group(1) if m else op_name
    for param in re.findall(r"\{([^}]+)\}", path):
        # naive type guess
        if "id" in param or "number" in param:
            args[param] = 123
        else:
            args[param] = "demo"
    return args


class SchemaOnlyDGShim:

    def __init__(self, inner: DataGenerator, openapi: OpenAPINormalized) -> None:
        self._inner = inner
        self._openapi = openapi

    def generate(self, schema: Dict[str, Any]) -> Any:
        return self._inner.generate(self._openapi, schema)


def main():
    parser = argparse.ArgumentParser(
        description="Agent Sandbox demo (rich logs, full stack)."
    )
    parser.add_argument(
        "--spec",
        type=str,
        default="examples/simple_openapi.yaml",
        help="Path to OpenAPI spec (JSON or YAML).",
    )
    parser.add_argument(
        "--service-name",
        type=str,
        default="sample_spec",
        help="Logical service name for generated fixtures.",
    )
    parser.add_argument(
        "--recordings-dir",
        type=str,
        default="recordings",
        help="Where to write call transcripts.",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=str,
        default=None,
        help="(Optional) root directory for fixture store if your FixtureStore supports it.",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Seed for data/chaos determinism."
    )
    parser.add_argument(
        "--chaos",
        type=float,
        default=0.0,
        help="Injected failure rate (0.0 to 1.0) via FaultProfile.error_rate.",
    )
    args = parser.parse_args()

    console.print(Panel.fit("[b]Agent Sandbox Demo[/b]"))

    console.print(Rule("[cyan]1) Load OpenAPI Spec[/cyan]"))
    spec = read_spec_file(args.spec)
    openapi = OpenAPINormalized.from_dict(spec)
    console.print(
        Panel.fit(
            f"[green]Loaded[/green] {args.spec}\n"
            f"Title: {spec.get('info', {}).get('title', '—')}  "
            f"Version: {spec.get('info', {}).get('version', '—')}",
            title="OpenAPI",
        )
    )

    console.print(Rule("[cyan]2) Register Operations[/cyan]"))
    router = APIOperationsRouter()
    register_ops_from_openapi(openapi, router)

    tools = router.list_ops()
    tbl = Table(title="Registered Tools", show_lines=False)
    tbl.add_column("#", justify="right")
    tbl.add_column("Name", overflow="fold")
    for i, name in enumerate(tools, 1):
        tbl.add_row(str(i), name)
    console.print(tbl)

    console.print(Rule("[cyan]3) Policy + Recorder[/cyan]"))
    policy = Policy(allowed_tools=tools)  # allow everything we registered
    recorder = Recorder(output_dir=args.recordings_dir)  # Sandbox will call it
    console.print(
        Panel.fit(
            f"Allowed tools: {len(tools)}\nRecordings dir: {Path(args.recordings_dir).resolve()}",
            title="Runtime Policy",
        )
    )

    console.print(Rule("[cyan]4) Data • Fixtures • Chaos[/cyan]"))
    dg = DataGenerator(seed=args.seed)
    fg = FixtureGenerator(dg)
    bundle = fg.generate(spec=spec, service_name=args.service_name)
    console.print(Panel.fit("Generated a FixtureBundle (summary below).", title="FixtureGenerator"))
    console.print(
        f"[dim]services[/dim]: {list(bundle.services.keys())} • "
        f"[dim]profiles[/dim]: {list(bundle.profiles.keys())} • "
        f"[dim]metadata.seed[/dim]: {bundle.metadata.get('seed')}"
    )

    dg_shim = SchemaOnlyDGShim(dg, openapi)

    fixtures = FixtureStore()

    from type import FaultProfile
    fault = FaultProfile(seed=args.seed, min_latency_ms=30, max_latency_ms=180, error_rate=args.chaos)

    sandbox = Sandbox(
        policy=policy,
        recorder=recorder,
        fault=fault,
        fixtures=fixtures,
        api_ops_router=router,
        data_generator=dg_shim,
    )

    # ---------- MCP Adapter view ----------
    console.print(Rule("[cyan]5) MCP Adapter: Describe Tools[/cyan]"))
    adapter = Adapter(sandbox)
    described = adapter.describe_tools()
    at = Table(title="Adapter.describe_tools()", show_lines=False)
    at.add_column("Name")
    at.add_column("Version", justify="center")
    at.add_column("Input keys", overflow="fold")
    for d in described:
        props = list((d.get("input_schema") or {}).get("properties", {}).keys())
        at.add_row(d["name"], d.get("version", "v1"), ", ".join(props) or "—")
    console.print(at)

    console.print(Rule("[cyan]6) Invoke Tools (record & replay)[/cyan]"))
    chosen = pick_demo_ops(tools, limit=2)
    if not chosen:
        console.print(Panel.fit("[yellow]No operations found in spec.[/yellow]"))
        return

    with Progress(SpinnerColumn(), *Progress.get_default_columns(), TimeElapsedColumn(), transient=True) as progress:
        for name in chosen:
            args1 = synth_args_for_path(name)
            task = progress.add_task(f"Calling [b]{name}[/b] (1st call: synth & record)...", total=None)
            invocation, response = sandbox.invoke(name, args1, record=True)
            progress.update(task, description=f"Done: {name}")
            progress.remove_task(task)

            console.print(
                Panel.fit(
                    f"[b]{name}[/b]\n"
                    f"id: {invocation.tool_id}\nlatency_ms: {response.latency_ms}\n"
                    f"ok: {response.ok}  error: {response.error or '—'}",
                    title="Invocation #1",
                )
            )
            if response.data is not None:
                console.print("[dim]data (preview)[/dim]:")
                console.print_json(data=response.data if isinstance(response.data, dict) else {"data": response.data})

            task = progress.add_task(f"Calling [b]{name}[/b] (2nd call: replay cached)...", total=None)
            invocation2, response2 = sandbox.invoke(name, args1, record=True)
            progress.update(task, description=f"Done: {name}")
            progress.remove_task(task)

            console.print(
                Panel.fit(
                    f"[b]{name}[/b]\n"
                    f"id: {invocation2.tool_id} (same signature)\nlatency_ms: {response2.latency_ms}\n"
                    f"ok: {response2.ok}  error: {response2.error or '—'}",
                    title="Invocation #2 (Cached)",
                )
            )

    console.print(Rule("[green]Demo complete[/green]"))

if __name__ == "__main__":
    safe_mkdir("recordings")
    main()
