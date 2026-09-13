"""
Tracer Module
Captures, visualizes, and records agent execution traces, tool invocations,
API latencies, token consumption, and intermediate steps.
"""

import json
import os
import sys
import time
import uuid

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class TraceSpan:
    span_id: str
    name: str
    span_type: str  # "LLM_CALL", "TOOL_CALL", "AGENT_STEP", "SYSTEM"
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "running"  # "running", "success", "error"
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "success", output_data: Optional[Dict[str, Any]] = None):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        if output_data is not None:
            self.output_data = output_data


class AgentTracer:
    """
    Session-level execution tracer for OpenAI Agent runs.
    Records spans, tokens, and renders visual summaries.
    """

    def __init__(self, query: str, model: str = "gpt-4o-mini"):
        self.trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.query = query
        self.model = model
        self.created_at = datetime.now().isoformat()
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.total_duration_ms: Optional[float] = None
        self.spans: List[TraceSpan] = []
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        self.active_spans: Dict[str, TraceSpan] = {}
        self.final_response: Optional[str] = None
        self.status = "running"

    def start_span(
        self,
        name: str,
        span_type: str,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        span_id = f"span_{len(self.spans) + 1}_{uuid.uuid4().hex[:4]}"
        span = TraceSpan(
            span_id=span_id,
            name=name,
            span_type=span_type,
            start_time=time.time(),
            input_data=input_data,
            metadata=metadata or {}
        )
        self.spans.append(span)
        self.active_spans[span_id] = span
        return span_id

    def end_span(
        self,
        span_id: str,
        status: str = "success",
        output_data: Optional[Dict[str, Any]] = None,
        tokens: Optional[Dict[str, int]] = None
    ):
        span = self.active_spans.pop(span_id, None)
        if span:
            span.finish(status=status, output_data=output_data)
            if tokens:
                self.token_usage["prompt_tokens"] += tokens.get("prompt_tokens", 0)
                self.token_usage["completion_tokens"] += tokens.get("completion_tokens", 0)
                self.token_usage["total_tokens"] += tokens.get("total_tokens", 0)
                span.metadata["tokens"] = tokens

    def complete(self, final_response: str, status: str = "success"):
        self.end_time = time.time()
        self.total_duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.final_response = final_response
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "model": self.model,
            "status": self.status,
            "created_at": self.created_at,
            "total_duration_ms": self.total_duration_ms,
            "token_usage": self.token_usage,
            "spans_count": len(self.spans),
            "spans": [asdict(s) for s in self.spans],
            "final_response": self.final_response
        }

    def save_json(self, directory: str = "traces") -> str:
        """Save the trace session to a formatted JSON file."""
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{self.trace_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath

    def print_trace(self, console: Optional[Any] = None):
        """Render a rich, colorized execution trace in the terminal."""
        if not RICH_AVAILABLE:
            self._print_plain()
            return

        c = console or Console()
        c.print("\n")
        c.print(f"[bold cyan]🔍 EXECUTION TRACE DETAILS[/bold cyan] [dim]({self.trace_id})[/dim]")
        
        # Summary Overview Table
        summary_table = Table(box=None, padding=(0, 2))
        summary_table.add_column("Metric", style="bold magenta")
        summary_table.add_column("Value", style="cyan")
        
        summary_table.add_row("Status", f"[bold green]{self.status.upper()}[/bold green]" if self.status == "success" else f"[bold red]{self.status.upper()}[/bold red]")
        summary_table.add_row("Total Latency", f"[yellow]{self.total_duration_ms} ms[/yellow]")
        summary_table.add_row("Model", f"[white]{self.model}[/white]")
        summary_table.add_row(
            "Tokens Used",
            f"Prompt: {self.token_usage['prompt_tokens']} | Completion: {self.token_usage['completion_tokens']} | Total: [bold]{self.token_usage['total_tokens']}[/bold]"
        )
        summary_table.add_row("Steps / Spans", f"{len(self.spans)} events")
        
        c.print(Panel(summary_table, title="[bold]Trace Summary[/bold]", border_style="cyan"))

        # Step-by-Step Execution Tree
        tree = Tree(f"[bold yellow]Agent Run: \"{self.query}\"[/bold yellow]")
        
        for idx, span in enumerate(self.spans, 1):
            dur = f"[yellow]{span.duration_ms}ms[/yellow]" if span.duration_ms else "[dim]pending[/dim]"
            status_badge = "🟢" if span.status == "success" else ("🔴" if span.status == "error" else "⏳")
            
            if span.span_type == "LLM_CALL":
                node_label = f"{status_badge} [bold blue]Step {idx}: LLM Inference[/bold blue] ({dur})"
                node = tree.add(node_label)
                if span.metadata.get("tokens"):
                    tok = span.metadata["tokens"]
                    node.add(f"[dim]Tokens: {tok.get('total_tokens', 0)} (Prompt: {tok.get('prompt_tokens', 0)}, Compl: {tok.get('completion_tokens', 0)})[/dim]")
                if span.output_data and span.output_data.get("tool_calls_requested"):
                    calls = span.output_data["tool_calls_requested"]
                    node.add(f"[green]Decision: Call {len(calls)} tool(s): {', '.join(calls)}[/green]")
                elif span.output_data and span.output_data.get("response_preview"):
                    node.add(f"[italic cyan]Generated final answer preview: \"{span.output_data['response_preview'][:80]}...\"[/italic cyan]")

            elif span.span_type == "TOOL_CALL":
                node_label = f"{status_badge} [bold magenta]Step {idx}: Tool '{span.name}'[/bold magenta] ({dur})"
                node = tree.add(node_label)
                if span.input_data:
                    node.add(f"[cyan]Input:[/cyan] {json.dumps(span.input_data)}")
                if span.output_data:
                    summary_text = ""
                    if "status" in span.output_data and "location" in span.output_data:
                        loc = span.output_data["location"]
                        loc_str = f"{loc.get('city')}, {loc.get('country')}"
                        if "current_weather" in span.output_data:
                            cw = span.output_data["current_weather"]
                            summary_text = f"Weather: {cw.get('temperature')}, {cw.get('condition')}, Humidity: {cw.get('humidity')}"
                        elif "forecast" in span.output_data:
                            summary_text = f"Forecast: {len(span.output_data['forecast'])} days retrieved"
                        node.add(f"[green]Data fetched for {loc_str}: {summary_text}[/green]")
                    else:
                        out_str = json.dumps(span.output_data)
                        node.add(f"[dim]Output: {out_str[:120]}...[/dim]")

            else:
                node_label = f"{status_badge} [white]Step {idx}: {span.name}[/white] ({dur})"
                tree.add(node_label)

        c.print(Panel(tree, title="[bold]Trace Execution Spans (Waterfall)[/bold]", border_style="blue"))

    def _print_plain(self):
        """Plain text fallback."""
        print(f"\n--- TRACE: {self.trace_id} ---")
        print(f"Query: {self.query}")
        print(f"Status: {self.status} | Latency: {self.total_duration_ms}ms")
        print(f"Tokens: {self.token_usage}")
        for s in self.spans:
            print(f" - [{s.span_type}] {s.name}: {s.status} ({s.duration_ms}ms)")
        print("-" * 40)
