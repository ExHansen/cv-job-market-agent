from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from cv_agent.agent.graph import build_cv_agent_graph
from cv_agent.config import settings
from cv_agent.ingestion.cv_parser import load_master_profile
from cv_agent.ingestion.job_fetcher import fetch_jobs_jobspy
from cv_agent.ingestion.job_finder import export_daily_snapshot, find_matching_jobs
from cv_agent.renderer.rendercv_bridge import export_and_render_pdf
from cv_agent.storage.market_db import MarketDatabase

app = typer.Typer(help="Local AI Agent for Company/Job Market Research & ATS CV Optimization.")
console = Console()


@app.command()
def market(
    role: Annotated[str, typer.Option(help="Target job role")] = "Data Engineer",
    region: Annotated[str, typer.Option(help="Target region")] = "Indonesia",
    refresh: Annotated[
        bool,
        typer.Option(help="Run live python-jobspy scrape before summarizing"),
    ] = False,
) -> None:
    """Show job market skill trends from DuckDB (or benchmark seed)."""
    db = MarketDatabase()
    if refresh:
        console.print(f"[cyan]Fetching live jobs for '{role}' in {region}...[/cyan]")
        df = fetch_jobs_jobspy(role=role, location=region)
        count = db.upsert_jobs(df)
        console.print(f"[green]Ingested {count} unique postings into DuckDB.[/green]")

    snap = db.get_market_snapshot(role=role, region=region)
    table = Table(title=f"Job Market Radar: {snap.role} ({snap.region}, n={snap.sample_size})")
    table.add_column("Skill", style="bold")
    table.add_column("Category")
    table.add_column("Demand %", justify="right", style="cyan")
    table.add_column("Tier")

    for s in snap.top_mandatory_skills:
        table.add_row(s.skill, s.category, f"{s.frequency_pct:.1f}%", "Mandatory")
    for s in snap.rising_skills:
        table.add_row(s.skill, s.category, f"{s.frequency_pct:.1f}%", "Rising")
    console.print(table)


@app.command("daily-sync")
def daily_sync(
    hours_old: Annotated[int, typer.Option(help="Lookback window in hours")] = 72,
    limit_per_source: Annotated[int, typer.Option(help="Max jobs per source")] = 15,
) -> None:
    """Run daily Indonesia + Global Remote job ingestion and export Git-friendly snapshots."""
    profile_file = settings.data_dir / "master_profile.yaml"
    if not profile_file.exists():
        profile_file = settings.data_dir / "master_profile.example.yaml"
    profile = load_master_profile(profile_file)
    mdb = MarketDatabase()

    roles = ["Data Engineer", "Data Quality Engineer", "Analytics Engineer"]
    console.print(
        f"[cyan]Running daily sync for {roles} (last {hours_old}h, Indonesia + Remote)...[/cyan]"
    )
    res = find_matching_jobs(
        profile=profile,
        roles=roles,
        scope="both",
        hours_old=hours_old,
        limit_per_source=limit_per_source,
        allow_live_fetch=True,
        market_db=mdb,
    )
    exported = export_daily_snapshot(mdb)
    console.print(
        f"[green]Daily sync complete:[/green] {res.total_fetched} matched jobs | "
        f"sources={res.source_counts}"
    )
    console.print(
        f"[cyan]Snapshot exported:[/cyan] {exported['parquet_path']} "
        f"({exported['total_jobs_exported']} clean data jobs)"
    )


@app.command()
def tailor(
    profile_path: Annotated[
        Path,
        typer.Option(help="Path to MasterProfile YAML"),
    ] = settings.data_dir / "master_profile.yaml",
    role: Annotated[str, typer.Option(help="Target role")] = "Data Engineer",
    company: Annotated[str, typer.Option(help="Target company name (e.g. Shopee, Bank Jago)")] = "",
    job_url: Annotated[str, typer.Option(help="Optional direct job posting URL")] = "",
    no_llm: Annotated[
        bool,
        typer.Option(help="Run deterministic baseline without calling Ollama"),
    ] = False,
    no_web: Annotated[
        bool,
        typer.Option(help="Disable live web/ATS lookup for offline testing"),
    ] = False,
    render_pdf: Annotated[
        bool,
        typer.Option(help="Export RenderCV YAML & compile PDF"),
    ] = False,
) -> None:
    """Research target company + JD, audit gaps, tailor CV, and optionally compile ATS PDF."""
    resolved = (
        profile_path
        if profile_path.exists()
        else settings.data_dir / "master_profile.example.yaml"
    )
    profile = load_master_profile(resolved)
    graph = build_cv_agent_graph()
    result = graph.invoke(
        {
            "master_profile": profile,
            "target_role": role,
            "target_company": company,
            "job_url": job_url,
            "region": "Indonesia",
            "use_llm": not no_llm,
            "allow_web_research": not no_web,
            "max_revisions": 3,
            "events": [],
        }
    )

    for event in result.get("events", []):
        console.print(f"• {event}")

    intel = result["company_intel"]
    if intel.company_name:
        console.print(
            f"\n[bold magenta]Company Profile:[/bold magenta] {intel.company_name} "
            f"({intel.industry}) | JD Source: {intel.jd_source}"
        )
        if intel.company_summary:
            console.print(f"[dim]{intel.company_summary[:300]}...[/dim]")
        if intel.job_title_found:
            console.print(f"[cyan]Matched Open Role:[/cyan] {intel.job_title_found}")

    audit = result["gap_audit"]
    check = result["fact_check"]
    console.print(
        f"\n[bold green]ATS Score:[/bold green] {check.ats_score}% | Passed: {check.passed}"
    )
    console.print(f"[bold]Matched Skills:[/bold] {', '.join(audit.matched_skills)}")
    console.print(f"[bold cyan]Hidden Quick Wins:[/bold cyan] {', '.join(audit.hidden_quick_wins)}")
    console.print(f"[bold yellow]True Skill Gaps:[/bold yellow] {', '.join(audit.true_skill_gaps)}")

    if check.violations:
        console.print("\n[bold yellow]Fact-Check Notes:[/bold yellow]")
        for v in check.violations:
            console.print(f"  [{v.severity.upper()}] {v.rule}: {v.detail}")

    tailored = result["tailored_cv"]
    console.print(f"\n[bold]Summary:[/bold]\n{tailored.professional_summary}\n")
    console.print(
        f"[bold]Prioritized Projects:[/bold] {', '.join(p.name for p in tailored.projects[:3])}\n"
    )
    for exp in tailored.experiences:
        period = f"{exp.start_date} – {exp.end_date}"
        console.print(f"[bold]{exp.role} — {exp.company}[/bold] ({period})")
        for b in exp.bullets:
            console.print(f"  - [{b.source_id}] {b.rewritten_text}")

    if render_pdf:
        out = export_and_render_pdf(profile, tailored)
        console.print(f"\n[cyan]RenderCV YAML:[/cyan] {out['yaml_path']}")
        if out["pdf_path"]:
            console.print(f"[green]Compiled PDF:[/green] {out['pdf_path']}")
        else:
            console.print(f"[red]RenderCV failed:[/red] {out['stderr']}")


if __name__ == "__main__":
    app()
