"""Interactive Console UX for News & Analysis Agent."""

from __future__ import annotations
import sys
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from news_agent_core import (
    NewsAnalystAgent,
    ConfigManager,
    NaturalVoiceBriefer,
    AgentDialogueManager,
    TopicConfig
)

app = typer.Typer(help="News & Analysis Intelligence Agent CLI")
console = Console(highlight=False, emoji=True)


def get_default_dates() -> tuple[str, str]:
    today = datetime.now()
    start = today - timedelta(days=7)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


@app.command("digest")
def run_digest(
    start_date: Optional[str] = typer.Option(None, "--start", "-s", help="Start date YYYY-MM-DD"),
    end_date: Optional[str] = typer.Option(None, "--end", "-e", help="End date YYYY-MM-DD"),
    compact: bool = typer.Option(False, "--compact", "-c", help="Display in 1-precise-line news mode"),
    speak: bool = typer.Option(False, "--speak", "-v", help="Read out executive audio briefing after fetching"),
):
    """Aggregate top news across all configured dynamic topics with optional 1-line or 5-line view."""
    default_start, default_end = get_default_dates()
    s_date = start_date or default_start
    e_date = end_date or default_end

    console.print(Panel.fit(
        f"[bold cyan]News & Analysis Agent[/bold cyan]\n"
        f"[dim]Date Window:[/dim] [green]{s_date}[/green] [dim]to[/dim] [green]{e_date}[/green]\n"
        f"[dim]View Mode:[/dim] [yellow]{'1-Precise-Line' if compact else 'Full 5-Line Analysis'}[/yellow]",
        border_style="cyan"
    ))

    config_mgr = ConfigManager()
    agent = NewsAnalystAgent(config_manager=config_mgr)
    briefer = NaturalVoiceBriefer(config=config_mgr.config.voice)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[yellow]Initializing agent and gathering news...", total=None)

        def update_progress(msg: str):
            progress.update(task, description=f"[yellow]{msg}")

        digest = asyncio.run(agent.aggregate_all_topics(s_date, e_date, update_progress))

    # Print Executive Overview
    console.print("\n")
    console.print(Panel(
        Markdown(digest.executive_overview),
        title="[bold gold1]Cross-Topic Executive Intelligence Overview[/bold gold1]",
        border_style="gold1"
    ))

    # Print News for each Dynamic Topic Tab
    for res in digest.topic_results:
        console.print(f"\n[bold magenta]======= {res.topic_title} ({len(res.items)} events) ======[/bold magenta]")
        console.print(f"[italic dim]Strategy: {res.strategy_applied.strip()}[/italic dim]\n")

        if not res.items:
            console.print("[dim]No news identified in this date range.[/dim]")
            continue

        if compact:
            # 1-Precise-Line news format
            for idx, item in enumerate(res.items, 1):
                console.print(
                    f" [bold cyan]{idx}.[/bold cyan] [bold white]{item.title}[/bold white] — "
                    f"{item.summary.line1_what} "
                    f"[dim]({item.publisher} | [link={item.url}]Link[/link])[/dim]"
                )
        else:
            # Full 5-Line structured format
            for idx, item in enumerate(res.items, 1):
                bullets_text = (
                    f"[bold cyan]1. What:[/bold cyan] {item.summary.line1_what}\n"
                    f"[bold cyan]2. Context:[/bold cyan] {item.summary.line2_context}\n"
                    f"[bold cyan]3. Impact:[/bold cyan] {item.summary.line3_impact}\n"
                    f"[bold cyan]4. Key Data:[/bold cyan] {item.summary.line4_data}\n"
                    f"[bold cyan]5. Outlook:[/bold cyan] {item.summary.line5_outlook}\n\n"
                    f"[dim]Source: [link={item.url}]{item.publisher}[/link] ({item.published_date})[/dim]"
                )

                console.print(Panel(
                    bullets_text,
                    title=f"[bold white]{idx}. {item.title}[/bold white]",
                    border_style="blue",
                    padding=(0, 1)
                ))

    # Voice Readout if requested
    if speak and digest.executive_audio_script:
        console.print("\n[bold green]Playing Executive Voice Broadcast Briefing...[/bold green]")
        asyncio.run(briefer.speak_locally(digest.executive_audio_script))


