# SQL Data Management Script

## Overview
`manage_sql_data.py` is a Python utility that automates the generation of INSERT and DELETE SQL statements for your database tables, with automatic dependency ordering.

## Features
- **Automatic Dependency Analysis**: Parses SQL files to determine table relationships and foreign keys
- **Smart Insertion Order**: Automatically orders tables based on foreign key dependencies for conflict-free inserts
- **Smart Deletion Order**: Reverses the insertion order to respect referential integrity constraints
- **Timestamped Output**: Generates uniquely named migration files with date and counter
- **Column-Complete Inserts**: Generates INSERT statements that specify all columns explicitly
- **Conflict-Safe**: Uses proper value formatting to avoid SQL injection and syntax errors
- **Interactive**: User-friendly prompts for action selection and table choice

## Prerequisites
1. Python 3.7+
2. `psycopg2` library (included in rallypoint requirements)
3. Access to the local PostgreSQL database

## Database Configuration
The script uses the following connection string (hardcoded):
```
postgresql://postgres:ocean202@localhost:5432/jlrs
```

Modify the `db_url` variable in `main()` if your database credentials differ.

## Usage

### Run the Script
```bash
cd c:\rallypoint
python manage_sql_data.py
```

### Interactive Prompts
The script will display:
1. **Available Tables**: List of all parsed tables with their dependencies
2. **Action Selection**: Choose between:
   - `1` - Generate INSERT statements
   - `2` - Generate DELETE statements
3. **Table Selection**: Enter comma-separated table names (or leave blank for all tables)

### Example Session
```
Action: 1
Tables: event, session, match

✓ Saved to: c:\rallypoint\sql\migrations\insert_05062026-1.sql
```

## Output Files

### Insert Migration
**Filename**: `insert_ddmmyyyy-counter.sql`
- Contains INSERT INTO statements for selected tables
- Tables are ordered by dependencies (no foreign key violations)
- All columns are explicitly specified
- Wrapped in a transaction (BEGIN; ... COMMIT;)

### Delete Migration
**Filename**: `delete_ddmmyyyy-counter.sql`
- Contains DELETE FROM statements for selected tables
- Tables are ordered in reverse dependency order (respects constraints)
- Wrapped in a transaction (BEGIN; ... COMMIT;)

## How It Works

### 1. SQL File Parsing
- Scans the `sql/` folder for `*.sql` files
- Extracts table definitions using regex patterns
- Identifies foreign key relationships
- Builds a dependency graph

### 2. Dependency Ordering
**Insertion Order**: Topological sort ensuring parent tables are inserted before children
```
season → event → session → match → fixture_slot → match_set_score
```

**Deletion Order**: Reverse of insertion order
```
match_set_score → fixture_slot → match → session → event → season
```

### 3. Data Retrieval
- Connects to the local database
- Fetches all rows from selected tables
- Retrieves column metadata (names, types, nullability)

### 4. SQL Generation
- Formats values based on data types (NULL, boolean, string, numeric, JSON)
- Generates parameterized INSERT statements
- Wraps everything in a transaction for atomicity

## Examples

### Generate Insert for Specific Tables
```
Tables: event, session, match
```
Output: `insert_05062026-1.sql` with INSERT statements for these 3 tables in proper order

### Generate Delete for All Tables
```
Tables: [leave blank]
Action: 2
```
Output: `delete_05062026-1.sql` with DELETE statements for all tables in proper order

### Generate Multiple Migrations
Running the script multiple times on the same day creates:
- `insert_05062026-1.sql`
- `insert_05062026-2.sql` (next run)
- `insert_05062026-3.sql` (third run)

## Migration Execution

### Apply an Insert Migration
```bash
psql postgresql://postgres:ocean202@localhost:5432/jlrs < sql\migrations\insert_05062026-1.sql
```

### Apply a Delete Migration
```bash
psql postgresql://postgres:ocean202@localhost:5432/jlrs < sql\migrations\delete_05062026-1.sql
```

## Advanced: Manual Edits

After generation, you can manually edit the `.sql` files:
1. Remove specific INSERT/DELETE statements as needed
2. Add WHERE clauses to DELETE statements for selective deletion
3. Modify values in INSERT statements for test data

Example: Delete only recent records
```sql
DELETE FROM public.match WHERE match_date > '2026-05-31';
```

## Troubleshooting

### Database Connection Failed
- Verify PostgreSQL is running: `psql -U postgres -h localhost -d jlrs`
- Check credentials: `postgresql://postgres:ocean202@localhost:5432/jlrs`
- Update the `db_url` in the script if credentials have changed

### Table Not Found
- Ensure SQL file exists in `sql/` folder
- Check for typos in table names (case-sensitive)
- Verify the CREATE TABLE statement is present in the SQL file

### Foreign Key Violations on Insert
- This shouldn't happen if dependencies are correctly parsed
- Manually verify the generated INSERT order
- Check for circular dependencies in your schema

### Foreign Key Violations on Delete
- Ensure all dependent records are deleted first
- Use the generated delete order (reverse dependency order)
- Manually inspect the DELETE statement order if needed

## Customization

### Change Database URL
Edit line in `main()`:
```python
db_url = "postgresql://postgres:ocean202@localhost:5432/jlrs"
```

### Add Custom Table Ordering
Modify `_compute_insertion_order()` method to add manual overrides

### Change Output Folder
Edit the `migrations_folder` path in `save_to_file()`:
```python
migrations_folder = self.sql_folder / "migrations"
```

## Performance Notes
- Script scans all SQL files once at startup
- Database queries are performed sequentially
- For large tables (10K+ rows), generation may take a few seconds
- Output files can be several MB for large datasets

## Limitations
- Requires explicit database connectivity (no offline mode)
- Does not validate data integrity constraints
- Assumes standard PostgreSQL schema structure
- Does not handle cascading deletes or triggers

## Future Enhancements
- [ ] Support for WHERE clauses in DELETE generation
- [ ] Batch insert mode for large datasets
- [ ] UPSERT (ON CONFLICT) support
- [ ] Schema validation and conflict detection
- [ ] Dry-run mode
- [ ] Data sampling for large tables
