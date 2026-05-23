import os
import time
import asyncio
import click
import pyfiglet
import warnings
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.text import Text
from rich.align import Align
from rich.style import Style
from rich.layout import Layout
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

# New imports
import datetime
from typing import Optional

# Suppress other warnings if needed
warnings.filterwarnings("ignore", category=UserWarning)

from backend.models.database import SessionLocal, engine, Base
from backend.models.processed_email import ProcessedEmailRecord
from backend.models.token import GoogleToken
from backend.services.google_service import GoogleService
from backend.services.agent_service import AgentService

load_dotenv()

# Ensure tables exist
Base.metadata.create_all(bind=engine)

console = Console()

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass # Handle closure in commands

def show_logo():
    # Fetch user status
    db = SessionLocal()
    token = db.query(GoogleToken).first()
    user_email = token.user_email if token else "Not logged in"
    db.close()

    # --- NOLEAKS Style Circuit Gradient ---
    GRADIENT = ["bright_green", "green1", "spring_green1", "cyan1", "bright_cyan", "cyan2", "deep_sky_blue1", "bright_blue"]

    # --- High-Resolution Circuit Block Logo (MAILSYNC) ---
    # Manually crafted 8-letter version for maximum readability and circuit style
    circuit_logo = [
        "██   ██  █████  ██ ██       ██████  ██   ██ ███  ██  ██████ ",
        "███ ███ ██   ██ ██ ██      ██       ██   ██ ███  ██ ██      ",
        "██ █ ██ ███████ ██ ██       █████    █████  ██ █ ██ ██      ",
        "██   ██ ██   ██ ██ ██           ██     █    ██  ███ ██      ",
        "██   ██ ██   ██ ██ ███████ ██████      █    ██   ██  ██████ ",
        "╚═╝  ╚═╝ ╚═════╝ ╚╝ ╚══════╝╚══════╝    ╚╝    ╚╝   ╚╝  ╚══════╝"
    ]

    # Apply the vertical gradient to the circuit logo
    styled_logo_lines = []
    for i, line in enumerate(circuit_logo):
        color = GRADIENT[min(i, len(GRADIENT)-1)]
        # Enhance the circuit look by coloring connectors slightly differently
        styled_line = line.replace("█", f"[{color}]█[/{color}]").replace("═", "[dim cyan]═[/dim cyan]").replace("║", "[dim cyan]║[/dim cyan]").replace("╚", "[dim cyan]╚[/dim cyan]").replace("╝", "[dim cyan]╝[/dim cyan]").replace("╔", "[dim cyan]╔[/dim cyan]").replace("╗", "[dim cyan]╗[/dim cyan]")
        styled_logo_lines.append(styled_line)
    styled_logo = "\n".join(styled_logo_lines)

    # --- Vibrant Copilot-Style Mascot ---
    def get_mascot(frame_num):
        eye_color = "bright_green" if frame_num % 2 == 0 else "green3"
        return [
            f"   [bright_cyan]▄████████▄[/bright_cyan]  ",
            f"  [bright_cyan]███▀▀▀▀▀▀███[/bright_cyan] ",
            f"  [bright_magenta]██[/bright_magenta] [bright_cyan]▄▄[/bright_cyan]  [bright_cyan]▄▄[/bright_cyan] [bright_magenta]██[/bright_magenta] ",
            f"  [magenta]██[/magenta] [{eye_color}]▀▀[/{eye_color}]  [{eye_color}]▀▀[/{eye_color}] [magenta]██[/magenta] ",
            f"  [bright_magenta]███▄▄▄▄▄▄███[/bright_magenta] ",
            f"   [bright_magenta]▀████████▀[/bright_magenta]  "
        ]

    def render_frame(frame_num):
        grid = Table.grid(padding=(0, 4), expand=True)
        grid.add_column(ratio=3)
        grid.add_column(ratio=1)

        tagline = Align.right(Text("", style="white dim"), width=55)
        left_side = Group(
            Text(" Welcome to Mailsync", style="bold white"),
            Text.from_markup(styled_logo),
            tagline
        )

        mascot_lines = get_mascot(frame_num)
        right_side = Group(*[Text.from_markup(line) for line in mascot_lines])

        grid.add_row(left_side, right_side)

        # Copilot-style corner brackets
        width = 78
        top_line = Text.assemble(("┌", "white dim"), (" " * (width - 2)), ("┐", "white dim"))
        bottom_line = Text.assemble(("└", "white dim"), (" " * (width - 2)), ("┘", "white dim"))

        description = Text("\nMailsync can scan, analyze and track your emails right from your terminal.\n"
                           "Connect your account to get started or use the shell for active monitoring.", style="white")
        
        status_line = Text.assemble(
            ("\n● ", "bright_cyan"),
            ("Logged in as user: ", "white"),
            (user_email, "bright_cyan")
        )

        return Group(top_line, grid, bottom_line, description, status_line)

    # --- Animation Loop ---
    with Live(render_frame(0), refresh_per_second=13, screen=False) as live:
        for f in range(15):
            live.update(render_frame(f))
            time.sleep(0.075)

