# Age Category Change Plan: U10 → U11

## Summary

This plan documents the full change required to replace the current `U10` age category with `U11` while keeping the other age categories (`U13`, `U15`, `U17`) unchanged.

## Assumption

The intended behavior is:
- `U11` should replace `U10`
- `U11` should cover ages `<= 11`
- `U13` remains and will effectively cover ages `12-13`
- `U15` remains and will cover ages `14-15`
- `U17` remains and will cover ages `16-17`

If the requirement is only a label rename without changing the boundary, update the implementation accordingly, but the safer interpretation is to shift the first bracket to age 11.

## Impacted areas

1. Application logic
   - `app/utils/rating_math.py`
   - `app/services/leaderboard_service.py`
   - `app/services/academy_service.py`
   - `app/routers/leaderboard.py`
   - `schemas/enums.py`

2. Configuration and seed data
   - `sql/seed_system_configuration.sql`
   - existing `system_configuration` database rows

3. Frontend
   - `web/src/pages/Leaderboard.tsx`

4. Tests
   - `test_config_loading.py`
   - `tests/unit/test_computed_stats.py`

5. Documentation
   - `docs/jlrs_api_contract.md`
   - `docs/jlrs_impl_plan.md`
   - any other docs or UX copy referencing `U10`

## Required changes

### 1. Code updates

- Rename age-group enum values from `U10` to `U11` in `schemas/enums.py`.
- Update age-group boundary config references in `app/utils/rating_math.py`:
  - Add `age_group_u11_max` default
  - Remove or deprecate `age_group_u10_max`
  - Change `get_age_group()` to return `U11` for ages `<= 11`
- Update SQL-generated age-group logic in:
  - `app/services/leaderboard_service.py`
  - `app/services/academy_service.py`
  - Replace `WHEN ... THEN 'U10'` with `WHEN ... THEN 'U11'`
  - Update `VALID_AGE_GROUPS` from `{"U10", "U13", "U15", "U17"}` to `{"U11", "U13", "U15", "U17"}`
- Update API query descriptions in `app/routers/leaderboard.py` to list `U11` instead of `U10`.

### 2. Config and migraton

- Update `sql/seed_system_configuration.sql`:
  - Change `('age_group_u10_max', '10', 'Maximum age for U10 group')`
  - To `('age_group_u11_max', '11', 'Maximum age for U11 group')`
- Ensure runtime config keys are updated in fallback/default logic.
- Add migration or manual DB patch to:
  - rename existing `system_configuration` key `age_group_u10_max` to `age_group_u11_max`
  - update the value from `10` to `11`
- Optionally keep fallback support for old key while migrating.

### 3. Frontend updates

- Change leaderboard filter option in `web/src/pages/Leaderboard.tsx` from `U10` to `U11`.
- Search the frontend for any additional `U10` labels and replace them.

### 4. Tests

- Update `test_config_loading.py`:
  - change key list to include `age_group_u11_max`
  - update boundary expectations and printed descriptions if age boundary shifts
- Update `tests/unit/test_computed_stats.py`:
  - change expected results from `U10` to `U11`
  - if age boundary shifts to 11, adjust test ages accordingly
- Add regression coverage for the new `U11` label and allowed age-group query values.

### 5. Documentation

- Update `docs/jlrs_api_contract.md`:
  - change age-group notes from `U10` to `U11`
  - adjust examples and age-group listing for `analytics/leaderboard`
- Update `docs/jlrs_impl_plan.md` wherever age group boundaries are documented.
- Search for `U10` across docs and UX files and replace with `U11` where appropriate.

## Detailed implementation checklist

1. Update default config mapping in `app/utils/rating_math.py`:
   - `_DEFAULTS['age_group_u11_max'] = 11.0`
   - remove or alias `_DEFAULTS['age_group_u10_max']`
   - `get_age_group()` should use `u11_max` and return `"U11"`

2. Update config loading and fallback behavior:
   - if `age_group_u11_max` missing, fallback to `age_group_u10_max` for migration safety
   - update SQL service functions to use new key names

3. Update labels and allowed values in service-level constants and router descriptions.

4. Update seed and any DB migration scripts.

5. Update tests and rerun:
   - `pytest tests/unit/test_computed_stats.py`
   - `python test_config_loading.py`
   - any relevant API or integration tests

6. Update UI and docs.

## Verification criteria

- New age-group label `U11` appears in API responses, frontend selection, and documentation.
- Age grouping logic returns:
  - age `<= 11` → `U11`
  - age `12-13` → `U13`
  - age `14-15` → `U15`
  - age `16-17` → `U17`
  - age `> 17` → `OPEN`
- No remaining runtime or documentation references to `U10`.
- Existing DB config migrations are handled cleanly and tests pass.

## Notes

- Because the code currently uses `age_group_u10_max` as the active config key, the safest migration path is to introduce `age_group_u11_max` while preserving fallback from `age_group_u10_max` until the database is updated.
- If the requirement is only to rename `U10` text without shifting age coverage, then adjust the boundary mapping accordingly and do not change the `age_group_u13_max` boundary.
