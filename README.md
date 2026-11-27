# AI Study Assistant

An AI-powered conversational learning platform that helps students study smarter. The platform functions like an interactive AI tutor featuring real-time conversational streaming, pedagogical coaching, document grounding, tool integration, and study workflow automation.

---

## Tech Stack

- **Backend:** Python 3.13+, FastAPI, Starlette, Uvicorn, Pydantic V2
- **Database:** MongoDB, Motor (AsyncIO driver), PyMongo
- **AI & LLM:** Google Gemini API (`google-genai` SDK), `gemini-2.5-flash`, Vector Embeddings
- **Frontend (In Progress):** React, Vite, Tailwind CSS
- **Testing & Tools:** Pytest, HTTPX, Pytest-AsyncIO

---

## Features

- **Conversational AI Tutor:** Interactive study assistance with Server-Sent Events (SSE) streaming for real-time response generation.
- **Resilient AI Pipeline:** Automatic retries with exponential backoff, circuit breaker protection against outages, and fallback model routing.
- **Socratic Coaching:** Multi-turn pedagogical workflows that guide students with questions, hints, and comprehension scoring (1–5 scale).
- **Tool-Assisted Learning:** Function calling capabilities allowing the AI to run study calculations and lookups.
- **Document Grounding & RAG:** Context-aware study queries grounded directly in uploaded student notes and textbooks.
- **Background Task Processing:** Non-blocking asynchronous job execution for study summaries, flashcards, and analytics.

---

## Getting Started

### 1. Prerequisites

- Python 3.13 or higher
- Node.js 18+ (for frontend)
- MongoDB running locally or a MongoDB Atlas connection URI
- Google Gemini API Key

---

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows (Git Bash):
source venv/Scripts/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:

```env
PROJECT_NAME="AI Study Assistant API"
ENVIRONMENT=development
DEBUG=True

MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=study_assistant_db

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=gemini-2.5-flash-lite
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_TOKENS=1024

RATE_LIMIT_PER_MINUTE=10
```

Start the backend server:

```bash
uvicorn app.main:app --reload
```

- API Base URL: `http://127.0.0.1:8000`
- Interactive API Docs: `http://127.0.0.1:8000/docs`

---

### 3. Frontend Setup

_(Frontend initialization coming in Phase 4/5)_

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

---

## Running Tests

Run the backend test suite:

```bash
# From the backend directory with virtual environment activated
python -m pytest
```

---

## API Overview

### Chat & Sessions

- `POST /api/chat/sessions` - Create a new study session
- `GET /api/chat/sessions` - List user sessions
- `GET /api/chat/sessions/{id}` - Get session details
- `GET /api/chat/sessions/{id}/full` - Get session details with full message history
- `DELETE /api/chat/sessions/{id}` - Delete a session
- `GET /api/chat/sessions/{id}/messages` - Get paginated messages
- `POST /api/chat/sessions/{id}/messages` - Send a message and get an AI answer
- `POST /api/chat/sessions/{id}/stream` - Stream AI answers via SSE

### Learning Modes & Tools

- `POST /api/chat/sessions/{id}/grounded` - Document-grounded study query
- `POST /api/chat/sessions/{id}/tools` - Tool-augmented AI chat
- `POST /api/chat/sessions/{id}/coaching` - Multi-turn Socratic coaching turn
- `POST /api/chat/sessions/{id}/summarize` - Synchronous session summary

### Background Jobs & System

- `POST /api/chat/sessions/{id}/summarize/background` - Queue background summarization (HTTP 202 Accepted)
- `GET /api/chat/sessions/{id}/summary/status` - Poll summary status
- `GET /api/chat/resilience/status` - Circuit breaker metrics and AI health
- `GET /api/health` - Health check endpoint

---

## Development Roadmap

- [x] **FastAPI Architecture & Asynchronous Motor Database Layer**
- [x] **Session Management & Conversation Persistence**
- [x] **Google Gemini AI Client & SSE Streaming**
- [x] **Document Grounding & Pedagogical Function Tools**
- [x] **Socratic Multi-Turn Coaching Engine**
- [x] **Circuit Breaker Resilience & Model Fallbacks**
- [x] **FastAPI Background Tasks & Async Job Workers**
- [ ] **Phase 7:** Vector Embeddings & Local Vector Store (FAISS/ChromaDB)
- [ ] **Phase 8:** Dynamic Prompt Engineering & Automated Quality Scoring
- [ ] **Phase 6:** Document Parsing & Text Chunking (PDF, DOCX)
- [ ] **Phase 4:** React + Tailwind CSS Web Frontend
- [ ] **Phase 9:** Quiz Generator, Flashcards, Spaced Repetition & Study Analytics
- [ ] **Phase 10:** Docker, GitHub Actions CI/CD & Cloud Deployment
