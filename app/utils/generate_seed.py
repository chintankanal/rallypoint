import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Connection details provided
LOCAL_DB_URL = "postgresql://postgres:ocean202@localhost:5432/jlrs"

# The sequence derived from your schema dependencies
TABLE_ORDER = [
    "system_configuration",
    "users",
    "user_identifier_history",
    "academy",
    "academy_asi_history",
    "academy_status_history",
    "player",
    "player_academy_history",
    "player_seeding_history",
    "player_status_history",
    "season",
    "event",
    "event_player_registration",
    "event_referee",
    "event_umpire",
    "session",
    "event_fixture_slot",
    "fixture_slot",
    "match",
    "match_set_score",
    "match_set_score_audit",
    "rating_history",
    "dispute",
    "system_configuration_history"
]

def generate_seed():
    conn = None
    try:
        print(f"Connecting to {LOCAL_DB_URL}...")
        conn = psycopg2.connect(LOCAL_DB_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        with open("seed.sql", "w", encoding="utf-8") as f:
            f.write("-- JLRS Data Seed File\n")
            f.write("-- Generated for Railway migration\n\n")
            f.write("BEGIN;\n\n")
            
            # List of tables successfully processed to enable triggers later
            processed_tables = []
            
            for table in TABLE_ORDER:
                print(f"Processing table: {table}...")
                try:
                    cur.execute(f"SELECT * FROM {table}")
                    rows = cur.fetchall()
                except psycopg2.errors.UndefinedTable:
                    print(f"  Skipping: Table '{table}' does not exist yet.")
                    conn.rollback()
                    continue
                
                if not rows:
                    print(f"  Table '{table}' is empty.")
                    continue
                
                processed_tables.append(table)
                
                # Disable triggers (including FK checks) for this table
                f.write(f"ALTER TABLE {table} DISABLE TRIGGER ALL;\n")
                
                f.write(f"-- Data for {table} ({len(rows)} rows)\n")
                columns = list(rows[0].keys()) # Convert dict_keys to list for consistent iteration
                col_names = ", ".join([f'"{col}"' for col in columns]) # Escape col names
                
                for row in rows:
                    vals = []
                    for col in columns:
                        val = row[col]
                        if val is None:
                            vals.append("NULL")
                        elif isinstance(val, (int, float)):
                            vals.append(str(val))
                        elif isinstance(val, bool):
                            vals.append(str(val).upper())
                        elif isinstance(val, dict) or isinstance(val, list):
                            # Handle JSONB fields
                            json_str = json.dumps(val).replace("'", "''")
                            vals.append(f"'{json_str}'")
                        else:
                            # Standard string/date escaping
                            safe_val = str(val).replace("'", "''")
                            vals.append(f"'{safe_val}'")
                    
                    f.write(f"INSERT INTO {table} ({col_names}) VALUES ({', '.join(vals)}) ON CONFLICT DO NOTHING;\n")
                f.write("\n")
            
            # Re-enable triggers in reverse order
            f.write("-- Re-enabling triggers\n")
            for table in reversed(processed_tables):
                f.write(f"ALTER TABLE {table} ENABLE TRIGGER ALL;\n")
                
            f.write("COMMIT;\n")
            
        print("\nSuccess! 'seed.sql' has been generated in the correct sequence.")
        
    except Exception as e:
        print(f"\nFailed to generate seed: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    generate_seed()
