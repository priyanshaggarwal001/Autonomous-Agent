import os
import asyncio
import click
import warnings
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.align import Align
from rich.prompt import Confirm, Prompt

# New imports
import datetime
import re
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

def get_connected_account():
    db = SessionLocal()
    token = get_active_token(db)
    user_email = token.user_email if token else None
    db.close()
    return user_email


def get_active_token(db):
    tokens = db.query(GoogleToken).all()
    return next((token for token in tokens if (token.token_data or {}).get("is_active")), None)


def logout_current_account():
    db = get_db()
    try:
        token = get_active_token(db)
        if not token:
            return None
        token.token_data = {**(token.token_data or {}), "is_active": False}
        db.commit()
        return token.user_email
    finally:
        db.close()

def show_dashboard(title="MAILSYNC"):
    account = get_connected_account()
    status = "Connected" if account else "Not connected"
    status_style = "green" if account else "yellow"

    header = Panel(
        Align.center("[bold cyan]MAILSYNC[/bold cyan]\n[dim]Personal email intelligence[/dim]"),
        border_style="cyan",
    )
    account_panel = Panel(
        f"[{status_style}]● {status}[/{status_style}]\n"
        f"[dim]{account or 'Run Connect to link your Gmail account'}[/dim]",
        title="Account",
        border_style=status_style,
    )
    actions = Table.grid(padding=(0, 2))
    actions.add_column(style="cyan", width=4)
    actions.add_column(style="white")
    actions.add_row("1", "Sync and analyze emails")
    actions.add_row("2", "Ask a question about your mail")
    actions.add_row("3", "View recent activity")
    actions.add_row("4", "Switch Gmail account")
    actions.add_row("5", "Show help and examples")
    actions.add_row("0", "Exit")
    menu_panel = Panel(actions, title="What would you like to do?", border_style="bright_cyan")
    console.print(Group(header, account_panel, menu_panel))


def render_workflow(steps, query):
    table = Table.grid(padding=(0, 1))
    table.add_column(width=3)
    table.add_column(width=20, style="bold")
    table.add_column()
    for label, state, detail in steps:
        icon = "✓" if state == "done" else "›" if state == "active" else "·"
        style = "green" if state == "done" else "cyan" if state == "active" else "dim"
        table.add_row(f"[{style}]{icon}[/{style}]", label, f"[{style}]{detail}[/{style}]")
    return Panel(table, title=f"Live workflow  [dim]{query}[/dim]", border_style="cyan")


