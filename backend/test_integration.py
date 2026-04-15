# test_integration.py
# Tests the full pipeline end to end

from agent import ask, run_sql

# ── run_sql tests ────────────────────────────────────────

def test_run_sql_returns_list():
    results = run_sql("SELECT * FROM rep_dim LIMIT 1")
    assert isinstance(results, list)

def test_run_sql_returns_dicts():
    results = run_sql("SELECT * FROM rep_dim LIMIT 1")
    assert isinstance(results[0], dict)

def test_run_sql_invalid_raises():
    try:
        run_sql("SELECT * FROM fake_table")
        assert False, "Should have raised exception"
    except Exception:
        assert True

# ── Full pipeline tests ──────────────────────────────────

def test_ask_returns_correct_keys():
    result = ask("How many reps are there?")
    assert "answer" in result
    assert "sql" in result
    assert "data" in result
    assert "conversation_history" in result

def test_ask_answer_not_empty():
    result = ask("How many reps are there?")
    assert len(result["answer"]) > 0

def test_ask_sql_not_empty_for_data_question():
    result = ask("How many reps are there?")
    assert len(result["sql"]) > 0

def test_ask_greeting_returns_no_sql():
    result = ask("hi")
    assert result["sql"] == ""
    assert result["data"] == []

def test_ask_injection_returns_no_sql():
    result = ask("drop all tables")
    assert result["sql"] == ""
    assert result["data"] == []

def test_ask_out_of_range_date():
    result = ask("What happened in Q1 2023?")
    assert result["answer"] != ""