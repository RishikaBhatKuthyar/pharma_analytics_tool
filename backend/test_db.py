from db import get_connection

conn = get_connection()

# Test 1 — see all tables loaded
print("\n--- Tables loaded ---")
print(conn.execute("SHOW TABLES").fetchdf())

# Test 2 — check date_dim
print("\n--- date_dim sample ---")
print(conn.execute("SELECT * FROM date_dim LIMIT 3").fetchdf())

# Test 3 — check what quarters exist
print("\n--- Quarters available ---")
print(conn.execute("SELECT DISTINCT year, quarter FROM date_dim ORDER BY year, quarter").fetchdf())

# Test 4 - check rep_dim
print("\n--- rep_dim sample ---")
print(conn.execute("SELECT * FROM rep_dim LIMIT 3").fetchdf())

# Test 5 - check fact_rx brands
print("\n--- What drug brands exist ---")
print(conn.execute("SELECT DISTINCT brand_code FROM fact_rx").fetchdf())

# Test 6 - check activity types and statuses
print("\n--- Activity types ---")
print(conn.execute("SELECT DISTINCT activity_type, status FROM fact_rep_activity").fetchdf())

# Test 7 - check payor types
print("\n--- Payor types ---")
print(conn.execute("SELECT DISTINCT payor_type FROM fact_payor_mix").fetchdf())

# Test 8 - check entity types in fact_ln_metrics
print("\n--- Entity types in fact_ln_metrics ---")
print(conn.execute("SELECT DISTINCT entity_type FROM fact_ln_metrics").fetchdf())