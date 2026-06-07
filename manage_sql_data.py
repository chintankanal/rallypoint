#!/usr/bin/env python3
"""
SQL Data Management Script
Manages insertion and deletion of data across tables with proper dependency ordering.
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
import psycopg2
from psycopg2.extras import RealDictCursor


class SQLTableManager:
    """Manages SQL table metadata and dependencies."""
    
    def __init__(self, sql_folder: str, db_url: str):
        self.sql_folder = Path(sql_folder)
        self.db_url = db_url
        self.tables: Dict[str, Dict] = {}
        self.table_order_insert: List[str] = []
        self.table_order_delete: List[str] = []
        self.conn = None
        
    def connect_db(self) -> None:
        """Connect to the database."""
        try:
            self.conn = psycopg2.connect(self.db_url)
            print("[OK] Connected to database successfully")
        except psycopg2.Error as e:
            print(f"[ERROR] Database connection failed: {e}")
            sys.exit(1)
    
    def disconnect_db(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def parse_sql_files(self) -> None:
        """Parse SQL files to extract table definitions and relationships."""
        sql_files = sorted(self.sql_folder.glob("*.sql"))
        
        for sql_file in sql_files:
            if sql_file.name.startswith(("seed", "migration", "009_")):
                continue
                
            content = sql_file.read_text(encoding='utf-8')
            
            # Extract table name
            table_match = re.search(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(?:public\.)?(\w+)\s*\(', content)
            if not table_match:
                continue
            
            table_name = table_match.group(1)
            
            # Extract foreign keys
            fk_pattern = r'REFERENCES\s+(?:public\.)?(\w+)\s*\('
            foreign_keys = re.findall(fk_pattern, content)
            
            # Extract column names and types
            columns = self._extract_columns(content, table_name)
            
            self.tables[table_name] = {
                'file': sql_file.name,
                'foreign_keys': list(set(foreign_keys)),
                'columns': columns
            }
        
        print(f"[OK] Parsed {len(self.tables)} tables")
        self._compute_insertion_order()
        self._compute_deletion_order()
    
    def _extract_columns(self, content: str, table_name: str) -> Dict[str, str]:
        """Extract column definitions from CREATE TABLE statement."""
        columns = {}
        
        # Find the CREATE TABLE block
        create_match = re.search(
            rf'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(?:public\.)?{re.escape(table_name)}\s*\((.*?)\);',
            content,
            re.DOTALL
        )
        
        if not create_match:
            return columns
        
        table_def = create_match.group(1)
        
        # Split by comma but be careful with nested parens
        lines = table_def.split('\n')
        paren_depth = 0
        current_col = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            paren_depth += line.count('(') - line.count(')')
            
            if paren_depth == 0 and (',' in line or 'CONSTRAINT' not in line):
                if current_col:
                    current_col += " " + line
                else:
                    current_col = line
                
                if line.endswith(',') or 'CONSTRAINT' in line or 'PRIMARY KEY' in line:
                    col_def = current_col.rstrip(',').strip()
                    if col_def and not col_def.startswith('CONSTRAINT') and not col_def.startswith('PRIMARY'):
                        parts = col_def.split()
                        if parts:
                            col_name = parts[0]
                            col_type = " ".join(parts[1:])
                            columns[col_name] = col_type
                    current_col = ""
            else:
                current_col += " " + line if current_col else line
        
        return columns
    
    def _compute_insertion_order(self) -> None:
        """Compute insertion order based on foreign key dependencies."""
        visited = set()
        order = []
        
        def visit(table: str):
            if table in visited:
                return
            visited.add(table)
            
            if table in self.tables:
                for fk in self.tables[table].get('foreign_keys', []):
                    if fk in self.tables:
                        visit(fk)
            
            order.append(table)
        
        for table in self.tables.keys():
            visit(table)
        
        self.table_order_insert = order
    
    def _compute_deletion_order(self) -> None:
        """Compute deletion order (reverse of insertion order)."""
        self.table_order_delete = list(reversed(self.table_order_insert))
    
    def get_table_columns(self, table_name: str) -> List[Tuple[str, str, bool]]:
        """Get column information from database."""
        if not self.conn:
            return []
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                
                columns = []
                for row in cur.fetchall():
                    columns.append((
                        row['column_name'],
                        row['data_type'],
                        row['is_nullable'] == 'YES'
                    ))
                return columns
        except psycopg2.Error as e:
            print(f"[ERROR] Error fetching columns for {table_name}: {e}")
            return []
    
    def get_table_data(self, table_name: str) -> List[Dict]:
        """Fetch all data from a table."""
        if not self.conn:
            return []
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM {table_name} ORDER BY ctid")
                return cur.fetchall()
        except psycopg2.Error as e:
            print(f"[ERROR] Error fetching data from {table_name}: {e}")
            return []
    
    def get_insertion_order(self, tables: List[str]) -> List[str]:
        """Get insertion order for specified tables."""
        order = []
        for table in self.table_order_insert:
            if table in tables:
                order.append(table)
        return order
    
    def get_deletion_order(self, tables: List[str]) -> List[str]:
        """Get deletion order for specified tables."""
        order = []
        for table in self.table_order_delete:
            if table in tables:
                order.append(table)
        return order
    
    def format_value(self, value) -> str:
        """Format a database value for SQL."""
        if value is None:
            return "NULL"
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, dict):
            # For JSONB
            import json
            escaped = json.dumps(value).replace("'", "''")
            return f"'{escaped}'::jsonb"
        else:
            return f"'{str(value)}'"
    
    def generate_insert_statements(self, tables: List[str]) -> str:
        """Generate INSERT statements for specified tables."""
        self.connect_db()
        
        statements = []
        statements.append("-- Auto-generated INSERT statements")
        statements.append("-- Generated on: " + datetime.now().isoformat())
        statements.append("BEGIN;\n")
        
        order = self.get_insertion_order(tables)
        
        for table_name in order:
            if table_name not in self.tables:
                print(f"[WARN] Table {table_name} not found in schema")
                continue
            
            columns = self.get_table_columns(table_name)
            if not columns:
                print(f"[WARN] Could not get columns for {table_name}")
                continue
            
            data = self.get_table_data(table_name)
            
            col_names = [col[0] for col in columns]
            col_list = ", ".join(col_names)
            
            if data:
                statements.append(f"\n-- Insert data into {table_name} ({len(data)} rows)")
                for row in data:
                    values = []
                    for col_name in col_names:
                        values.append(self.format_value(row.get(col_name)))
                    value_list = ", ".join(values)
                    stmt = f"INSERT INTO {table_name} ({col_list}) VALUES ({value_list}) ON CONFLICT DO NOTHING;"
                    statements.append(stmt)
            else:
                statements.append(f"\n-- No data in {table_name}")
        
        statements.append("\nCOMMIT;")
        self.disconnect_db()
        
        return "\n".join(statements)
    
    def generate_delete_statements(self, tables: List[str]) -> str:
        """Generate DELETE statements for specified tables."""
        statements = []
        statements.append("-- Auto-generated DELETE statements")
        statements.append("-- Generated on: " + datetime.now().isoformat())
        statements.append("BEGIN;\n")
        
        order = self.get_deletion_order(tables)
        
        for table_name in order:
            if table_name in self.tables:
                statements.append(f"DELETE FROM {table_name};")
        
        statements.append("\nCOMMIT;")
        
        return "\n".join(statements)
    
    def save_to_file(self, content: str, action: str) -> str:
        """Save generated SQL to a file with timestamp and counter."""
        migrations_folder = self.sql_folder / "migrations"
        migrations_folder.mkdir(exist_ok=True)
        
        # Generate filename with date and counter
        today = datetime.now().strftime("%d%m%Y")
        counter = 1
        
        while True:
            filename = f"{action}_{today}-{counter}.sql"
            filepath = migrations_folder / filename
            if not filepath.exists():
                break
            counter += 1
        
        filepath.write_text(content, encoding='utf-8')
        print(f"[OK] Saved to: {filepath}")
        return str(filepath)


def main():
    """Main entry point."""
    sql_folder = Path(__file__).parent / "sql"
    db_url = "postgresql://postgres:ocean202@localhost:5432/jlrs"
    
    manager = SQLTableManager(str(sql_folder), db_url)
    
    print("=" * 70)
    print("SQL Data Management Script")
    print("=" * 70)
    
    # Parse SQL files
    manager.parse_sql_files()
    
    print(f"\nAvailable tables ({len(manager.tables)}):")
    for i, table in enumerate(manager.tables.keys(), 1):
        fks = manager.tables[table].get('foreign_keys', [])
        fk_str = f" (depends on: {', '.join(fks)})" if fks else ""
        print(f"  {i}. {table}{fk_str}")
    
    # Get user action
    print("\n" + "=" * 70)
    print("Actions:")
    print("  1 = Insert data from database")
    print("  2 = Delete data from tables")
    print("=" * 70)
    
    while True:
        action_input = input("\nEnter action (1 or 2): ").strip()
        if action_input in ['1', '2']:
            break
        print("[ERROR] Invalid action. Please enter 1 or 2.")
    
    action_type = "insert" if action_input == "1" else "delete"
    
    # Get table names
    print("\nEnter table names (comma-separated) or leave blank for all tables:")
    table_input = input("Tables: ").strip()
    
    if table_input:
        requested_tables = [t.strip() for t in table_input.split(",")]
        invalid_tables = [t for t in requested_tables if t not in manager.tables]
        if invalid_tables:
            print(f"[ERROR] Invalid tables: {', '.join(invalid_tables)}")
            sys.exit(1)
        tables_to_process = requested_tables
    else:
        tables_to_process = list(manager.tables.keys())
    
    print(f"\n[OK] Processing {len(tables_to_process)} table(s)")
    
    # Generate and save SQL
    if action_type == "insert":
        print("\nGenerating INSERT statements...")
        sql_content = manager.generate_insert_statements(tables_to_process)
    else:
        print("\nGenerating DELETE statements...")
        sql_content = manager.generate_delete_statements(tables_to_process)
    
    filepath = manager.save_to_file(sql_content, action_type)
    
    print("\n" + "=" * 70)
    print(f"[OK] SQL file generated successfully!")
    print(f"[OK] File: {filepath}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[ERROR] Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
