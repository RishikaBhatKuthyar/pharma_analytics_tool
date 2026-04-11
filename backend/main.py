# main.py
# FastAPI server — bridge between React frontend and AI pipeline.
# Handles conversation history for follow-up questions.
# Includes timeout handling and rate limiting.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from agent import ask
import uvicorn

app = FastAPI(
    title="Pharma Analytics Tool",
    description="Natural language interface for pharma sales data",
    version="1.0.0"
)

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
    role: str     # "user" or "assistant"
    content: str  # the message text


# Request model — question + full conversation history
class QuestionRequest(BaseModel):
    question: str
    conversation_history: Optional[List[ConversationMessage]] = []


# Response model
class AnswerResponse(BaseModel):
    answer: str
    sql: str
    data: list
    conversation_history: list


# Health check
@app.get("/")
def health_check():
    return {"status": "running", "message": "Pharma Analytics API is live"}


# Main endpoint
@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Receives a question + conversation history.
    Returns answer + updated conversation history.
    Times out after 30 seconds with a helpful message.
    """

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Convert conversation history from Pydantic models to plain dicts
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.conversation_history
    ]

    try:
        # Wrap in asyncio timeout — returns error after 30 seconds
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: ask(request.question, history)
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

        # Give specific messages for known error types
        if "authentication" in error_message.lower() or "401" in error_message:
            raise HTTPException(
                status_code=401,
                detail="API key error. Please check your Anthropic API key."
            )
        elif "rate_limit" in error_message.lower() or "429" in error_message:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment and try again."
            )
        elif "overloaded" in error_message.lower():
            raise HTTPException(
                status_code=503,
                detail="Claude API is temporarily busy. Please try again in a few seconds."
            )
        else:
            raise HTTPException(status_code=500, detail=error_message)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )