@echo off
setlocal
echo Applying SQL schemas to jlrs database...

:: If psql is in PATH, use "psql". Otherwise, use the absolute path:
IF EXIST "C:\Program Files\PostgreSQL\18\bin\psql.exe" (
    SET "PSQL_CMD=C:\Program Files\PostgreSQL\18\bin\psql.exe"
) ELSE (
    SET "PSQL_CMD=psql"
)

SET PGPASSWORD=ocean202

:: Optimized to run in a single session, requiring only one password entry:
"%PSQL_CMD%" -h localhost -U postgres -d jlrs ^
    -f "c:\rallypoint\sql\users.sql" ^
    -f "c:\rallypoint\sql\academy.sql" ^
    -f "c:\rallypoint\sql\player.sql" ^
    -f "c:\rallypoint\sql\system_configuration.sql" ^
    -f "c:\rallypoint\sql\system_configuration_history.sql" ^
    -f "c:\rallypoint\sql\season.sql" ^
    -f "c:\rallypoint\sql\academy_asi_history.sql" ^
    -f "c:\rallypoint\sql\academy_status_history.sql" ^
    -f "c:\rallypoint\sql\player_academy_history.sql" ^
    -f "c:\rallypoint\sql\player_status_history.sql" ^
    -f "c:\rallypoint\sql\player_seeding_history.sql" ^
    -f "c:\rallypoint\sql\event.sql" ^
    -f "c:\rallypoint\sql\event_academy.sql" ^
    -f "c:\rallypoint\sql\event_referee.sql" ^
    -f "c:\rallypoint\sql\event_umpire.sql" ^
    -f "c:\rallypoint\sql\event_player_registration.sql" ^
    -f "c:\rallypoint\sql\session.sql" ^
    -f "c:\rallypoint\sql\fixture_slot.sql" ^
    -f "c:\rallypoint\sql\match.sql" ^
    -f "c:\rallypoint\sql\rating_history.sql" ^
    -f "c:\rallypoint\sql\dispute.sql" ^
    -f "c:\rallypoint\sql\dispute_status_history.sql" ^
    -f "c:\rallypoint\sql\user_identifier_history.sql" ^

echo Schema application complete.
pause
