# SQL Data Management Script - Quick Start Guide

## Files Created

1. **manage_sql_data.py** - Main interactive script
2. **manage_sql_cli.py** - CLI wrapper for automation
3. **MANAGE_SQL_DATA_README.md** - Comprehensive documentation

## Quick Examples

### List All Available Tables
```bash
python manage_sql_cli.py list
```

Output shows:
- 25 tables parsed from the sql/ folder
- Each table's foreign key dependencies
- Proper insertion/deletion order

### Generate INSERT Migration for Event Table
```bash
python manage_sql_cli.py insert event
```

Creates: `sql\migrations\insert_05062026-1.sql`
- Contains 7 INSERT statements for all event records
- All columns explicitly specified
- Ready to apply to a clean database

### Generate INSERT for Multiple Tables
```bash
python manage_sql_cli.py insert event,session,match
```

Creates: `sql\migrations\insert_05062026-2.sql`
- Inserts event first, then session, then match
- Respects foreign key dependencies
- All data from local database

### Generate DELETE Migration
```bash
python manage_sql_cli.py delete event,session,match
```

Creates: `sql\migrations\delete_05062026-1.sql`
- Deletes match first, then session, then event
- Reverse dependency order (respects constraints)
- Safe deletion order

### Interactive Mode (Full Control)
```bash
python manage_sql_data.py
```

Prompts for:
1. Action (1=Insert, 2=Delete)
2. Table names (or all if blank)

## File Naming Convention

Generated files use this pattern:
```
{action}_{DDMMYYYY}-{counter}.sql
```

Examples:
- `insert_05062026-1.sql` - First insert migration on June 5, 2026
- `insert_05062026-2.sql` - Second insert migration on same day
- `delete_05062026-1.sql` - First delete migration on same day

## Applying Generated Migrations

### Using psql
```bash
# Apply an insert migration
psql postgresql://postgres:ocean202@localhost:5432/jlrs < sql\migrations\insert_05062026-1.sql

# Apply a delete migration
psql postgresql://postgres:ocean202@localhost:5432/jlrs < sql\migrations\delete_05062026-1.sql
```

### Using Railway
```bash
# Apply via Railway
railway run psql "postgresql://..." -f sql\migrations\insert_05062026-1.sql
```

## Common Use Cases

### Backup Current Data
```bash
# Export all table data to insert statement
python manage_sql_cli.py insert
```
Creates full backup in INSERT format

### Reset Specific Tables
```bash
# Delete tables in correct order
python manage_sql_cli.py delete match fixture_slot session event

# Then regenerate from seed
python manage_sql_cli.py insert event session match fixture_slot
```

### Mirror Data Between Databases
```bash
# Generate insert statements from local database
python manage_sql_cli.py insert event session

# Run on remote database
railway run psql "postgresql://..." -f sql\migrations\insert_*.sql
```

### Create Test Fixtures
```bash
# Generate inserts for test data
python manage_sql_cli.py insert event session event_player_registration
```

## Dependency Analysis

The script automatically detects and respects:

**Insertion Order** (parents before children):
```
season → event → session → match → fixture_slot
                     ↓
            event_player_registration
                     ↓
            event_fixture_slot
```

**Deletion Order** (children before parents):
```
fixture_slot ← match ← session ← event ← season
    ↑
event_fixture_slot
    ↑
event_player_registration
```

## Advanced: Manual Editing

After generation, you can:

### Selective Deletion
```sql
-- Delete only recent matches
DELETE FROM public.match WHERE match_date > '2026-05-31';
```

### Filter Inserts
```sql
-- Insert only specific events
INSERT INTO public.event ... WHERE event_type = 'LEAGUE';
```

### Add Conditions
```sql
-- Selective data sync
INSERT INTO public.session ...
ON CONFLICT DO NOTHING;
```

## Troubleshooting

### "Database connection failed"
- Verify PostgreSQL running: `psql -U postgres -h localhost -d jlrs`
- Check port: default is 5432
- Update connection string if needed

### "Table not found in schema"
- Ensure SQL file exists in `sql/` folder
- Check CREATE TABLE statement syntax
- Verify table name is unique

### Unicode/Encoding Errors (Windows)
- Script already handles this automatically
- If issues persist, use: `python -c "chr(0x1f5f9)"` to test

### "Foreign key constraint violation"
- Verify dependency order in generated SQL
- Check that parent records exist before inserts
- Review foreign key definitions

## Performance Tips

### Large Tables (10K+ rows)
```bash
# Generate in batches
python manage_sql_cli.py insert season event  # Parents first
python manage_sql_cli.py insert match session  # Then children
```

### One-Time Setup
```bash
# Generate and save all migrations
python manage_sql_cli.py insert > all_inserts.sql
python manage_sql_cli.py delete > all_deletes.sql

# Then apply as needed
```

### Check Before Applying
```bash
# Preview SQL without applying
cat sql/migrations/insert_05062026-1.sql | head -20
```

## Configuration

### Change Database URL
Edit `manage_sql_cli.py` line or use CLI flag:
```bash
python manage_sql_cli.py insert -d "postgresql://user:pass@host:5432/db"
```

### Change SQL Folder
```bash
python manage_sql_cli.py insert -s "./schemas"
```

## Summary

| Task | Command |
|------|---------|
| List tables | `python manage_sql_cli.py list` |
| Insert all | `python manage_sql_cli.py insert` |
| Insert specific | `python manage_sql_cli.py insert event,session` |
| Delete all | `python manage_sql_cli.py delete` |
| Delete specific | `python manage_sql_cli.py delete match,fixture_slot` |
| Interactive | `python manage_sql_data.py` |
| Apply migration | `psql ... -f sql\migrations\insert_*.sql` |

## Support

For detailed documentation, see: **MANAGE_SQL_DATA_README.md**
