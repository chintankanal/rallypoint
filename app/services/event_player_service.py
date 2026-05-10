from app.database import get_connection


def list_players(event_id: str) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT epr.registration_id::text, epr.player_id::text,
                       p.name, p.current_rating,
                       p.primary_academy_id::text AS academy_id,
                       a.name AS academy_name,
                       epr.status, epr.registered_at
                FROM event_player_registration epr
                JOIN player p ON p.player_id = epr.player_id
                JOIN academy a ON a.academy_id = p.primary_academy_id
                WHERE epr.event_id = %s
                  AND epr.status IN ('REGISTERED', 'CHECKED_IN')
                ORDER BY a.name, p.current_rating DESC
                """,
                (event_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def register_player(
    event_id: str,
    player_id: str,
    registered_by: str,
    caller_role: str,
    caller_academy_id: str | None,
    caller_user_id: str,
) -> dict | None:
    """
    Registers a player for an INTER_ACADEMY event.
    - ADMIN: any player whose academy participates
    - COACH: only players from their own academy
    - PLAYER: only themselves (verified via player.user_id)
    Returns the registration dict, None if event or player not found.
    Raises ValueError for authorization / business rule violations.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT scheduling_mode, status, fixture_state FROM event WHERE event_id = %s",
                (event_id,),
            )
            event = cur.fetchone()
            if not event:
                return None
            if event["scheduling_mode"] != "INTER_ACADEMY":
                raise ValueError("Player registration only applies to INTER_ACADEMY events")
            if event["status"] not in ("SCHEDULED", "IN_PROGRESS"):
                raise ValueError("Cannot register players for a completed or cancelled event")
            if event["fixture_state"] and event["fixture_state"] != "ROSTER_OPEN":
                raise ValueError(
                    f"Cannot modify roster: fixtures have been generated ({event['fixture_state']}). "
                    "Regenerate fixtures to add or remove players."
                )

            cur.execute(
                "SELECT player_id, primary_academy_id, status, user_id FROM player WHERE player_id = %s",
                (player_id,),
            )
            player = cur.fetchone()
            if not player:
                return None
            if player["status"] != "ACTIVE":
                raise ValueError("Cannot register an inactive player")

            if caller_role == "COACH":
                if str(player["primary_academy_id"]) != caller_academy_id:
                    raise ValueError("Coaches can only register players from their own academy")
            elif caller_role == "PLAYER":
                if player["user_id"] is None or str(player["user_id"]) != caller_user_id:
                    raise ValueError("Players can only register themselves")

            # Auto-link the player's academy to the event if not already present
            cur.execute(
                """
                INSERT INTO event_academy (event_id, academy_id, added_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (event_id, academy_id) DO NOTHING
                """,
                (event_id, str(player["primary_academy_id"]), registered_by),
            )

            # Upsert: re-register if previously withdrawn / no-show
            cur.execute(
                """
                INSERT INTO event_player_registration (event_id, player_id, registered_by, status)
                VALUES (%s, %s, %s, 'REGISTERED')
                ON CONFLICT (event_id, player_id)
                DO UPDATE SET status = 'REGISTERED',
                              registered_by = EXCLUDED.registered_by,
                              registered_at = NOW()
                WHERE event_player_registration.status IN ('WITHDRAWN', 'NO_SHOW')
                """,
                (event_id, player_id, registered_by),
            )

            cur.execute(
                """
                SELECT epr.registration_id::text, epr.player_id::text,
                       p.name, p.current_rating,
                       p.primary_academy_id::text AS academy_id,
                       a.name AS academy_name,
                       epr.status, epr.registered_at
                FROM event_player_registration epr
                JOIN player p ON p.player_id = epr.player_id
                JOIN academy a ON a.academy_id = p.primary_academy_id
                WHERE epr.event_id = %s AND epr.player_id = %s
                """,
                (event_id, player_id),
            )
            return dict(cur.fetchone())


def remove_player(
    event_id: str,
    player_id: str,
    withdrawn_by: str,
    caller_role: str,
    caller_academy_id: str | None,
    caller_user_id: str,
) -> bool:
    """
    Withdraws a player from the event (sets status = WITHDRAWN).
    Returns True if withdrawn, False if registration not found / already withdrawn.
    Raises ValueError for authorization violations.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fixture_state FROM event WHERE event_id = %s",
                (event_id,),
            )
            ev = cur.fetchone()
            if ev and ev["fixture_state"] and ev["fixture_state"] != "ROSTER_OPEN":
                raise ValueError(
                    f"Cannot modify roster: fixtures have been generated ({ev['fixture_state']}). "
                    "Regenerate fixtures to add or remove players."
                )

            cur.execute(
                """
                SELECT epr.status,
                       p.primary_academy_id::text,
                       p.user_id::text
                FROM event_player_registration epr
                JOIN player p ON p.player_id = epr.player_id
                WHERE epr.event_id = %s AND epr.player_id = %s
                """,
                (event_id, player_id),
            )
            row = cur.fetchone()
            if not row or row["status"] not in ("REGISTERED", "CHECKED_IN"):
                return False

            if caller_role == "COACH":
                if row["primary_academy_id"] != caller_academy_id:
                    raise ValueError("Coaches can only remove players from their own academy")
            elif caller_role == "PLAYER":
                if row["user_id"] != caller_user_id:
                    raise ValueError("Players can only withdraw themselves")

            cur.execute(
                """
                UPDATE event_player_registration
                SET status = 'WITHDRAWN', withdrawn_at = NOW(), withdrawn_by = %s
                WHERE event_id = %s AND player_id = %s
                """,
                (withdrawn_by, event_id, player_id),
            )
            return True
