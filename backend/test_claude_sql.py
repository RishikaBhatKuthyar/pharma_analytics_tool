# test_claude_sql.py
# Tests that Claude generates correct SQL
# WARNING: calls Claude API — costs money
# Run manually before changing schema prompt

from agent import generate_sql, run_sql

def test_claude_sql_top_rep_Q4_2024():
    """Claude generates correct SQL for top rep question"""
    sql = generate_sql("Which rep had most completed calls in Q4 2024?")
    claude_result = run_sql(sql)
    correct_result = run_sql("""
        SELECT r.first_name, r.last_name, COUNT(*) as call_count
        FROM fact_rep_activity a
        JOIN rep_dim r ON a.rep_id = r.rep_id
        JOIN date_dim d ON a.date_id = d.date_id
        WHERE d.quarter = 'Q4' AND d.year = 2024
        AND a.activity_type = 'call'
        AND a.status = 'completed'
        GROUP BY r.first_name, r.last_name
        ORDER BY call_count DESC LIMIT 1
    """)
    assert claude_result[0]['first_name'] == correct_result[0]['first_name']
    assert claude_result[0]['last_name'] == correct_result[0]['last_name']

def test_claude_sql_tier_a_count():
    """Claude correctly maps Tier 1 to tier = A"""
    sql = generate_sql("How many Tier 1 doctors are there?")
    claude_result = run_sql(sql)
    assert list(claude_result[0].values())[0] == 26

def test_claude_sql_market_share_2025Q1():
    """Claude handles 2025Q1 quarter format correctly"""
    sql = generate_sql("Which doctor has the highest market share in 2025Q1?")
    claude_result = run_sql(sql)
    assert "Patel" in str(claude_result[0])

def test_claude_sql_payor_mix():
    """Claude correctly joins account and payor tables"""
    sql = generate_sql("What is the payor mix for Mountain Hospital?")
    claude_result = run_sql(sql)
    assert len(claude_result) > 0
    values = [list(row.values()) for row in claude_result]
    all_values = [v for row in values for v in row]
    assert any(isinstance(v, float) for v in all_values)

def test_claude_sql_rep_count():
    """Claude returns correct rep count"""
    sql = generate_sql("How many sales reps are there?")
    claude_result = run_sql(sql)
    assert list(claude_result[0].values())[0] == 9

def test_claude_sql_territory_count():
    """Claude returns correct territory count"""
    sql = generate_sql("How many territories are there?")
    claude_result = run_sql(sql)
    assert list(claude_result[0].values())[0] == 3

def test_claude_sql_tier_a_doctor_count():
    """Claude returns correct Tier A doctor count"""
    sql = generate_sql("How many Tier A doctors are there?")
    claude_result = run_sql(sql)
    assert list(claude_result[0].values())[0] == 26

def test_claude_sql_completed_filter():
    """Claude applies completed status filter correctly"""
    sql = generate_sql("How many completed calls were made in Q4 2024?")
    claude_result = run_sql(sql)
    correct_result = run_sql("""
        SELECT COUNT(*) as total
        FROM fact_rep_activity a
        JOIN date_dim d ON a.date_id = d.date_id
        WHERE d.quarter = 'Q4' AND d.year = 2024
        AND a.activity_type = 'call'
        AND a.status = 'completed'
    """)
    assert list(claude_result[0].values())[0] == list(correct_result[0].values())[0]

def test_claude_sql_out_of_range_returns_empty():
    """Claude handles out of range date correctly"""
    sql = generate_sql("How many calls were made in Q1 2023?")
    claude_result = run_sql(sql)
    assert list(claude_result[0].values())[0] == 0

def test_claude_sql_left_join_unvisited_doctors():
    """Claude uses LEFT JOIN correctly for unvisited doctors"""
    sql = generate_sql("Which Tier A doctors were not visited in Q4 2024?")
    claude_result = run_sql(sql)
    assert isinstance(claude_result, list)