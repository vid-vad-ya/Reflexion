# Reflexion: Self-Correcting AI Pull Request Agent

Reflexion is a production-quality self-correcting AI agent that clones repository codebases, runs automated planning and patching agents, verifies build compilation/test results locally, and uses feedback loops to fix failures before opening pull requests on GitHub.

---

## Folder Structure

```text
reflexion/
├── backend/                       # Python FastAPI Backend
│   ├── app/
│   │   ├── api/                   # Router Endpoints
│   │   ├── core/                  # Configurations & Security
│   │   ├── services/              # Git & LLM abstractions
│   │   ├── agents/                # LangGraph node agents
│   │   └── main.py                # FastAPI Bootstrap entry
│   └── requirements.txt           # App dependencies
├── frontend/                      # Vite + React Client
│   ├── src/
│   │   ├── components/            # Shared UI (Monaco Diff Viewer)
│   │   ├── pages/                 # Routing Pages
│   │   └── main.tsx               # Client entrypoint
│   └── package.json               # Frontend dependencies
└── README.md                      # General Instructions
```

---

## Local Development Setup

### Prerequisites
* Python 3.10+
* Node.js 18+
* PostgreSQL DB or Neon database URL
* Gemini API Access Token
* GitHub OAuth Application Credentials

### Backend Setup
1. Open a terminal in `/backend`:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy environment template and populate your credentials:
   ```bash
   cp ../.env.template .env
   ```
5. Start development API server:
   ```bash
   uvicorn app.main:app --reload
   ```
   Verify documentation on `http://localhost:8000/docs`.

### Frontend Setup
1. Open a terminal in `/frontend`:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Start local development client:
   ```bash
   npm run dev
   ```
   Verify client page on `http://localhost:5173`.
