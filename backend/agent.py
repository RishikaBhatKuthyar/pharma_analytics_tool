# agent.py
# Core AI pipeline — takes a user question, generates SQL,
# executes it on DuckDB, and returns a plain English answer.
# Supports conversational memory via conversation_history parameter.

import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
import duckdb
from anthropic import Anthropic
from prompt import SCHEMA_PROMPT
import redis
import json
import time

import requests

def track(metric_name: str, value: float):
    """Send metric to Datadog."""
    try:
        requests.post(
            "https://api.us5.datadoghq.com/api/v1/series",
            headers={
                "Content-Type": "application/json",
                "DD-API-KEY": os.getenv("DATADOG_API_KEY", "")
            },
            json={"series": [{
                "metric": metric_name,
                "points": [[int(time.time()), value]],
                "type": "gauge",
                "tags": ["app:pharma-analytics"]
            }]},
            timeout=2
        )
    except:
        pass


# Initialize Anthropic client
client = Anthropic()

# Initialize Redis client

# Connect to Redis — uses REDIS_URL environment variable in production
# Falls back to localhost for local development
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
# Rate limiting — tracks requests per session to prevent cost explosion
request_count = 0
MAX_REQUESTS_PER_USER = 50



def get_history(session_id: str) -> list:
    """
    Fetches conversation history from Redis for a given session.
    Returns empty list if no history exists yet for this session.
    Each session is stored as a JSON string under key 'history:session_id'
    """
    try:
        data = redis_client.get(f"history:{session_id}")
        return json.loads(data) if data else []
    except Exception as e:
        print(f"Redis get error: {e}")
        return []


def save_history(session_id: str, history: list):
    """
    Saves updated conversation history to Redis.
    Expires after 1 hour (3600 seconds) of inactivity.
    If user comes back within 1 hour their history is still there.
    After 1 hour Redis automatically deletes it.
    """
    try:
        redis_client.setex(
            f"history:{session_id}",  # key format: history:abc123
            3600,                      # expire after 1 hour
            json.dumps(history)        # store as JSON string
        )
    except Exception as e:
        print(f"Redis save error: {e}")


def get_db_connection():
    """
    Opens the existing pharma.db DuckDB database file.
    Read-only so nothing can accidentally modify the data.
    """
    db_path = os.path.join(os.path.dirname(__file__), 'pharma.db')
    return duckdb.connect(database=db_path)


def clean_sql(sql: str) -> str:
    """
    Strips markdown code blocks if Claude wraps SQL in backticks.
    Handles ```sql ... ``` and ``` ... ``` formats.
    Also strips any leading/trailing whitespace.
    """
    sql = sql.strip()

    # Remove ```sql or ``` at the start
    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]

    # Remove ``` at the end
    if sql.endswith("```"):
        sql = sql[:-3]

    return sql.strip()
def is_casual_or_summary(question: str) -> str | None:
    """SQL injection guard only — everything else passes through."""
    question_lower = question.lower().strip()
    dangerous_keywords = [
        "drop", "delete", "truncate", "insert", "update",
        "alter", "create", "replace", "password", "hack"
    ]
    if any(word in question_lower for word in dangerous_keywords):
        return "I can only answer read-only questions about your pharma sales data."
    return None

def is_casual(question: str) -> str | None:
    """
    Detects greetings and off-topic questions.
    Separate from SQL generation so history stays clean.
    No history passed — just the current message.
    """
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": (
                f"You are a pharma sales analytics assistant.\n"
                f"The user said: \"{question}\"\n\n"
                f"Is this a data question about sales reps, doctors, "
                f"prescriptions, territories, or market share?\n\n"
                f"If YES — respond with exactly: DATA_QUESTION\n"
                f"If NO — respond naturally in 1-2 sentences. "
                f"For greetings respond warmly. "
                f"For unavailable data explain what IS available. "
                f"No markdown."
            )
        }]
    )
    # Track casual check cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = (input_tokens * 0.00000025) + (output_tokens * 0.00000125)
    print(f"💰 Casual check — {input_tokens} in / {output_tokens} out — ${cost:.6f}")

    result = response.content[0].text.strip()
    if result == "DATA_QUESTION":
        return None
    return result

def generate_sql(user_question: str, conversation_history: list = []) -> str:
    """
    LAYER 1 — SQL generation only.
    Clean format — no casual detection mixed in.
    History stays consistent for follow-up context.
    """
    messages = conversation_history + [
        {
            "role": "user",
            "content": (
                f"Today's date is {datetime.now().strftime('%B %d, %Y')}. "
                f"The most recent complete quarter is Q4 2024. "
                f"Data is available from August 2024 through December 2025.\n\n"
                f"Convert this question to SQL: {user_question}"
            )
        }
    ]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=[
            {
                "type": "text",
                "text": SCHEMA_PROMPT,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=messages
    )
    # Track Layer 1 cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = (input_tokens * 0.00000025) + (output_tokens * 0.00000125)
    print(f"💰 Layer 1 — {input_tokens} in / {output_tokens} out — ${cost:.6f}")

    # Track metrics in Datadog
    track('pharma.cost.layer1', cost)
    track('pharma.tokens.input', input_tokens)
    track('pharma.tokens.output', output_tokens)
    sql = response.content[0].text.strip()
    sql = clean_sql(sql)
    return sql
def run_sql(sql: str) -> list:
    conn = get_db_connection()
    try:
        result = conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        conn.close()
        raise Exception(f"SQL execution failed: {str(e)}\nSQL was: {sql}")

# def run_sql(sql: str) -> list:
#     """
#     Executes the SQL query against DuckDB.
#     Returns results as a list of dictionaries.
#     Raises a descriptive error if SQL fails.
#     """
#     conn = get_db_connection()

#     try:  
#         result = conn.execute(sql).fetchdf()
#         conn.close()
#         return result.to_dict(orient='records')

#     except Exception as e:
#         conn.close()
#         raise Exception(f"SQL execution failed: {str(e)}\nSQL was: {sql}")

def clean_results(results: list) -> list:
    """
    Cleans raw DuckDB results before display and summarization.
    - Rounds floats to 1 decimal place
    - Replaces None/NULL with 0
    """
    cleaned = []
    for row in results:
        clean_row = {}
        for key, value in row.items():
            if value is None:
                clean_row[key] = 0
            elif isinstance(value, float):
                clean_row[key] = round(value, 1)
            else:
                clean_row[key] = value
        cleaned.append(clean_row)
    return cleaned
def summarize_result(user_question: str, sql: str, results: list) -> str:
    """
    LAYER 2 — Claude receives raw query results and summarizes
    them in plain English for a non-technical sales manager.
    Handles empty results with a helpful explanation.
    """

    # Handle empty results with a helpful explanation instead of generic message
    if not results:
        empty_prompt = f"""
    The user asked: "{user_question}"

    The database query ran successfully but returned zero results.
    Give a short 1-2 sentence plain English explanation of what this likely means.
    If asking about unvisited doctors and getting zero results — it likely means all doctors were visited.
    If asking about a time period outside August 2024 to December 2025 — say data is not available.
    Do not mention SQL or databases. No markdown. Be specific to the question asked.
    """
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": empty_prompt}]
        )
        return response.content[0].text.strip()

    # Limit result size sent to Claude to avoid token overflow
    # If more than 50 rows, summarize the first 50 and note there are more
    result_sample = results[:50]
    result_note = ""
    if len(results) > 50:
        result_note = f"\nNote: Showing first 50 of {len(results)} total rows."

    summary_prompt = f"""
The user asked: "{user_question}"

The database returned these results:
{result_sample}
{result_note}

Please summarize this data in 1-3 clear sentences for a non-technical pharmaceutical sales manager.
Be specific — include actual names, numbers, and percentages from the data.
Do not mention SQL or databases.
Do not use markdown, headers, or bullet points. Plain text only.
IMPORTANT: Trust the data completely. The query already applied all filters correctly.
If the data shows Tier A doctors, they ARE Tier A doctors.
Never question or second-guess the results.
Never ask for clarification. Always give a definitive answer based on what the data shows.
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": summary_prompt
            }
        ]
    )
    # Track Layer 2 cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = (input_tokens * 0.00000025) + (output_tokens * 0.00000125)
    print(f"💰 Layer 2 — {input_tokens} in / {output_tokens} out — ${cost:.6f}")

    # Track metrics in Datadog
    track('pharma.cost.layer2', cost)
    track('pharma.tokens.input', input_tokens)
    track('pharma.tokens.output', output_tokens)



    return response.content[0].text.strip()

def ask(user_question: str, session_id: str = None, conversation_history: list = []) -> dict:

    """
    Main pipeline function.
    If session_id provided — uses Redis for history (production mode)
    If no session_id — uses passed conversation_history (backwards compatible)
    """
    start_time = time.time()

    # If session_id provided fetch history from Redis
    # Otherwise fall back to passed conversation_history
    if session_id:
        conversation_history = get_history(session_id)
        print(f"📋 Loaded {len(conversation_history)} messages from Redis for session {session_id[:8]}...")
    # def ask(user_question: str, conversation_history: list = []) -> dict:
    # Per-user rate limiting via Redis
    if session_id:
        rate_key = f"rate:{session_id}"
        count = redis_client.incr(rate_key)
        if count == 1:
            redis_client.expire(rate_key, 86400)  # resets every 24 hours
        if count > MAX_REQUESTS_PER_USER:
            return {
                "answer": "You've reached your daily limit of 50 questions. Resets in 24 hours.",
                "sql": "",
                "data": [],
                "conversation_history": conversation_history
            }

    print(f"\n🔍 Question: {user_question}")

    # Step 0 — Check for casual messages or summary requests first
    direct_response = is_casual_or_summary(user_question)
    if direct_response:
        print(f"💬 Direct response: {direct_response}")
        return {
            "answer": direct_response,
            "sql": "",
            "data": [],
            "conversation_history": conversation_history
        }
    
    # Step 0.5 — Casual detection (separate from SQL pipeline)
    casual_response = is_casual(user_question)
    if casual_response:
        print(f"💬 Casual response: {casual_response}")
        return {
            "answer": casual_response,
            "sql": "",
            "data": [],
            "conversation_history": conversation_history
        }

    # Step 1 — Generate SQL (only reaches here if it's a real data question)
    print("⚙️  Generating SQL...")
    sql = generate_sql(user_question, conversation_history)
    print(f"📝 SQL:\n{sql}\n")


    # Step 2 — Execute SQL with one automatic retry
    print("🗄️  Running query...")
    try:
        results = run_sql(sql)
        print(f"📊 Results: {len(results)} rows returned\n")

    except Exception as e:
        print(f"❌ SQL Error on first attempt: {e}")
        track('pharma.errors.sql', 1)  

        print("🔄 Retrying with error context...")


        retry_messages = conversation_history + [
            {
                "role": "user",
                "content": f"Convert this question to SQL: {user_question}"
            },
            {
                "role": "assistant",
                "content": sql
            },
            {
                "role": "user",
                "content": (
                    f"That SQL failed with this error: {str(e)}\n\n"
                    f"Please fix the SQL and return only the corrected query. "
                    f"No explanation, no backticks, just the fixed SQL."
                )
            }
        ]

        try:
            retry_response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                system=[
                    {
                        "type": "text",
                        "text": SCHEMA_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=retry_messages
            )

            corrected_sql = clean_sql(retry_response.content[0].text.strip())
            print(f"📝 Corrected SQL:\n{corrected_sql}\n")

            results = run_sql(corrected_sql)
            sql = corrected_sql
            print(f"📊 Results after retry: {len(results)} rows returned\n")

        except Exception as retry_error:
            print(f"❌ Retry also failed: {retry_error}")
            track('pharma.errors.retry_failed', 1)


            return {
                "answer": "I had trouble running that query even after correcting it. Try rephrasing your question or being more specific.",
                "sql": sql,
                "data": [],
                "conversation_history": conversation_history

            }

    # ── OUTSIDE both try/except blocks ──
    # Step 3 — Summarize
    print("💬 Summarizing...")
    answer = summarize_result(user_question, sql, results)
    print(f"✅ Answer: {answer}\n")

# Step 4 — Update history
    # Store in same format as generate_sql sends — consistent context for follow-ups
    # Step 4 — Update history — simple clean format
    updated_history = conversation_history + [
        {"role": "user", "content": f"Convert this question to SQL: {user_question}"},
        {"role": "assistant", "content": sql}
    ]
    if len(updated_history) > 20:
        updated_history = updated_history[-20:]

    # Save to Redis if session_id provided
    if session_id:
        save_history(session_id, updated_history)
        print(f"💾 Saved {len(updated_history)} messages to Redis for session {session_id[:8]}...")
    print(f"📊 Question complete — session {session_id[:8] if session_id else 'N/A'}")

    # Track metrics in Datadog
    duration = time.time() - start_time
    track('pharma.questions.total', 1)
    track('pharma.question.latency', duration)
    print(f"📊 Total latency: {duration:.2f}s")
    return {
        "answer": answer,
        "sql": sql,
        "data": results,
        "conversation_history": updated_history
    }


# Test the pipeline when run directly
if __name__ == "__main__":
    test_questions = [
        "Which rep had the most completed calls in Q4 2024?",
        "What is the payor mix for Mountain Hospital?",
        "Which doctor has the highest market share in 2025Q1?",
        "Which rep has the highest no-contact rate?",
    ]

    history = []
    for question in test_questions:
        result = ask(question, history)
        history = result["conversation_history"]
        print("=" * 60)