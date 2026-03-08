# Agentic Networking Platform

An agentic platform for managing interactions with your professional network. The system processes natural language prompts about interactions and automatically updates contacts, schedules follow-ups, creates meetings, and manages TODOs.

## Architecture

- **Frontend**: Next.js with 3 tabs (Warm Contacts, TODO, Input Prompt)
- **Backend**: FastAPI (API + Orchestrator)
- **MCP Servers**: FastMCP - Calendar, Contacts, Todos (modular)
- **Database**: PostgreSQL

## Features

- Warm contacts dashboard with hot/cold coloring (last 7 days=hot, 30=warm, 90=cool, 90+=cold)
- Full interaction history per contact
- Company as first-class entity
- Tags/labels for contacts
- Notes and context per contact
- Contact deduplication (by email/phone)
- Reminders ("Haven't spoken to X in 90 days")
- Search by contact name, company, interaction summary
- CSV export for contacts and TODOs
- Audit log
- Agent reasoning/confidence logging
- Retry with backoff for external APIs (Google Calendar)
- Scheduling window: 5PM–10PM Pacific (configurable)
- Default meeting duration: 10 minutes

## Prerequisites

1. **Google Calendar API**:
   - Enable Google Calendar API in Google Cloud Console
   - Create OAuth 2.0 credentials (Desktop app)
   - Copy `credentials.json.example` to `mcp-servers/calendar/secrets/credentials.json`
   - Fill in your OAuth client credentials
   - Run OAuth flow once locally to create `token.json` (see setup below)

2. **Environment**: Copy `.env.example` to `.env` and set `OPENAI_API_KEY`

## Quick Start

```bash
# Create calendar secrets directory
mkdir -p mcp-servers/calendar/secrets
cp mcp-servers/calendar/credentials.json.example mcp-servers/calendar/secrets/credentials.json
# Add your OAuth credentials to credentials.json

# Build and run
docker compose up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

## First-Time Google Calendar OAuth

Run once locally (with a browser) to create token.json:

```bash
cd mcp-servers/calendar
export GOOGLE_CREDENTIALS_PATH=secrets/credentials.json
export GOOGLE_TOKEN_PATH=secrets/token.json
pip install -r requirements.txt
python -c "
from google_calendar import get_calendar_service
svc = get_calendar_service()
print('Connected - token.json created')
"
# Copy secrets/token.json into mcp-servers/calendar/secrets/ for Docker
```

## Running Tests

```bash
cd backend
pip install -r requirements.txt
# Unit tests (some require PostgreSQL)
pytest

# API integration tests (with services running)
BACKEND_URL=http://localhost:8000 pytest
```

## Project Structure

```
├── backend/           # FastAPI - API + Orchestrator
├── frontend/          # Next.js
├── mcp-servers/
│   ├── calendar/      # Google Calendar (5PM–10PM PT)
│   ├── contacts/      # Contact tools
│   └── todos/         # TODO tools
├── shared/            # Schemas, DB migrations
└── docker-compose.yml
```
