# main.py
# FastAPI server — bridge between React frontend and AI pipeline.
# Handles conversation history for follow-up questions.
# Includes timeout handling and rate limiting.

import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from agent import ask
from auth import (
    LoginRequest, RegisterRequest, TokenResponse,
    login_handler, register_handler, get_optional_user
)
from database import init_db, get_db

import uvicorn
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        StarletteIntegration(),
        FastApiIntegration(),
    ],
    traces_sample_rate=0.1,
    environment="production"
)

app = FastAPI(
    title="Pharma Analytics Tool",
    description="Natural language interface for pharma sales data",
    version="1.0.0"
)

# Initialize database tables on startup
@app.on_event("startup")
def startup():
    init_db()

# CORS — allows React frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Message format for conversation history
class ConversationMessage(BaseModel):
    role: str
    content: str

class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    conversation_history: Optional[List[ConversationMessage]] = []

class AnswerResponse(BaseModel):
    answer: str
    sql: str
    data: list
    conversation_history: list


@app.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    return login_handler(request, db)

@app.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    return register_handler(request, db)

@app.post("/clear-history")
async def clear_history(current_user: dict = Depends(get_optional_user)):
    """Clears Redis conversation history for the current user."""
    import redis as redis_lib
    r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    session_key = current_user.get("user_id") if current_user else None
    if session_key:
        r.delete(f"history:{session_key}")
        print(f"🗑️ Cleared Redis history for {session_key}")
    return {"status": "cleared"}

# Health check
@app.get("/")
def health_check():
    return {"status": "running", "message": "Pharma Analytics API is live"}

@app.get("/sentry-test")
async def sentry_test():
    raise Exception("Sentry is working!")


# Main endpoint
@app.post("/ask", response_model=AnswerResponse)
async def ask_question(
    request: QuestionRequest,
    current_user: dict = Depends(get_optional_user)
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if len(request.question) > 500:
        raise HTTPException(status_code=400, detail="Question too long. Please keep it under 500 characters.")

    if current_user:
        print(f"👤 Request from: {current_user.get('email')} ({current_user.get('user_id')})")

    history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.conversation_history
    ]

    try:
        # Use user_id from JWT as session key if authenticated
        # Falls back to browser session_id if no token
        effective_session_id = (
            current_user.get("user_id") if current_user else request.session_id
        )
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: ask(
                    request.question,
                    session_id=effective_session_id,
                    conversation_history=history
                )
            ),
            timeout=30.0
        )

        return AnswerResponse(
            answer=result["answer"],
            sql=result["sql"],
            data=result["data"],
            conversation_history=result["conversation_history"]
        )

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Request timed out after 30 seconds. Please try a simpler question."
        )

    except Exception as e:
        error_message = str(e)

        if "authentication" in error_message.lower() or "401" in error_message:
            raise HTTPException(status_code=401, detail="API key error. Please check your Anthropic API key.")
        elif "rate_limit" in error_message.lower() or "429" in error_message:
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment and try again.")
        elif "overloaded" in error_message.lower():
            raise HTTPException(status_code=503, detail="Claude API is temporarily busy. Please try again in a few seconds.")
        else:
            raise HTTPException(status_code=500, detail=error_message)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )