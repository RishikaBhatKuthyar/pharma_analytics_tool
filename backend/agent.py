# agent.py
# Core AI pipeline — takes a user question, generates SQL,
# executes it on DuckDB, and returns a plain English answer.
# Supports conversational memory via conversation_history parameter.

import os
from datetime import datetime
from dotenv import load_dotenv
import duckdb
from anthropic import Anthropic
from prompt import SCHEMA_PROMPT
import redis
import json

# Load environment variables from .env file
load_dotenv()

# Initialize Anthropic client
client = Anthropic()

# Initialize Redis client
# Connects to local Redis server on default port 6379
# db=0 is the default Redis database
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Rate limiting — tracks requests per session to prevent cost explosion
request_count = 0
MAX_REQUESTS_PER_SESSION = 50  # hard limit per server session

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
    return duckdb.connect(database=db_path, read_only=True)


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
    """
    Pre-check before hitting the SQL pipeline.
    Three things are hardcoded for reliability:
      1. SQL injection — must never reach Claude
      2. Off-topic — clear scope boundary
      3. Unavailable data — known dataset limitations
    Everything else — greetings, thanks, summaries — handled by Claude naturally.
    Returns None if it's a real data question (passes through to SQL pipeline).
    Returns a string if it should be answered directly without SQL.
    """

    question_lower = question.lower().strip()

    # HARDCODED 1 — SQL injection guard
    # Block destructive commands before they reach the pipeline
    dangerous_keywords = [
        "drop", "delete", "truncate", "insert", "update",
        "alter", "create", "replace", "password", "hack"
    ]
    if any(word in question_lower for word in dangerous_keywords):
        return "I can only answer read-only questions about your pharma sales data. I cannot modify or delete any data."

    # HARDCODED 2 — Off-topic guard
    # Block questions clearly outside pharma sales scope
    off_topic_keywords = [
        "weather", "capital city", "poem", "recipe", "sports score",
        "movie", "music", "joke", "news", "stock price", "crypto",
        "what is 2", "calculate", "translate", "write me a"
    ]
    if any(phrase in question_lower for phrase in off_topic_keywords):
        return "I can only answer questions about your pharma sales data — reps, doctors, prescriptions, territories, and market share."

   

    # CLAUDE HANDLED — everything else
    # Let Claude decide if this is a data question or a casual message
    # This covers greetings, thanks, summaries, and any edge cases
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": f"""You are a pharma sales analytics assistant.

The ONLY data available is:
- Sales rep activity (calls, meetings, visit status, duration)
- Doctor information (name, specialty, tier, territory)  
- Prescription counts for GAZYVA (total and new Rx)
- Hospital and clinic accounts with payor/insurance mix
- Market share and LINE OF THERAPY PATIENT COUNTS per doctor per quarter
- Territory and date information

The user said: "{question}"

Can this question be answered using ONLY the data listed above?

If YES — respond with exactly: DATA_QUESTION
If NO — explain in 1-2 sentences what isn't available and suggest what IS available.
For greetings or thanks — respond warmly in 1-2 sentences.
No markdown. Keep it short."""
            }
        ]
    )

    result = response.content[0].text.strip()

    # DATA_QUESTION means pass through to SQL pipeline
    if result == "DATA_QUESTION":
        return None

    # Anything else is a direct response — no SQL needed
    return result
def generate_sql(user_question: str, conversation_history: list = []) -> str:
    """
    LAYER 1 — Claude reads the schema prompt + conversation history
    + current question and returns a SQL query.

    conversation_history: list of previous messages for follow-up context
    Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """

    # Build messages — include history for conversational context
    messages = conversation_history + [
        {
            "role": "user",
            "content": (
                f"Today's date is {datetime.now().strftime('%B %d, %Y')}. "
                f"The most recent complete quarter is Q4 2024. "
                f"Data is available from August 2024 through December 2025.\n\n"
                f"Convert this question to SQL: {user_question}"
)        }
    ]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=[
            {
                "type": "text",
                "text": SCHEMA_PROMPT,
                "cache_control": {"type": "ephemeral"}  # 90% cost saving on schema
            }
        ],
        messages=messages
    )

    sql = response.content[0].text.strip()

    # Clean any markdown formatting Claude might add
    sql = clean_sql(sql)

    return sql


def run_sql(sql: str) -> list:
    """
    Executes the SQL query against DuckDB.
    Returns results as a list of dictionaries.
    Raises a descriptive error if SQL fails.
    """
    conn = get_db_connection()

    try:
        result = conn.execute(sql).fetchdf()
        conn.close()
        return result.to_dict(orient='records')

    except Exception as e:
        conn.close()
        raise Exception(f"SQL execution failed: {str(e)}\nSQL was: {sql}")

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

    return response.content[0].text.strip()

def ask(user_question: str, session_id: str = None, conversation_history: list = []) -> dict:
    """
    Main pipeline function.
    If session_id provided — uses Redis for history (production mode)
    If no session_id — uses passed conversation_history (backwards compatible)
    """
    # If session_id provided fetch history from Redis
    # Otherwise fall back to passed conversation_history
    if session_id:
        conversation_history = get_history(session_id)
        print(f"📋 Loaded {len(conversation_history)} messages from Redis for session {session_id[:8]}...")
# def ask(user_question: str, conversation_history: list = []) -> dict:
    global request_count

    # Rate limit check
    request_count += 1
    if request_count > MAX_REQUESTS_PER_SESSION:
        return {
            "answer": "Request limit reached for this session. Please restart the server.",
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

    # Step 1 — Generate SQL (only reaches here if it's a real data question)
    print("⚙️  Generating SQL...")
    sql = generate_sql(user_question, conversation_history)
    print(f"📝 SQL:\n{sql}\n")

    # Step 2 — Execute SQL
    print("🗄️  Running query...")
    try:
        results = run_sql(sql)
        print(f"📊 Results: {len(results)} rows returned\n")
    except Exception as e:
        print(f"❌ SQL Error: {e}")
        return {
            "answer": "I had trouble running that query. Try rephrasing your question or adding a specific time period like 'in Q4 2024'.",
            "sql": sql,
            "data": [],
            "conversation_history": conversation_history
        }

    # Step 3 — Summarize
    print("💬 Summarizing...")
    answer = summarize_result(user_question, sql, results)
    print(f"✅ Answer: {answer}\n")

    # Step 4 — Update history
    updated_history = conversation_history + [
        {"role": "user", "content": f"Convert this question to SQL: {user_question}"},
        {"role": "assistant", "content": sql}
    ]
    if len(updated_history) > 20:
        updated_history = updated_history[-20:]

        # Save updated history to Redis if session_id provided
    if session_id:
        save_history(session_id, updated_history)
        print(f"💾 Saved {len(updated_history)} messages to Redis for session {session_id[:8]}...")
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