@click.group()
def cli():
    """mailsync: AI-powered Email Analysis assistant."""
    pass

@cli.command()
def login():
    """Authenticate with Google."""
    db = get_db()
    google_service = GoogleService(db)
    try:
        console.print("[yellow]Opening browser for authentication...[/yellow]")
        email = google_service.login_cli()
        console.print(f"[bold green]Successfully authenticated as {email}![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Login failed: {e}[/bold red]")
    finally:
        db.close()

@cli.command()
def status():
    """Show current login status."""
    db = get_db()
    token = db.query(GoogleToken).first()
    if token:
        console.print(f"[bold green]Logged in as:[/bold green] {token.user_email}")
    else:
        console.print("[bold red]Not logged in.[/bold red] Run 'mailsync login' first.")
    db.close()

async def run_sync(start_date: Optional[datetime.datetime] = None, end_date: Optional[datetime.datetime] = None):
    db = get_db()
    token = db.query(GoogleToken).first()
    if not token:
        console.print("[bold red]Error:[/bold red] Not logged in. Run 'mailsync login' first.")
        db.close()
        return

    user_email = token.user_email
    google_service = GoogleService(db)
    agent_service = AgentService()
    timezone = os.getenv("TIMEZONE", "UTC")

    with Progress(
        SpinnerColumn("simpleDots"),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        query_parts = []
        if start_date:
            query_parts.append(f'after:{start_date.strftime("%Y/%m/%d")}')
            if not end_date: # If only start_date is provided, end_date defaults to today
                end_date = datetime.datetime.utcnow() 
            query_parts.append(f'before:{end_date.strftime("%Y/%m/%d")}')
        
        query_string = " ".join(query_parts) if query_parts else 'is:unread newer_than:2d'
        
        task_description = f"Scanning emails with query: '{query_string}'..." if query_string else "Scanning unread emails..."
        task = progress.add_task(task_description, total=None)
        
        try:
            messages = google_service.list_messages(user_email, query=query_string, max_results=500)
            if not messages:
                progress.update(task, description="No new emails found matching criteria.")
                return

            progress.update(task, description=f"Found {len(messages)} emails. Processing...")
            
            for msg_meta in messages:
                msg_id = msg_meta['id']
                
                # Check if already processed
                exists = db.query(ProcessedEmailRecord).filter(ProcessedEmailRecord.id == msg_id).first()
                if exists:
                    continue
                
                progress.update(task, description=f"Analyzing email {msg_id}...")
                
                try:
                    full_msg = google_service.get_email_details(user_email, msg_id)
                    body = google_service.extract_body(full_msg['payload'])
                    
                    # Handle PDF attachments
                    pdf_bytes = None
                    if 'parts' in full_msg['payload']:
                        for part in full_msg['payload']['parts']:
                            if part.get('mimeType') == 'application/pdf':
                                pdf_bytes = google_service.get_attachment(user_email, msg_id, part['body']['attachmentId'])
                                break
                    
                    extraction = None
                    if pdf_bytes:
                        extraction = await agent_service.analyze_with_pdf(body, pdf_bytes)
                    else:
                        extraction = await agent_service.analyze_email(body)

                    status = 'skipped'
                    if extraction.is_event and extraction.importance_score >= 5:
                        progress.update(task, description=f"Event detected: {extraction.title}. Creating calendar event...")
                        
                        event_data = {
                            'summary': extraction.title,
                            'location': extraction.location,
                            'description': extraction.description,
                            'start': {
                                'dateTime': extraction.start_time,
                                'timeZone': timezone,
                            },
                            'end': {
                                'dateTime': extraction.end_time,
                                'timeZone': timezone,
                            },
                        }
                        
                        try:
                            # Filter out None values
                            event_data = {k: v for k, v in event_data.items() if v is not None}
                            if event_data.get('start', {}).get('dateTime') and event_data.get('end', {}).get('dateTime'):
                                created_event = google_service.create_calendar_event(user_email, event_data)
                                console.print(f"Calendar event created: {created_event.get('htmlLink')}")
                                status = 'added'
                            else:
                                console.print(f"Skipping calendar event creation for '{extraction.title}': Missing start or end time.")
                                status = 'skipped_no_time'
                        except Exception as calendar_e:
                            console.print(f"Failed to create calendar event for {extraction.title}: {calendar_e}")
                            status = 'error_calendar'
                    
                    record = ProcessedEmailRecord(
                        id=msg_id,
                        user_email=user_email,
                        status=status,
                        extraction_data=extraction.model_dump() if hasattr(extraction, 'model_dump') else extraction.dict()
                    )
                    db.add(record)
                    db.commit()
                    
                except Exception as e:
                    console.print(f"[red]Error processing {msg_id}: {e}[/red]")
                    db.rollback()

            progress.update(task, description="[bold green]Sync complete!")
            
        except Exception as e:
            console.print(f"[bold red]Sync failed: {e}[/bold red]")
        finally:
            db.close()

@cli.command()
@click.option('--start-date', type=click.DateTime(['%Y-%m-%d']), help='Start date (YYYY-MM-DD) to sync emails from.')
@click.option('--end-date', type=click.DateTime(['%Y-%m-%d']), help='End date (YYYY-MM-DD) to sync emails to. Defaults to today if start-date is provided.')
def sync(start_date: Optional[datetime.datetime], end_date: Optional[datetime.datetime]):
    """Sync and analyze emails. Can specify a date range."""
    asyncio.run(run_sync(start_date=start_date, end_date=end_date))

@cli.command()
def history():
    """View sync history."""
    db = get_db()
    records = db.query(ProcessedEmailRecord).order_by(ProcessedEmailRecord.processed_at.desc()).limit(10).all()
    
    if not records:
        console.print("[yellow]No history found.[/yellow]")
        db.close()
        return

    table = Table(title="[bold cyan]Sync History (Last 10)[/bold cyan]")
    table.add_column("Date", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Title")
    table.add_column("Score", justify="right")
    table.add_column("Reasoning")

    for r in records:
        data = r.extraction_data
        status_style = "green" if r.status == "processed" else "yellow"
        table.add_row(
            r.processed_at.strftime("%Y-%m-%d %H:%M"),
            f"[{status_style}]{r.status}[/{status_style}]",
            data.get('title', 'N/A'),
            str(data.get('importance_score', 0)),
            data.get('reasoning', '')
        )
    
    console.print(table)
    db.close()

from rich.layout import Layout
from rich.align import Align
from rich.console import Group
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

@cli.command()
def shell():
    """Enter the interactive Mailsync Neural Shell."""
    session = PromptSession()
    
    console.print(Panel(
        Align.center("[bold bright_green]MAILSYS NEURAL INTERFACE[/bold bright_green]\n[dim]v1.0.0 - Interactive Mode[/dim]"),
        border_style="bright_green"
    ))
    
    while True:
        with patch_stdout():
            try:
                cmd = session.prompt("mailsync > ")
                cmd = cmd.strip().lower()
                
                if not cmd:
                    continue
                if cmd in ["exit", "quit"]:
                    break
                elif cmd == "sync":
                    console.print("[cyan]Triggering Neural Sync...[/cyan]")
                    asyncio.run(run_sync())
                elif cmd == "history":
                    console.print("[yellow]Fetching history...[/yellow]")
                    # Call history logic
                    db = get_db()
                    records = db.query(ProcessedEmailRecord).order_by(ProcessedEmailRecord.processed_at.desc()).limit(10).all()
                    if not records:
                        console.print("[yellow]No history found.[/yellow]")
                    else:
                        table = Table(title="[bold cyan]Sync History (Last 10)[/bold cyan]")
                        table.add_column("Date", style="dim")
                        table.add_column("Status", style="bold")
                        table.add_column("Title")
                        table.add_column("Score", justify="right")
                        for r in records:
                            data = r.extraction_data
                            status_style = "green" if r.status == "processed" else "yellow"
                            table.add_row(
                                r.processed_at.strftime("%Y-%m-%d %H:%M"),
                                f"[{status_style}]{r.status}[/{status_style}]",
                                data.get('title', 'N/A'),
                                str(data.get('importance_score', 0))
                            )
                        console.print(table)
                    db.close()
                elif cmd == "status":
                    db = get_db()
                    token = db.query(GoogleToken).first()
                    if token:
                        console.print(f"[bold green]Connection stable:[/bold green] {token.user_email}")
                    else:
                        console.print("[bold red]Not logged in.[/bold red]")
                    db.close()
                elif cmd == "help":
                    console.print("[bold cyan]Available Commands:[/bold cyan]")
                    console.print("  [green]sync[/green]    - Run a full sync and analysis")
                    console.print("  [green]history[/green] - View recent processed emails")
                    console.print("  [green]status[/green]  - Check connection status")
                    console.print("  [green]help[/green]    - Show this help message")
                    console.print("  [green]exit[/green]    - Leave the shell")
                else:
                    console.print(f"[red]Unknown command: {cmd}. Type 'help' for options.[/red]")
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

if __name__ == "__main__":
    show_logo()
    cli()
