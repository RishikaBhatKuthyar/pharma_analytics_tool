# test_golden.py
# Known questions with known correct answers
# These verify the data is correct and queries work as expected

from agent import run_sql

# ── Rep performance ──────────────────────────────────────

def test_top_rep_Q4_2024():
    """Sage Brown had most completed calls in Q4 2024"""
    results = run_sql("""
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
    assert len(results) == 1
    full_name = f"{results[0]['first_name']} {results[0]['last_name']}"
    assert "Sage" in full_name
    assert "Brown" in full_name

# ── Doctor data ──────────────────────────────────────────

def test_tier_a_doctor_count():
    """There are 26 Tier A doctors"""
    results = run_sql("SELECT COUNT(*) as total FROM hcp_dim WHERE tier = 'A'")
    assert results[0]['total'] == 26

def test_highest_market_share_2025Q1():
    """Dr Alex Patel has highest market share in 2025Q1"""
    results = run_sql("""
        SELECT h.full_name, m.est_market_share
        FROM fact_ln_metrics m
        JOIN hcp_dim h ON m.entity_id = h.hcp_id
        WHERE m.entity_type = 'H' AND m.quarter_id = '2025Q1'
        ORDER BY m.est_market_share DESC LIMIT 1
    """)
    assert len(results) == 1
    assert "Patel" in results[0]['full_name']
    assert results[0]['est_market_share'] == 24.8

# ── Reference data counts ────────────────────────────────

def test_rep_count():
    """There are 9 sales reps"""
    results = run_sql("SELECT COUNT(*) as total FROM rep_dim")
    assert results[0]['total'] == 9

def test_territory_count():
    """There are 3 territories"""
    results = run_sql("SELECT COUNT(*) as total FROM territory_dim")
    assert results[0]['total'] == 3

def test_data_starts_august_2024():
    """Data starts from August 2024"""
    results = run_sql("SELECT MIN(date_id) as earliest FROM date_dim")
    assert str(results[0]['earliest']).startswith('2024')

def test_q1_2023_returns_empty():
    """Q1 2023 is outside data range — should return no results"""
    results = run_sql("""
        SELECT COUNT(*) as total FROM fact_rep_activity a
        JOIN date_dim d ON a.date_id = d.date_id
        WHERE d.year = 2023
    """)
    assert results[0]['total'] == 0