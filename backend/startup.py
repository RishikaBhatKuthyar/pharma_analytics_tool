# startup.py
# Runs once when the server starts on Render
# Generates pharma.db from the 9 CSV files
# Without this the database file doesn't exist on the server

from db import get_connection

print(" Starting database setup...")
conn = get_connection()
print("✅ Database ready — all 9 tables loaded")
conn.close()