@app.command("topic")
def run_topic(
    topic_id: str = typer.Argument(..., help="Topic slug ID (e.g. ai_machine_learning)"),
    start_date: Optional[str] = typer.Option(None, "--start", "-s"),
    end_date: Optional[str] = typer.Option(None, "--end", "-e"),
    compact: bool = typer.Option(False, "--compact", "-c", help="Display in 1-precise-line mode"),
    speak: bool = typer.Option(False, "--speak", "-v"),
):
    """Fetch and synthesize news for a single topic."""
    default_start, default_end = get_default_dates()
    s_date = start_date or default_start
    e_date = end_date or default_end

    config_mgr = ConfigManager()
    topic = config_mgr.get_topic(topic_id)
    if not topic:
        console.print(f"[bold red]Topic ID '{topic_id}' not found.[/bold red]")
        console.print("Available topics: " + ", ".join([t.id for t in config_mgr.config.topics]))
        return

    agent = NewsAnalystAgent(config_manager=config_mgr)
    briefer = NaturalVoiceBriefer(config=config_mgr.config.voice)

    with console.status(f"[yellow]Analyzing topic: {topic.title}..."):
        result = asyncio.run(agent.analyze_topic(topic, s_date, e_date))

    console.print(Panel.fit(
        f"[bold magenta]{topic.title}[/bold magenta]\n"
        f"[dim]Strategy:[/dim] {result.strategy_applied.strip()}\n"
        f"[dim]Found {len(result.items)} curated news items ({'1-Line Mode' if compact else 'Full 5-Line Mode'})[/dim]",
        border_style="magenta"
    ))

    if compact:
        for idx, item in enumerate(result.items, 1):
            console.print(
                f" [bold cyan]{idx}.[/bold cyan] [bold white]{item.title}[/bold white] — "
                f"{item.summary.line1_what} "
                f"[dim]({item.publisher} | [link={item.url}]Link[/link])[/dim]"
            )
    else:
        for idx, item in enumerate(result.items, 1):
            bullets = (
                f"[bold cyan]1. What:[/bold cyan] {item.summary.line1_what}\n"
                f"[bold cyan]2. Context:[/bold cyan] {item.summary.line2_context}\n"
                f"[bold cyan]3. Impact:[/bold cyan] {item.summary.line3_impact}\n"
                f"[bold cyan]4. Key Data:[/bold cyan] {item.summary.line4_data}\n"
                f"[bold cyan]5. Outlook:[/bold cyan] {item.summary.line5_outlook}\n\n"
                f"[dim][link={item.url}]{item.publisher}[/link] ({item.published_date})[/dim]"
            )
            console.print(Panel(bullets, title=f"{idx}. {item.title}", border_style="blue"))

    if speak and result.executive_audio_script:
        console.print("\n[bold green]Narrating topic briefing...[/bold green]")
        asyncio.run(briefer.speak_locally(result.executive_audio_script))


