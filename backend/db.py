import duckdb  # DuckDB is our database engine - runs entirely in Python, no separate server needed
import os      # os lets us build file paths that work on any operating system (Mac, Windows, Linux)

# Build the path to the data folder
# __file__ = current file (db.py)
# '..' = go one level up (from backend/ to project root)
# 'data' = then into the data folder
# Result: /your/project/pharma_analytics_tool/data
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def get_connection():
    """
    Creates a DuckDB in-memory database and loads all 9 CSV files as queryable tables.
    This function is called ONCE when the FastAPI app starts up.
    After this runs, you can write SQL against any of these tables.
    """

    # Create an in-memory DuckDB connection
    # In-memory means the data lives in RAM, not saved to a file on disk
    # This is fine for our use case since the CSVs are the source of truth
    conn = duckdb.connect("pharma.db")

    # Dictionary mapping table names to their CSV filenames
    # Key   = what the table will be called in SQL queries
    # Value = the actual CSV filename in the data/ folder
    tables = {
        'account_dim':       'account_dim.csv',       # healthcare facilities (hospitals, clinics)
        'date_dim':          'date_dim.csv',           # calendar dates for time-based filtering
        'hcp_dim':           'hcp_dim.csv',            # healthcare providers (doctors)
        'rep_dim':           'rep_dim.csv',            # sales representatives
        'territory_dim':     'territory_dim.csv',      # geographic sales territories
        'fact_rx':           'fact_rx.csv',            # prescription counts per doctor per date
        'fact_rep_activity': 'fact_rep_activity.csv',  # rep visits and calls to doctors
        'fact_payor_mix':    'fact_payor_mix.csv',     # insurance breakdown per account
        'fact_ln_metrics':   'fact_ln_metrics.csv',    # market share and patient counts
    }

    # Loop through each table and load it into DuckDB
    for table_name, filename in tables.items():

        # Build the full file path to the CSV
        # Example: /project/data/fact_rx.csv
        filepath = os.path.join(DATA_DIR, filename)

        # read_csv_auto() is a DuckDB function that:
        # - automatically detects column names from the header row
        # - automatically detects data types (integer, string, date, etc.)
        # - no manual schema definition needed
        # CREATE TABLE ... AS SELECT * creates a full in-memory table from the CSV
        conn.execute(f"""
        DROP TABLE IF EXISTS {table_name};
        CREATE TABLE {table_name} AS 
        SELECT * FROM read_csv_auto('{filepath}')
        """)

        # Confirm each table loaded successfully
        print(f"✅ Loaded {table_name}")

    # Return the connection so the rest of the app can run SQL queries against it
    return conn