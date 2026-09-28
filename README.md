# mailsync: AI-powered Email Analysis assistant.

`mailsync` is a CLI tool that monitors your Gmail, extracts important events (including from PDFs), analyzes their sentiment, and records them in your history.

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- A Google Cloud Project with Gmail APIs enabled.
- A Gemini API Key from [Google AI Studio](https://aistudio.google.com/).

### 2. Google Cloud Configuration
To use the CLI, you must use a **Desktop app** OAuth Client ID:
1. Go to [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials).
2. Click **Create Credentials > OAuth client ID**.
3. Select **Application type: Desktop app**.
4. Download the `client_id` and `client_secret`.

### 3. Configuration
Copy `.env.example` to `.env` in the project root and replace the placeholders with the values from your Google Cloud OAuth **Desktop app** credentials:
```env
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
TIMEZONE=Asia/Kolkata
```

The OAuth client must be created under **Google Cloud Console > APIs & Services > Credentials > Create credentials > OAuth client ID > Desktop app**. Also enable the Gmail API and Google Calendar API for that project.

### 4. Installation

## Usage

### Guided Shell
Run `python mailsync.py shell` for a guided workspace with connection status, numbered actions, date filters, question examples, and live sync progress.

### Commands
- **Login:** Authenticate your Google account.
  ```bash
  python mailsync.py login
  ```
- **Sync:** Scan and analyze unread emails.
  ```bash
  python mailsync.py sync
  ```
- **Focused sync:** Analyze only messages matching a topic or instruction.
  ```bash
  python mailsync.py sync --start-date 2026-09-01 --end-date 2026-09-28 --question "Which KPMG emails mention internship registration deadlines?"
  ```
- **History:** View the last 10 processed emails and the agent's reasoning.
  ```bash
  python mailsync.py history
  ```
- **Status:** Check which account is currently connected.
  ```bash
  python mailsync.py status
  ```
- **Logout:** Disconnect the currently active Gmail account, without deleting saved account credentials.
  ```bash
  python mailsync.py logout
  ```
- **Shell:** Enter the interactive Mailsync Neural Shell.
  ```bash
  python mailsync.py shell
  ```
- **Ask:** Search Gmail for relevant messages and answer a question from their contents.
  ```bash
  python mailsync.py ask "What are my exam dates and subject names?"
  ```
  After answering, MailSync can analyze the strongest matching email and optionally add a detected event to Google Calendar.

## How it Works
1. **Connect or switch accounts:** Run `python mailsync.py login`, or choose option `4` in the guided shell to log out of the current account and connect another Gmail account.
2. **Sync:** Run `python mailsync.py sync`.
3. **Agentic Logic:**
   - The agent reads the email body.
  - Text PDFs are read directly; scanned PDFs use a small, two-page vision sample to reduce laptop load.
   - It extracts a title, date, time, and importance score.
   - Events are analyzed and recorded for easy tracking.
  - The `ask` command searches Gmail, ranks the strongest matches, and gives the local model only those messages as context.