def calendar_event_data(extraction, timezone):
    return {
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

@click.group(invoke_without_command=True)
@click.pass_context
def cli(context):
    """mailsync: AI-powered Email Analysis assistant."""
    if context.invoked_subcommand is None:
        context.invoke(shell)

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
    token = get_active_token(db)
    if token:
        console.print(f"[bold green]Logged in as:[/bold green] {token.user_email}")
    else:
        console.print("[bold red]Not logged in.[/bold red] Run 'mailsync login' first.")
    db.close()


@cli.command()
def logout():
    """Log out of the currently active Gmail account."""
    email = logout_current_account()
    if email:
        console.print(f"[green]Logged out of {email}.[/green]")
    else:
        console.print("[yellow]No Gmail account is currently connected.[/yellow]")

async def run_sync(
    start_date: Optional[datetime.datetime] = None,
    end_date: Optional[datetime.datetime] = None,
    focus: Optional[str] = None,
):
    db = get_db()
    token = get_active_token(db)
    if not token:
        console.print("[bold red]Error:[/bold red] Not logged in. Run 'mailsync login' first.")
        db.close()
        return

    user_email = token.user_email
    google_service = GoogleService(db)
    agent_service = AgentService()
    timezone = os.getenv("TIMEZONE", "UTC")
    steps = [
        ["Connect to Gmail", "active", "Checking account"],
        ["Find messages", "pending", "Waiting"],
        ["Read and analyze", "pending", "Waiting"],
        ["Create calendar events", "pending", "Waiting"],
        ["Finish", "pending", "Waiting"],
    ]

    def update_step(index, state, detail):
        steps[index][1] = state
        steps[index][2] = detail
        live.update(render_workflow(steps, query_string))

    with Live(render_workflow(steps, "preparing"), refresh_per_second=8, console=console) as live:
        query_parts = []
        if focus:
            focus_words = [word for word in re.findall(r"[\w@.-]+", focus.lower()) if len(word) > 2]
            query_parts.extend(focus_words[:8])
        if start_date:
            query_parts.append(f'after:{start_date.strftime("%Y/%m/%d")}')
            if not end_date: # If only start_date is provided, end_date defaults to today
                end_date = datetime.datetime.utcnow() 
            query_parts.append(f'before:{end_date.strftime("%Y/%m/%d")}')
        
        query_string = " ".join(query_parts) if query_parts else 'is:unread newer_than:2d'
        live.update(render_workflow(steps, query_string))
        
        try:
            update_step(0, "done", f"Connected as {user_email}")
            update_step(1, "active", "Searching Gmail")
            max_messages = max(1, int(os.getenv("MAX_SYNC_MESSAGES", "10")))
            messages = google_service.list_messages(
                user_email, query=query_string, max_results=max_messages
            )
            if not messages:
                update_step(1, "done", "No matching messages")
                update_step(4, "done", "Nothing to process")
                return

            update_step(1, "done", f"Found {len(messages)} messages")
            update_step(2, "active", "Starting analysis")
            
            for position, msg_meta in enumerate(messages, start=1):
                msg_id = msg_meta['id']
                
                # Check if already processed
                exists = db.query(ProcessedEmailRecord).filter(ProcessedEmailRecord.id == msg_id).first()
                if exists:
                    continue
                
                update_step(2, "active", f"Analyzing {position} of {len(messages)}")
                
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
                        extraction = await agent_service.analyze_with_pdf(body, pdf_bytes, focus=focus)
                    else:
                        extraction = await agent_service.analyze_email(body, focus=focus)

                    status = 'skipped'
                    if extraction.is_event and extraction.importance_score >= 5:
                        update_step(3, "active", f"Adding {extraction.title}")
                        
                        event_data = calendar_event_data(extraction, timezone)
                        
                        try:
                            # Filter out None values
                            event_data = {k: v for k, v in event_data.items() if v is not None}
                            if event_data.get('start', {}).get('dateTime') and event_data.get('end', {}).get('dateTime'):
                                created_event = google_service.create_calendar_event(user_email, event_data)
                                status = 'added'
                            else:
                                status = 'skipped_no_time'
                        except Exception as calendar_e:
                            update_step(3, "active", f"Calendar skipped: {calendar_e}")
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

            update_step(2, "done", "Analysis complete")
            update_step(3, "done", "Calendar updates complete")
            update_step(4, "done", f"Processed {len(messages)} messages")
            
        except Exception as e:
            update_step(4, "active", f"Stopped: {e}")
        finally:
            db.close()

async def run_question(question: str):
    """Search Gmail and answer a natural-language question from the best matches."""
    db = get_db()
    token = get_active_token(db)
    if not token:
        console.print("[bold red]Error:[/bold red] Not logged in. Run 'mailsync login' first.")
        db.close()
        return

    try:
        google_service = GoogleService(db)
        agent_service = AgentService()
        words = [word for word in re.findall(r"[\w@.-]+", question.lower()) if len(word) > 2]
        gmail_query = " ".join(words[:8])
        message_refs = google_service.list_messages(
            token.user_email, query=gmail_query or None, max_results=50
        )
        emails = [
            google_service.get_searchable_email(token.user_email, ref['id'])
            for ref in message_refs
        ]
        question_words = set(words)

        def relevance(email):
            haystack = " ".join(
                [email.get('subject', ''), email.get('sender', ''), email.get('body', '')]
            ).lower()
            return sum(haystack.count(word) for word in question_words)

        emails = sorted(emails, key=relevance, reverse=True)[:8]
        if not emails:
            console.print("[yellow]I could not find matching messages in Gmail.[/yellow]")
            return
        answer = await agent_service.answer_mail_question(question, emails)
        console.print(Panel(Markdown(answer), title="Mail answer", border_style="bright_cyan"))
        if Confirm.ask("Add a detected event from the strongest matching email to Google Calendar?", default=False):
            extraction = await agent_service.analyze_email(emails[0]['body'], focus=question)
            if not extraction.is_event or not extraction.start_time or not extraction.end_time:
                console.print("[yellow]I could not find a complete calendar event in that email.[/yellow]")
            else:
                event_data = calendar_event_data(extraction, os.getenv("TIMEZONE", "UTC"))
                google_service.create_calendar_event(token.user_email, event_data)
                console.print(f"[green]Added '{extraction.title}' to Google Calendar.[/green]")
    except Exception as error:
        console.print(f"[bold red]Question failed: {error}[/bold red]")
    finally:
        db.close()

@cli.command()
@click.option('--start-date', type=click.DateTime(['%Y-%m-%d']), help='Start date (YYYY-MM-DD) to sync emails from.')
@click.option('--end-date', type=click.DateTime(['%Y-%m-%d']), help='End date (YYYY-MM-DD) to sync emails to. Defaults to today if start-date is provided.')
@click.option('--question', '--focus', 'focus', help='Only analyze messages relevant to this question or instruction.')
def sync(start_date: Optional[datetime.datetime], end_date: Optional[datetime.datetime], focus: Optional[str]):
    """Sync and analyze emails. Can specify a date range."""
    asyncio.run(run_sync(start_date=start_date, end_date=end_date, focus=focus))

@cli.command()
@click.argument('question')
def ask(question: str):
    """Find relevant Gmail messages and answer a question about them."""
    asyncio.run(run_question(question))

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
    table.add_column("Added on", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Title")
    table.add_column("Event date", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Reasoning")

    for r in records:
        data = r.extraction_data
        status_style = "green" if r.status == "processed" else "yellow"
        table.add_row(
            r.processed_at.strftime("%Y-%m-%d %H:%M"),
            f"[{status_style}]{r.status}[/{status_style}]",
            data.get('title', 'N/A'),
            data.get('start_time') or "-",
            str(data.get('importance_score', 0)),
            data.get('reasoning', '')
        )
    
    console.print(table)
    db.close()

@cli.command()
def shell():
    """Open the guided Mailsync workspace."""
    def guided_login():
        current_account = get_connected_account()
        if current_account:
            console.print(f"[dim]Currently connected as {current_account}.[/dim]")
            if not Confirm.ask("Log out and connect a different Gmail account", default=True):
                return
        if Confirm.ask("Connect your Gmail account now", default=True):
            db = get_db()
            try:
                console.print("[cyan]Opening Google's secure login page...[/cyan]")
                email = GoogleService(db).login_cli()
                console.print(f"[green]Connected as {email}.[/green]")
            except Exception as error:
                console.print(f"[red]Login failed: {error}[/red]")
            finally:
                db.close()

    def guided_sync():
        choice = Prompt.ask(
            "How much mail should I scan?",
            choices=["recent", "custom", "all"],
            default="recent",
            show_choices=True,
        )
        if choice == "recent":
            focus = Prompt.ask("Ask a question about the emails to analyze (optional)", default="")
            asyncio.run(run_sync(focus=focus or None))
        elif choice == "all":
            focus = Prompt.ask("Ask a question about the emails to analyze (optional)", default="")
            asyncio.run(run_sync(datetime.datetime(2000, 1, 1), datetime.datetime.utcnow(), focus=focus or None))
        else:
            start = Prompt.ask("Start date", default=(datetime.date.today() - datetime.timedelta(days=7)).isoformat())
            end = Prompt.ask("End date", default=datetime.date.today().isoformat())
            focus = Prompt.ask("Ask a question about these emails", default="")
            try:
                asyncio.run(run_sync(
                    datetime.datetime.strptime(start, "%Y-%m-%d"),
                    datetime.datetime.strptime(end, "%Y-%m-%d"),
                    focus=focus or None,
                ))
            except ValueError:
                console.print("[red]Use dates in YYYY-MM-DD format.[/red]")

    def guided_ask():
        console.print(Panel(
            "Examples:\n"
            "[dim]• What are my exam dates and subject names?\n"
            "• Find emails from my university about registration.\n"
            "• What did Company X say about my interview?[/dim]",
            title="Ask your mailbox",
            border_style="cyan",
        ))
        question = Prompt.ask("Question")
        if question.strip():
            asyncio.run(run_question(question.strip()))

    def guided_help():
        console.print(Panel(
            "[bold]Sync[/bold] searches Gmail, analyzes email content and PDFs, then adds important events to Google Calendar.\n\n"
            "[bold]Ask[/bold] finds the most relevant messages and answers using their subjects, senders, dates and content.\n\n"
            "[bold]Date options[/bold] keep scans focused: recent mail is fastest, custom dates give control, and all mail is the broadest search.",
            title="How Mailsync works",
            border_style="bright_cyan",
        ))

    if not get_connected_account():
        show_dashboard()
        guided_login()

    while True:
        show_dashboard()
        choice = Prompt.ask("Choose an action", choices=["1", "2", "3", "4", "5", "0"], default="1")
        if choice == "1":
            guided_sync()
        elif choice == "2":
            guided_ask()
        elif choice == "3":
            history.callback() if hasattr(history, "callback") else history()
        elif choice == "4":
            guided_login()
        elif choice == "5":
            guided_help()
        elif choice == "0":
            console.print("[dim]Goodbye.[/dim]")
            break

if __name__ == "__main__":
    cli()
