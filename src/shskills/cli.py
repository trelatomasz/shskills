"""Typer-based CLI for shskills."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from shskills._version import __version__
from shskills.config import DEFAULT_REF, KNOWN_AGENTS
from shskills.exceptions import ConfigError, FetchError, InstallError, ManifestError, ShskillsError

app = typer.Typer(
    name="shskills",
    help="Install agent skills from GitHub repositories.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

console = Console()
err_console = Console(stderr=True, style="bold red")

# ---------------------------------------------------------------------------
# Shared option types
# ---------------------------------------------------------------------------

_AgentArg = Annotated[
    str,
    typer.Option(
        "--agent",
        "-a",
        help=f"Target agent. One of: {', '.join(sorted(KNOWN_AGENTS))}",
        show_default=True,
    ),
]
_DestArg = Annotated[
    Optional[Path],
    typer.Option(
        "--dest",
        "-d",
        help="Override the default installation directory.",
    ),
]


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s  %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@app.command("install")
def cmd_install(
    url: Annotated[str, typer.Option("--url", "-u", help="Git repository URL.")],
    agent: _AgentArg = "claude",
    subpath: Annotated[
        Optional[str],
        typer.Option("--subpath", "-s", help="Path relative to SKILLS/ to install."),
    ] = None,
    ref: Annotated[
        str,
        typer.Option("--ref", "-r", help="Branch, tag, or commit SHA."),
    ] = DEFAULT_REF,
    dest: _DestArg = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan without writing any files."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite skills whose content has changed."),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Remove orphaned skills no longer in the source."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Abort on any conflict."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed progress."),
    ] = False,
) -> None:
    """Fetch and install skills from a remote repository."""
    _setup_logging(verbose)

    from shskills.core.installer import install

    try:
        result = install(
            url=url,
            agent=agent,
            subpath=subpath,
            ref=ref,
            dest=dest,
            dry_run=dry_run,
            force=force,
            clean=clean,
            strict=strict,
            verbose=verbose,
        )
    except (ConfigError, FetchError, InstallError, ManifestError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc
    except ShskillsError as exc:
        err_console.print(f"Unexpected error: {exc}")
        raise typer.Exit(code=1) from exc

    prefix = "[dim][dry-run][/dim] " if dry_run else ""

    if result.installed:
        for s in result.installed:
            rprint(f"{prefix}[green]installed[/green]  {s}")
    if result.updated:
        for s in result.updated:
            rprint(f"{prefix}[blue]updated[/blue]    {s}")
    if result.skipped:
        for s in result.skipped:
            rprint(f"{prefix}[dim]skipped[/dim]    {s}")
    if result.cleaned:
        for s in result.cleaned:
            rprint(f"{prefix}[yellow]cleaned[/yellow]    {s}")
    if result.conflicts:
        for s in result.conflicts:
            rprint(f"[red]conflict[/red]   {s}  (use --force to overwrite)")
    if result.errors:
        for s in result.errors:
            rprint(f"[bold red]error[/bold red]      {s}")

    total = result.total_changes
    if total == 0 and not result.conflicts and not result.errors:
        rprint("[dim]Nothing to do — all skills up-to-date.[/dim]")
    else:
        summary_parts = []
        if result.installed:
            summary_parts.append(f"[green]{len(result.installed)} installed[/green]")
        if result.updated:
            summary_parts.append(f"[blue]{len(result.updated)} updated[/blue]")
        if result.cleaned:
            summary_parts.append(f"[yellow]{len(result.cleaned)} cleaned[/yellow]")
        if result.conflicts:
            summary_parts.append(f"[red]{len(result.conflicts)} conflicts[/red]")
        if result.errors:
            summary_parts.append(f"[bold red]{len(result.errors)} errors[/bold red]")
        rprint("  ".join(summary_parts))

    if result.errors or (strict and result.conflicts):
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command("list")
def cmd_list(
    url: Annotated[str, typer.Option("--url", "-u", help="Git repository URL.")],
    subpath: Annotated[
        Optional[str],
        typer.Option("--subpath", "-s", help="Path relative to SKILLS/ to list."),
    ] = None,
    ref: Annotated[
        str,
        typer.Option("--ref", "-r", help="Branch, tag, or commit SHA."),
    ] = DEFAULT_REF,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show front-matter details."),
    ] = False,
) -> None:
    """List available skills in a remote repository."""
    _setup_logging(verbose)

    from shskills.core.planner import list_skills

    try:
        skills = list_skills(url=url, subpath=subpath, ref=ref)
    except (FetchError, ShskillsError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc

    if not skills:
        rprint("[dim]No skills found.[/dim]")
        return

    table = Table(title=f"Skills in {url}", show_lines=False)
    table.add_column("path", style="cyan", no_wrap=True)
    table.add_column("name", style="white")
    table.add_column("version", style="dim")
    if verbose:
        table.add_column("description", style="white")

    for skill in skills:
        row: list[str] = [skill.rel_path, skill.frontmatter.name, skill.frontmatter.version]
        if verbose:
            row.append(skill.frontmatter.description or "—")
        table.add_row(*row)

    console.print(table)


# ---------------------------------------------------------------------------
# installed
# ---------------------------------------------------------------------------


@app.command("installed")
def cmd_installed(
    agent: _AgentArg = "claude",
    dest: _DestArg = None,
) -> None:
    """List skills that are currently installed for an agent."""
    from shskills.core.manifest import installed_skills

    try:
        skills = installed_skills(agent=agent, dest=dest)
    except (ConfigError, ManifestError, ShskillsError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc

    if not skills:
        rprint(f"[dim]No skills installed for agent '{agent}'.[/dim]")
        return

    table = Table(title=f"Installed skills — {agent}", show_lines=False)
    table.add_column("dest path", style="cyan", no_wrap=True)
    table.add_column("name", style="white")
    table.add_column("sha256", style="dim")
    table.add_column("installed", style="dim")

    for skill in skills:
        table.add_row(
            skill.dest_path,
            skill.name,
            skill.content_sha256[:12] + "…",
            skill.installed_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@app.command("doctor")
def cmd_doctor(
    agent: _AgentArg = "claude",
    dest: _DestArg = None,
) -> None:
    """Check the health of installed skills for an agent."""
    from shskills.core.installer import doctor
    from shskills.models import DoctorSeverity

    try:
        report = doctor(agent=agent, dest=dest)
    except (ConfigError, ShskillsError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc

    rprint(f"Agent:  [bold]{report.agent}[/bold]")
    rprint(f"Dest:   [bold]{report.dest}[/bold]")
    rprint(f"Skills: [bold]{report.installed_count}[/bold] installed\n")

    if not report.issues:
        rprint("[green]✓ All good.[/green]")
        return

    severity_color = {
        DoctorSeverity.ERROR: "bold red",
        DoctorSeverity.WARNING: "yellow",
        DoctorSeverity.INFO: "dim",
    }

    for issue in report.issues:
        color = severity_color[issue.severity]
        rprint(f"[{color}]{issue.severity.value.upper():8s}[/{color}]  {issue.message}")

    if not report.healthy:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def _version_callback(
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Print version and exit.", is_eager=True),
    ] = False,
) -> None:
    if version:
        rprint(f"shskills {__version__}")
        raise typer.Exit()