@app.command("chat")
def run_chat():
    """Launch interactive conversational dialogue and command interface with the Agent."""
    config_mgr = ConfigManager()
    agent = NewsAnalystAgent(config_manager=config_mgr)
    dialogue = AgentDialogueManager(analyst=agent)

    console.print(Panel(
        "[bold cyan]News Agent Interactive Console & Command Interface[/bold cyan]\n"
        "[dim]You can speak/type natural commands or questions like:[/dim]\n"
        "• 'Add a new topic on Quantum Computing focusing on error correction'\n"
        "• 'What are the top AI hardware stories right now?'\n"
        "• 'Switch LLM to local Ollama with model deepseek-r1:8b'\n"
        "• Type 'exit' to quit.",
        border_style="cyan"
    ))

    default_start, default_end = get_default_dates()

    while True:
        try:
            user_msg = Prompt.ask("\n[bold green]You[/bold green]")
            if user_msg.strip().lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            with console.status("[yellow]Agent thinking & querying RAG..."):
                resp = asyncio.run(dialogue.handle_user_message(
                    user_input=user_msg,
                    current_start_date=default_start,
                    current_end_date=default_end
                ))

            console.print(f"\n[bold cyan]Agent:[/bold cyan] {resp.reply}")

            if resp.config_mutated:
                console.print(f"[bold green]Configuration Saved: {resp.action_performed}[/bold green]")

            if resp.rag_sources:
                console.print("\n[dim]Sources Cited:[/dim]")
                for s in resp.rag_sources[:3]:
                    console.print(f"  • [link={s.get('url')}]{s.get('title')}[/link] ({s.get('source')})")

        except KeyboardInterrupt:
            break


@app.command("topics")
def list_topics():
    """List all dynamic topics configured in the agent."""
    config_mgr = ConfigManager()
    table = Table(title="Dynamic News Topics & Strategies", border_style="blue")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Enabled", style="green")
    table.add_column("Keywords Count", style="yellow")
    table.add_column("Strategy Summary", style="dim")

    for t in config_mgr.config.topics:
        table.add_row(t.id, t.title, str(t.enabled), str(len(t.search_queries)), t.strategy_prompt.strip()[:50] + "...")

    console.print(table)


@app.command("keywords")
def list_keywords(topic_id: str = typer.Argument(..., help="Topic ID or Title")):
    """List all search keywords/queries saved in YAML for a specific topic."""
    config_mgr = ConfigManager()
    topic = config_mgr.find_topic(topic_id)
    if not topic:
        console.print(f"[bold red]Topic '{topic_id}' not found.[/bold red]")
        return

    console.print(Panel(
        f"[bold cyan]Topic:[/bold cyan] {topic.title} ([dim]{topic.id}[/dim])\n"
        f"[bold yellow]Monitored Keywords (Saved in YAML):[/bold yellow]\n" +
        ("\n".join([f"  • {q}" for q in topic.search_queries]) if topic.search_queries else "  [dim]No keywords defined yet.[/dim]"),
        title="[bold green]Topic Keywords in YAML[/bold green]",
        border_style="cyan"
    ))


@app.command("add-keyword")
def add_keyword(
    topic_id: str = typer.Argument(..., help="Topic ID or Title to add keyword to"),
    keyword: str = typer.Argument(..., help="Search keyword or query string")
):
    """Add a search keyword/query to a topic and persist to config.user.yaml."""
    config_mgr = ConfigManager()
    topic = config_mgr.add_keywords_to_topic(topic_id, [keyword])
    if not topic:
        # Create new topic or auto-feed
        topic, is_new = config_mgr.quick_feed_keyword(keyword, topic_id)
        console.print(f"[bold green]✓ Created topic '{topic.title}' and saved keyword '{keyword}' to YAML![/bold green]")
    else:
        console.print(f"[bold green]✓ Added keyword '{keyword}' to '{topic.title}' and saved to YAML![/bold green]")


@app.command("remove-keyword")
def remove_keyword(
    topic_id: str = typer.Argument(..., help="Topic ID or Title"),
    keyword: str = typer.Argument(..., help="Keyword to remove")
):
    """Remove a search keyword from a topic and persist to YAML."""
    config_mgr = ConfigManager()
    success = config_mgr.remove_keyword_from_topic(topic_id, keyword)
    if success:
        console.print(f"[bold green]✓ Removed keyword '{keyword}' from '{topic_id}' in YAML.[/bold green]")
    else:
        console.print(f"[bold red]Keyword '{keyword}' not found in topic '{topic_id}'.[/bold red]")


if __name__ == "__main__":
    app()

