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
Update the `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_CLIENT_ID=your_new_desktop_client_id
GOOGLE_CLIENT_SECRET=your_new_desktop_client_secret
```

### 4. Installation

## Usage

### Animated Startup
Every time you run `mailsync`, you'll see a unique AI-themed animation.

### Commands
- **Login:** Authenticate your Google account.
  ```bash
  python mailsync.py login
  ```
- **Sync:** Scan and analyze unread emails.
  ```bash
  python mailsync.py sync
  ```
- **History:** View the last 10 processed emails and the agent's reasoning.
  ```bash
  python mailsync.py history
  ```
- **Status:** Check which account is currently connected.
  ```bash
  python mailsync.py status
  ```
- **Shell:** Enter the interactive Mailsync Neural Shell.
  ```bash
  python mailsync.py shell
  ```

## How it Works
1. **Connect:** Run `python mailsync.py login`.
2. **Sync:** Run `python mailsync.py sync`.
3. **Agentic Logic:**
   - The agent reads the email body.
   - If there's a PDF, Gemini analyzes the PDF content.
   - It extracts a title, date, time, and importance score.
   - Events are analyzed and recorded for easy tracking.
