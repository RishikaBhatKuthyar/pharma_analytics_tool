# test_unit.py
# Tests individual functions in agent.py

from agent import clean_sql, is_casual_or_summary, get_db_connection

# ── clean_sql tests ──────────────────────────────────────

def test_clean_sql_removes_sql_backticks():
    result = clean_sql("```sql\nSELECT * FROM rep_dim\n```")
    assert result == "SELECT * FROM rep_dim"

def test_clean_sql_removes_plain_backticks():
    result = clean_sql("```\nSELECT * FROM rep_dim\n```")
    assert result == "SELECT * FROM rep_dim"

def test_clean_sql_no_backticks_unchanged():
    result = clean_sql("SELECT * FROM rep_dim")
    assert result == "SELECT * FROM rep_dim"

def test_clean_sql_strips_whitespace():
    result = clean_sql("  SELECT * FROM rep_dim  ")
    assert result == "SELECT * FROM rep_dim"

# ── SQL injection guard tests ────────────────────────────

def test_injection_blocks_drop():
    result = is_casual_or_summary("drop all tables")
    assert result is not None

def test_injection_blocks_delete():
    result = is_casual_or_summary("delete all records")
    assert result is not None

def test_injection_blocks_truncate():
    result = is_casual_or_summary("truncate the table")
    assert result is not None

def test_injection_blocks_uppercase():
    result = is_casual_or_summary("DROP ALL TABLES")
    assert result is not None

def test_injection_allows_normal_question():
    result = is_casual_or_summary("Which rep had most calls?")
    assert result is None

def test_injection_allows_payor_question():
    result = is_casual_or_summary("What is the payor mix for Mountain Hospital?")
    assert result is None

# ── Database connection tests ────────────────────────────

def test_db_connection_opens():
    conn = get_db_connection()
    assert conn is not None
    conn.close()

def test_all_9_tables_exist():
    conn = get_db_connection()
    cursor = conn.cursor()
    tables = [
        'rep_dim', 'hcp_dim', 'account_dim',
        'territory_dim', 'date_dim', 'fact_rx',
        'fact_rep_activity', 'fact_payor_mix', 'fact_ln_metrics'
    ]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        result = cursor.fetchone()
        assert result[0] > 0, f"Table {table} is empty or missing"
    cursor.close()
    conn.close()