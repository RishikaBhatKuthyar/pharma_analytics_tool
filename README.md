# Pharma Analytics Tool

A natural language analytics tool for pharmaceutical sales data. Ask questions in plain English and get data-backed answers instantly.

## Live Demo
- Frontend: https://pharmademo.vercel.app
- Backend: https://pharma-analytics-tool.onrender.com

## What it does
Sales managers can ask plain English questions about rep performance, doctor coverage, prescriptions, and market share — without writing SQL or opening Excel.

## Tech Stack
- **Frontend**: React (Vite)
- **Backend**: FastAPI (Python)
- **Database**: DuckDB
- **AI**: Claude API (Anthropic)
- **Session Memory**: Redis Cloud
- **Deployment**: Render (backend) + Vercel (frontend)

## Architecture
1. User asks a question in plain English
2. Claude generates a SQL query using the schema prompt
3. DuckDB executes the SQL against 9 CSV files
4. Claude summarizes the result in plain English
5. Redis stores conversation history for follow-up questions

## Running Locally

### Backend
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
python startup.py
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
Create `backend/.env`:
ANTHROPIC_API_KEY=your_key_here
REDIS_URL=your_redis_url_here

## Dataset
9 CSV files covering pharma sales data from August 2024 through December 2025:
- Rep activity (calls, meetings)
- Doctor information (specialty, tier, territory)
- Prescription counts for GAZYVA
- Hospital payor mix
- Market share by doctor and quarter

## Key Design Decisions
- **Text-to-SQL over RAG**: Data is structured and relational — RAG is for unstructured text
- **DuckDB over SQLite**: Column-oriented for analytical queries, native CSV loading
- **Two-layer Claude pipeline**: Separate SQL generation from summarization for reliability
- **Redis for session memory**: Server-side sessions work across tabs and devices
- **Prompt caching**: 90% cost reduction on schema tokens