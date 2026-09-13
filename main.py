"""
Main Entry Point
Interactive CLI interface for the OpenAI Weather Agent with Real-Time Data & Live Tracing.
"""

import os
import sys

# Ensure UTF-8 output encoding across all platforms (especially Windows consoles)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from agent import WeatherAgent

load_dotenv()
console = Console()


def print_banner():
    banner_text = (
        "[bold cyan]🌤️ OPENAI WEATHER AGENT + REAL-TIME TRACING[/bold cyan]\n"
        "[dim]Powered by OpenAI SDK & Open-Meteo Free Global Weather API[/dim]\n\n"
        "• [green]Real-time weather data[/green]: Open-Meteo API (No API key needed!)\n"
        "• [blue]Agent Orchestration[/blue]: OpenAI Function Calling & Tool Loop\n"
        "• [magenta]Full Tracing Observability[/magenta]: Spans, Latency, Tool IO, Token Counters, JSON logs\n"
    )
    console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))


def run_query(agent: WeatherAgent, query: str):
    console.print(f"\n[bold yellow]User Question:[/bold yellow] [bold white]{query}[/bold white]")
    
    with console.status("[bold green]Agent thinking & executing tools...[/bold green]", spinner="dots"):
        response, tracer = agent.run(query)

    # 1. Print Final Weather Response
    console.print("\n[bold green]🤖 Weather Agent Response:[/bold green]")
    console.print(Panel(Markdown(response), border_style="green", padding=(1, 2)))

    # 2. Print Execution Trace (Waterfall & Metrics)
    tracer.print_trace(console=console)

    # 3. Inform about saved JSON trace
    console.print(f"[dim]📁 Detailed JSON trace saved at:[/dim] [cyan]traces/{tracer.trace_id}.json[/cyan]\n")


def main():
    print_banner()

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.strip() in ["your_openai_api_key_here", "your_gemini_api_key_here"]:
        console.print(
            "[bold yellow]⚠️ Notice:[/bold yellow] No active [cyan]OPENAI_API_KEY[/cyan] or [cyan]GEMINI_API_KEY[/cyan] found.\n"
            "Running in [bold green]Live Weather Mode with Local Execution Runner[/bold green]!\n"
            "(Fetches real-time weather from Open-Meteo and generates full execution traces).\n"
            "To use live LLM models, set [cyan]GEMINI_API_KEY[/cyan] or [cyan]OPENAI_API_KEY[/cyan] in [bold].env[/bold].\n",
            style="dim"
        )

    agent = WeatherAgent()

    # Check for CLI arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        run_query(agent, query)
        return

    # Interactive Loop
    sample_queries = [
        "What is the weather right now in Tokyo?",
        "What is the 3-day forecast for London?",
        "How is the weather in New York compared to Paris?",
        "Is it raining in Lahore today?"
    ]

    console.print("[bold]Quick options or enter your own custom query:[/bold]")
    for idx, sq in enumerate(sample_queries, 1):
        console.print(f"  [cyan]{idx}.[/cyan] {sq}")
    console.print("  [cyan]q.[/cyan] Quit\n")

    while True:
        try:
            choice = Prompt.ask("[bold magenta]Enter city/question or option number[/bold magenta]", default="1")
            
            if choice.strip().lower() in ["q", "quit", "exit"]:
                console.print("[bold cyan]Goodbye! Stay weather-ready! ☀️☔[/bold cyan]")
                break

            if choice.strip().isdigit() and 1 <= int(choice.strip()) <= len(sample_queries):
                query = sample_queries[int(choice.strip()) - 1]
            else:
                query = choice.strip()

            if not query:
                continue

            run_query(agent, query)
            
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Goodbye![/bold cyan]")
            break


if __name__ == "__main__":
    main()
