#!/usr/bin/env python3
"""
CLI wrapper for SQL Data Management Script
Allows non-interactive usage via command line arguments.
"""

import sys
import argparse
from pathlib import Path
from manage_sql_data import SQLTableManager


def main():
    parser = argparse.ArgumentParser(
        description="SQL Data Management - Generate INSERT/DELETE statements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python manage_sql_data.py
  
  # Insert all tables
  python manage_sql_cli.py insert
  
  # Delete specific tables
  python manage_sql_cli.py delete event session match
  
  # Insert specific tables
  python manage_sql_cli.py insert event,session,match
  
  # List available tables
  python manage_sql_cli.py list
        """
    )
    
    parser.add_argument(
        'action',
        choices=['insert', 'delete', 'list'],
        help='Action to perform'
    )
    
    parser.add_argument(
        'tables',
        nargs='*',
        help='Table names (space or comma separated). Leave empty for all tables.'
    )
    
    parser.add_argument(
        '-d', '--database',
        default='postgresql://postgres:ocean202@localhost:5432/jlrs',
        help='Database URL (default: postgresql://postgres:ocean202@localhost:5432/jlrs)'
    )
    
    parser.add_argument(
        '-s', '--sql-folder',
        default='sql',
        help='SQL folder path (default: ./sql)'
    )
    
    args = parser.parse_args()
    
    sql_folder = Path(args.sql_folder)
    if not sql_folder.exists():
        print(f"[ERROR] SQL folder not found: {sql_folder}")
        sys.exit(1)
    
    manager = SQLTableManager(str(sql_folder), args.database)
    
    print("=" * 70)
    print("SQL Data Management - CLI Mode")
    print("=" * 70)
    
    # Parse SQL files
    print("\nParsing SQL files...")
    manager.parse_sql_files()
    
    if args.action == 'list':
        print(f"\nAvailable tables ({len(manager.tables)}):")
        for i, table in enumerate(sorted(manager.tables.keys()), 1):
            fks = manager.tables[table].get('foreign_keys', [])
            fk_str = f" -> {', '.join(fks)}" if fks else ""
            print(f"  {i:2}. {table:<30} {fk_str}")
        print()
        sys.exit(0)
    
    # Parse table names
    if args.tables:
        # Handle both space-separated and comma-separated
        table_list = []
        for item in args.tables:
            table_list.extend([t.strip() for t in item.split(',')])
        tables_to_process = table_list
    else:
        tables_to_process = list(manager.tables.keys())
    
    # Validate tables
    invalid_tables = [t for t in tables_to_process if t not in manager.tables]
    if invalid_tables:
        print(f"[ERROR] Invalid tables: {', '.join(invalid_tables)}")
        sys.exit(1)
    
    print(f"[OK] Processing {len(tables_to_process)} table(s): {', '.join(tables_to_process)}")
    
    # Generate and save SQL
    try:
        if args.action == 'insert':
            print("\n-> Generating INSERT statements...")
            sql_content = manager.generate_insert_statements(tables_to_process)
            action_name = 'insert'
        else:  # delete
            print("\n-> Generating DELETE statements...")
            sql_content = manager.generate_delete_statements(tables_to_process)
            action_name = 'delete'
        
        filepath = manager.save_to_file(sql_content, action_name)
        
        print("\n" + "=" * 70)
        print("[OK] SQL file generated successfully!")
        print(f"  File: {filepath}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ERROR] Operation cancelled")
        sys.exit(0)
