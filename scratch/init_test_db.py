import os
import sys
import uuid

# Add workspace to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

import psycopg2
from app.services.auth_service import hash_password

DB_URL = "postgresql://postgres:ocean202@localhost:5432/jlrs_test"

SCHEMA_FILES = [
    "sql/users.sql",
    "sql/academy.sql",
    "sql/player.sql",
    "sql/system_configuration.sql",
    "sql/system_configuration_history.sql",
    "sql/season.sql",
    "sql/academy_asi_history.sql",
    "sql/academy_status_history.sql",
    "sql/player_academy_history.sql",
    "sql/player_status_history.sql",
    "sql/player_seeding_history.sql",
    "sql/event.sql",
    "sql/event_academy.sql",
    "sql/event_referee.sql",
    "sql/event_umpire.sql",
    "sql/event_player_registration.sql",
    "sql/session.sql",
    "sql/fixture_slot.sql",
    "sql/match.sql",
    "sql/rating_history.sql",
    "sql/dispute.sql",
    "sql/dispute_status_history.sql",
    "sql/user_identifier_history.sql",
]

def init_db():
    print("Connecting to test database...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    
    with conn.cursor() as cur:
        # Enable UUID extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        
        # Execute each schema file
        for file_path in SCHEMA_FILES:
            full_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", file_path))
            print(f"Applying schema: {file_path}")
            with open(full_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
                
                # Strip SET timezone and timezone-related commands since they might fail depending on pg config
                # and psycopg2 handles transactions well.
                # Just execute the queries.
                cur.execute(sql_content)

        print("Seeding system configuration...")
        seed_cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sql/seed_system_configuration.sql"))
        with open(seed_cfg_path, "r", encoding="utf-8") as f:
            cur.execute(f.read())

        # Seed admin user
        print("Checking if admin user exists in test DB...")
        cur.execute("SELECT user_id FROM users WHERE email = %s", ("admin@test.com",))
        row = cur.fetchone()
        
        admin_id = str(uuid.uuid4())
        if not row:
            print("Seeding admin user admin@test.com...")
            admin_pass_hash = hash_password("changeme123")
            cur.execute(
                """
                INSERT INTO users (user_id, name, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, %s, 'ADMIN', True)
                """,
                (admin_id, "Test Admin", "admin@test.com", admin_pass_hash),
            )
        else:
            admin_id = row[0]
            
        # Seed an active academy so tests have one available
        print("Checking if an academy exists...")
        cur.execute("SELECT academy_id FROM academy LIMIT 1")
        academy_row = cur.fetchone()
        if not academy_row:
            print("Seeding a default active academy...")
            cur.execute(
                """
                INSERT INTO academy (academy_id, name, location, city, state, status, min_tables, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE', 4, %s, %s)
                """,
                (str(uuid.uuid4()), "Test Academy One", "Test Location", "Test City", "Test State", admin_id, admin_id),
            )

    conn.close()
    print("Test database initialization and seeding complete.")

if __name__ == "__main__":
    init_db()
