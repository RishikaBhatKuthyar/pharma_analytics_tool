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

# Load environment variables from .env file
load_dotenv()

# Initialize Anthropic client
client = Anthropic()

# Rate limiting — tracks requests per session to prevent cost explosion
request_count = 0
MAX_REQUESTS_PER_SESSION = 50  # hard limit per server session


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

# Add this function to agent.py

def is_casual_or_summary(question: str) -> str | None:
    """
    Handles three cases before hitting the SQL pipeline:
    1. Casual greetings — respond warmly
    2. Summary requests — give data overview
    3. Off-topic or dangerous questions — block politely
    """

    question_lower = question.lower().strip()

    # Fix 5 — SQL injection guard
    # Block any question trying to modify or destroy data
    dangerous_keywords = [
        "drop", "delete", "truncate", "insert", "update",
        "alter", "create", "replace", "password", "hack"
    ]
    if any(word in question_lower for word in dangerous_keywords):
        return "I can only answer read-only questions about your pharma sales data. I cannot modify or delete any data."

    # Fix 1 — Off-topic guard
    # Block questions clearly unrelated to pharma sales data
    off_topic_keywords = [
        "weather", "capital city", "poem", "recipe", "sports score",
        "movie", "music", "joke", "news", "stock price", "crypto",
        "what is 2", "calculate", "translate", "write me a"
    ]
    if any(phrase in question_lower for phrase in off_topic_keywords):
        return "I can only answer questions about your pharma sales data — reps, doctors, prescriptions, territories, and market share."

    # Fast greeting detection — no API call needed
    greetings = [
        "hi", "hello", "hey", "how are you", "good morning",
        "good afternoon", "good evening", "thanks", "thank you",
        "what's up", "sup"
    ]
    if any(question_lower.startswith(g) for g in greetings) or question_lower in greetings:
        return "Hello! I'm your pharma sales analytics assistant. What would you like to know about your sales data — rep performance, doctor coverage, prescriptions, or market share?"

    # Summary request detection — no API call needed
    summary_triggers = [
        "summarize", "summary", "overview", "what data", "what do you have",
        "what can you tell me", "tell me everything", "show me everything",
        "what tables", "what information"
    ]
    if any(trigger in question_lower for trigger in summary_triggers):
        today = datetime.now().strftime("%B %d, %Y")
        return (
            f"Here is an overview of the pharma sales data I have access to (as of {today}):\n\n"
            f"Time range: August 2024 through December 2025\n\n"
            f"- 9 sales reps across 3 territories\n"
            f"- 30 healthcare providers (doctors) across Rheumatology, Nephrology, and Internal Medicine\n"
            f"- Prescription data for GAZYVA (new Rx and total Rx)\n"
            f"- Rep call and meeting activity with completion status\n"
            f"- Hospital and clinic accounts with insurance/payor breakdowns\n"
            f"- Market share and patient counts by quarter\n\n"
            f"Try asking: which rep had the most calls, which Tier A doctors haven't been visited, "
            f"payor mix for a specific hospital, or market share by doctor."
        )

    # Fix 6 — Questions about data that doesn't exist
    unavailable_data = [
        "revenue", "salary", "cost", "price", "profit",
        "patient name", "patient id", "side effect", "competitor",
        "email", "phone", "address of rep", "social"
    ]
    if any(phrase in question_lower for phrase in unavailable_data):
        return (
            "That information isn't available in this dataset. "
            "The data covers rep activity, doctor visits, GAZYVA prescriptions, "
            "payor mix, and market share. Try asking about one of those."
        )

    # Real data question — pass through to SQL pipeline
    return None
    
    # Otherwise return the direct response
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
        return (
            f"No data was found for that question. This could be because: "
            f"(1) the time period you asked about is outside the available data range "
            f"(data only exists from August 2024 through December 2025), "
            f"(2) the filter criteria returned no matches, or "
            f"(3) try rephrasing your question with a specific time period like 'in Q4 2024'."
        )

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


def ask(user_question: str, conversation_history: list = []) -> dict:
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