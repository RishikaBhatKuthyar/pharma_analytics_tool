# agent.py
# This file is the core AI pipeline.
# It takes a user question, sends it to Claude to generate SQL,
# runs that SQL on DuckDB, then sends the result back to Claude
# to summarize in plain English.

import os
from dotenv import load_dotenv
import duckdb
from anthropic import Anthropic
from prompt import SCHEMA_PROMPT

# Load environment variables from .env file
# This makes ANTHROPIC_API_KEY available to the code
load_dotenv()

# Initialize the Anthropic client
# It automatically picks up ANTHROPIC_API_KEY from environment
client = Anthropic()


def get_db_connection():
    """
    Opens the existing pharma.db DuckDB database file.
    Returns a live connection we can run SQL queries against.
    """
    db_path = os.path.join(os.path.dirname(__file__), 'pharma.db')
    return duckdb.connect(database=db_path, read_only=True)


def generate_sql(user_question: str) -> str:
    """
    LAYER 1 — Claude reads the schema prompt + user question
    and returns a SQL query.
    """
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
        messages=[
            {
                "role": "user",
                "content": user_question
            }
        ]
    )

    sql = response.content[0].text.strip()

    # Clean markdown backticks if Claude wraps SQL in code blocks
    # This handles ```sql ... ``` and ``` ... ``` formats
    if sql.startswith("```"):
        # Remove opening ```sql or ```
        sql = sql.split("\n", 1)[1] if "\n" in sql else sql
        # Remove closing ```
        if sql.endswith("```"):
            sql = sql[:-3].strip()

    return sql


def run_sql(sql: str) -> list:
    """
    Executes the SQL query against DuckDB.
    Returns results as a list of dictionaries.
    Each dictionary is one row: {column_name: value}
    """
    conn = get_db_connection()

    try:
        # Execute the query and convert to list of dicts
        result = conn.execute(sql).fetchdf()
        conn.close()

        # Convert dataframe to list of dictionaries for easy handling
        return result.to_dict(orient='records')

    except Exception as e:
        conn.close()
        # If SQL fails, return the error so we can handle it
        raise Exception(f"SQL execution failed: {str(e)}\nSQL was: {sql}")


def summarize_result(user_question: str, sql: str, results: list) -> str:
    """
    LAYER 2 — Claude receives the raw query results
    and summarizes them in plain English for a sales manager.
    """

    # Handle empty results gracefully
    if not results:
        return "No data found for that query. The filters may be too specific or the data may not exist for that time period."

    # Build the summary prompt
    summary_prompt = f"""
The user asked: "{user_question}"

The database returned these results:
{results}

Please summarize this data in 1-3 clear sentences for a non-technical pharmaceutical sales manager.
Be specific — include actual names, numbers, and percentages from the data.
Do not mention SQL or databases.
Do not use markdown, headers, or bullet points. Plain text only.
IMPORTANT: Trust the data completely. If the query filtered for Tier A doctors, 
assume all results ARE Tier A doctors. Do not question the data or ask for clarification.
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


def ask(user_question: str) -> dict:
    """
    Main function — the full pipeline.
    Input:  a plain English question
    Output: a dictionary with the answer, SQL, and raw data
    """
    print(f"\n🔍 Question: {user_question}")

    # Step 1 — Generate SQL from question
    print("⚙️  Generating SQL...")
    sql = generate_sql(user_question)
    print(f"📝 SQL generated:\n{sql}\n")

    # Step 2 — Run SQL against DuckDB
    print("🗄️  Running query...")
    results = run_sql(sql)
    print(f"📊 Results: {results}\n")

    # Step 3 — Summarize results in plain English
    print("💬 Summarizing...")
    answer = summarize_result(user_question, sql, results)
    print(f"✅ Answer: {answer}\n")

    # Return everything — the UI will use all three
    return {
        "answer": answer,      # plain English summary
        "sql": sql,            # the generated SQL (shown in UI for transparency)
        "data": results        # raw rows (shown as table in UI)
    }


# Test the pipeline directly when you run this file
if __name__ == "__main__":
    test_questions = [
        "Which rep had the most completed calls in Q4 2024?",
        "What is the payor mix for Mountain Hospital?",
        "Which doctor has the highest market share in 2025Q1?"
    ]

    for question in test_questions:
        result = ask(question)
        print("=" * 60)