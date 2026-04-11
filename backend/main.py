# main.py
# This is the FastAPI server — the bridge between the frontend and the AI pipeline.
# It exposes one endpoint: POST /ask
# The frontend sends a question, this returns an answer.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ask
import uvicorn

# Initialize the FastAPI app
app = FastAPI(
    title="Pharma Analytics Tool",
    description="Natural language interface for pharma sales data",
    version="1.0.0"
)

# CORS middleware — allows the React/Streamlit frontend to talk to this backend
# Without this, the browser will block requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # in production, replace * with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request model — defines what the frontend must send
class QuestionRequest(BaseModel):
    question: str  # the plain English question from the user


# Response model — defines what we send back to the frontend
class AnswerResponse(BaseModel):
    answer: str    # plain English summary from Claude
    sql: str       # the generated SQL query (shown in UI for transparency)
    data: list     # raw rows from DuckDB (shown as table in UI)


# Health check endpoint — useful to verify the server is running
@app.get("/")
def health_check():
    """Simple health check — visit http://localhost:8000 to confirm server is running"""
    return {"status": "running", "message": "Pharma Analytics API is live"}


# Main endpoint — receives question, returns answer
@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Main endpoint. Receives a plain English question,
    runs it through the full AI pipeline, returns the answer.
    """

    # Validate the question is not empty
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # Call the full pipeline from agent.py
        result = ask(request.question)

        # Return structured response
        return AnswerResponse(
            answer=result["answer"],
            sql=result["sql"],
            data=result["data"]
        )

    except Exception as e:
        # If anything goes wrong, return a clean error message
        raise HTTPException(status_code=500, detail=str(e))


# Run the server when this file is executed directly
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True   # auto-restart when you save changes during development
    )