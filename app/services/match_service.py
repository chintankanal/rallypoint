"""
Match lifecycle service: submit, confirm, dispute, void.
All functions accept an open psycopg2 connection — callers manage the transaction.
"""
import uuid
from datetime import date, datetime, timezone

import psycopg2.errors

from app.utils.timezone import end_of_day_ist

# Set score tables for validating winner sets per format
_REQUIRED_WINNER_SETS = {"BEST_OF_3": 2, "BEST_OF_5": 3, "BEST_OF_7": 4}

# Ratings trigger label per scheduling mode
_RATINGS_TRIGGER = {
    "INTRA_ACADEMY": "DAILY_EOD",
    "INTER_ACADEMY": "EVENT_COMPLETION",
}


def _canonical_order(player_a_id: str, player_b_id: str, sets_a: int, sets_b: int,
                     sets_a_actual: int | None, sets_b_actual: int | None):
    """Ensure player_a_id < player_b_id lexicographically, swapping scores if needed."""
    if player_a_id <= player_b_id:
        return player_a_id, player_b_id, sets_a, sets_b, sets_a_actual, sets_b_actual
    return (player_b_id, player_a_id, sets_b, sets_a,
            sets_b_actual, sets_a_actual)


def _check_gap_band_eligibility(
    gap_band: str | None,
    player_a_rating: float,
    player_b_rating: float,
) -> tuple[bool, str | None]:
    """
    Determine if match is rating-eligible based on fixture gap_band semantics.
    """
    gap_cap = 500

    if gap_band == "BYE":
        return False, "BYE_NO_OPPONENT"

    if gap_band == "OUT_OF_BAND":
        if abs(player_a_rating - player_b_rating) > gap_cap:
            return False, "OUT_OF_BAND_EXCEEDS_CAP"
        return True, None

    if abs(player_a_rating - player_b_rating) > gap_cap:
        return False, "RATING_GAP_EXCEEDED"

    return True, None


def _check_eligibility(
    player_a_rating: float,
    player_b_rating: float,
    sets_won_a: int,
    sets_won_b: int,
    is_retirement: bool,
    match_format: str,
    gap_band: str | None = None,
) -> tuple[bool, str | None]:
    """
    Returns (rating_eligible, not_eligible_reason | None).
    Evaluated at submission time using raw current ratings.
    """
    required = _REQUIRED_WINNER_SETS.get(match_format, 0)

    # Walkover: 0-0 and NOT retirement
    if sets_won_a == 0 and sets_won_b == 0 and not is_retirement:
        return False, "WALKOVER"

    # Retirement with zero physical sets played
    if is_retirement and sets_won_a == 0 and sets_won_b == 0:
        return False, "ZERO_SETS_RETIREMENT"

    return _check_gap_band_eligibility(gap_band, player_a_rating, player_b_rating)


def _check_diminishing_signal(cur, player_a_id: str, player_b_id: str, match_date: date) -> bool:
    """Return True if this pair has played ≥ diminishing_signal_count times in the last diminishing_signal_days days."""
    from datetime import timedelta
    cur.execute(
        "SELECT key, value FROM system_configuration WHERE key IN ('diminishing_signal_days', 'diminishing_signal_count')"
    )
    cfg = {r["key"]: int(r["value"]) for r in cur.fetchall()}
    window_days = cfg.get("diminishing_signal_days", 7)
    threshold = cfg.get("diminishing_signal_count", 2)

    window_start = match_date - timedelta(days=window_days)
    a, b = (player_a_id, player_b_id) if player_a_id < player_b_id else (player_b_id, player_a_id)
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM match
        WHERE player_a_id = %s
          AND player_b_id = %s
          AND match_date >= %s
          AND match_date <= %s
          AND confirmation_status NOT IN ('VOIDED')
        """,
        (a, b, window_start, match_date),
    )
    row = cur.fetchone()
    return row["cnt"] >= threshold


def submit_match(conn, body, submitted_by_user_id: str, caller_role: str = "") -> dict:
    """
    Persist a new match.  Raises:
      - psycopg2.errors.UniqueViolation  → caller converts to 409 MATCH_DUPLICATE
      - ValueError                        → caller converts to 400
      - PermissionError                   → caller converts to 403
    """
    with conn.cursor() as cur:
        # Resolve event to get scheduling_mode and default match format
        cur.execute(
            "SELECT event_id, scheduling_mode, event_type, default_match_format, status, fixture_state "
            "FROM event WHERE event_id = %s",
            (body.event_id,),
        )
        event = cur.fetchone()
        if not event:
            raise ValueError("Event not found")
        if event["status"] not in ("SCHEDULED", "IN_PROGRESS"):
            raise ValueError(f"Cannot submit matches for event with status '{event['status']}'")

        if event["scheduling_mode"] == "INTER_ACADEMY":
            if event["fixture_state"] not in ("FIXTURE_FROZEN", "RESULTS_SUBMITTED"):
                raise PermissionError(
                    "Inter-academy fixtures must be locked before submitting results"
                )
            if caller_role == "COACH":
                raise PermissionError(
                    "Coaches cannot submit match results for inter-academy events — only players, umpires, or referees may submit"
                )

        # Load players and validate active status
        for pid in (body.player_a_id, body.player_b_id):
            cur.execute(
                "SELECT player_id, current_rating, rated_matches_completed, primary_academy_id "
                "FROM player WHERE player_id = %s AND status = 'ACTIVE'",
                (pid,),
            )
            if not cur.fetchone():
                raise ValueError(f"Player {pid} not found or inactive")

        if caller_role == "PLAYER":
            cur.execute(
                "SELECT player_id FROM player WHERE user_id = %s AND status = 'ACTIVE'",
                (submitted_by_user_id,),
            )
            linked_player = cur.fetchone()
            if not linked_player:
                raise PermissionError(
                    "PLAYER accounts must be linked to an active player profile to submit results"
                )
            if linked_player["player_id"] not in (body.player_a_id, body.player_b_id):
                raise PermissionError(
                    "Players can only submit results for matches they participated in"
                )

        cur.execute(
            "SELECT player_id, current_rating, primary_academy_id "
            "FROM player WHERE player_id = %s",
            (body.player_a_id,),
        )
        player_a = cur.fetchone()
        cur.execute(
            "SELECT player_id, current_rating, primary_academy_id "
            "FROM player WHERE player_id = %s",
            (body.player_b_id,),
        )
        player_b = cur.fetchone()

        match_format = body.match_format.value

        # Canonical ordering
        a_id, b_id, sets_a, sets_b, sets_a_act, sets_b_act = _canonical_order(
            body.player_a_id, body.player_b_id,
            body.sets_won_a, body.sets_won_b,
            body.sets_won_a_actual, body.sets_won_b_actual,
        )

        # Determine winner
        winner_id = a_id if sets_a > sets_b else b_id

        # Validate fixture slot if provided and capture semantics
        # INTRA_ACADEMY uses fixture_slot (session-scoped); INTER_ACADEMY uses event_fixture_slot
        slot_match_category = None
        slot_gap_band = None
        slot_round_intent = None
        slot_player_a_role = None
        slot_player_b_role = None
        is_event_slot = event["scheduling_mode"] == "INTER_ACADEMY"
        if body.fixture_slot_id:
            slot_table = "event_fixture_slot" if is_event_slot else "fixture_slot"
            cur.execute(
                f"SELECT slot_id::text, player_a_id::text, player_b_id::text, status, "
                f"       match_category, gap_band, round_intent, player_a_role, player_b_role "
                f"FROM {slot_table} WHERE slot_id = %s",
                (body.fixture_slot_id,),
            )
            slot = cur.fetchone()
            if not slot:
                raise ValueError("Fixture slot not found")
            if slot["status"] != "SCHEDULED":
                raise ValueError(f"Fixture slot is already '{slot['status']}'")
            if slot["player_a_id"] != a_id or slot["player_b_id"] != b_id:
                raise ValueError("Fixture slot players do not match the submitted players")
            slot_match_category = slot["match_category"]
            slot_gap_band = slot["gap_band"]
            slot_round_intent = slot["round_intent"]
            slot_player_a_role = slot["player_a_role"]
            slot_player_b_role = slot["player_b_role"]

        # Eligibility (using raw ratings and fixture semantics when available)
        rating_a = float(player_a["current_rating"])
        rating_b = float(player_b["current_rating"])
        rating_eligible, not_eligible_reason = _check_eligibility(
            rating_a,
            rating_b,
            sets_a,
            sets_b,
            body.is_retirement,
            match_format,
            slot_gap_band,
        )

        # Diminishing signal check
        diminishing = _check_diminishing_signal(cur, a_id, b_id, body.match_date)

        # Confirmation deadline = end of match_date in IST stored as UTC
        deadline_utc = end_of_day_ist(body.match_date)

        # Academy ID snapshots at submission time (canonical order)
        a_academy = (
            player_a["primary_academy_id"]
            if body.player_a_id == a_id
            else player_b["primary_academy_id"]
        )
        b_academy = (
            player_b["primary_academy_id"]
            if body.player_b_id == b_id
            else player_a["primary_academy_id"]
        )

        match_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)
        auto_confirm_roles = ("ADMIN", "COACH", "UMPIRE", "REFEREE")
        confirmation_status = (
            "AUTO_CONFIRMED" if caller_role in auto_confirm_roles else "PENDING"
        )
        confirmed_by = submitted_by_user_id if confirmation_status == "AUTO_CONFIRMED" else None
        confirmed_at = now_utc if confirmation_status == "AUTO_CONFIRMED" else None

        cur.execute(
            """
            INSERT INTO match (
                match_id, event_id, session_id, fixture_slot_id,
                player_a_id, player_b_id,
                player_a_academy_id, player_b_academy_id,
                match_format,
                sets_won_a, sets_won_b,
                sets_won_a_actual, sets_won_b_actual,
                is_retirement, winner_id,
                rating_eligible, not_eligible_reason,
                diminishing_signal_applied,
                match_date, match_timestamp,
                submitted_by, confirmation_status, confirmed_by, confirmed_at,
                confirmation_deadline,
                match_category, gap_band, round_intent, player_a_role, player_b_role
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s, %s, %s
            )
            """,
            (
                match_id, body.event_id, body.session_id, body.fixture_slot_id,
                a_id, b_id,
                a_academy, b_academy,
                match_format,
                sets_a, sets_b,
                sets_a_act, sets_b_act,
                body.is_retirement, winner_id,
                rating_eligible, not_eligible_reason,
                diminishing,
                body.match_date, now_utc,
                submitted_by_user_id, confirmation_status, confirmed_by, confirmed_at,
                deadline_utc,
                slot_match_category, slot_gap_band, slot_round_intent,
                slot_player_a_role, slot_player_b_role,
            ),
        )

        # If per-set point scores were provided, persist them
        if getattr(body, "set_scores", None):
            store_set_scores(conn, match_id, body.set_scores)

        if body.fixture_slot_id:
            if is_event_slot:
                cur.execute(
                    "UPDATE event_fixture_slot SET status = 'PLAYED', match_id = %s WHERE slot_id = %s",
                    (match_id, body.fixture_slot_id),
                )
            else:
                cur.execute(
                    "UPDATE fixture_slot SET status = 'PLAYED', match_id = %s WHERE slot_id = %s",
                    (match_id, body.fixture_slot_id),
                )
            if body.session_id:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status != 'BYE') AS total,
                        COUNT(*) FILTER (WHERE status = 'PLAYED') AS played
                    FROM fixture_slot WHERE session_id = %s
                    """,
                    (body.session_id,),
                )
                counts = cur.fetchone()
                if counts["played"] >= counts["total"]:
                    cur.execute(
                        "UPDATE session SET status = 'COMPLETED', updated_at = NOW() "
                        "WHERE session_id = %s AND status != 'COMPLETED'",
                        (body.session_id,),
                    )
                else:
                    cur.execute(
                        "UPDATE session SET status = 'IN_PROGRESS', updated_at = NOW() "
                        "WHERE session_id = %s AND status = 'SCHEDULED'",
                        (body.session_id,),
                    )

        # Update last_match_date at submission time so roster reflects activity immediately
        cur.execute(
            """
            UPDATE player SET last_match_date = %s
            WHERE player_id IN (%s, %s)
              AND (last_match_date IS NULL OR last_match_date < %s)
            """,
            (body.match_date, a_id, b_id, body.match_date),
        )

        return _fetch_match(cur, match_id, event["scheduling_mode"])


def update_match(conn, match_id: str, body, acting_user_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT match_id, event_id, session_id, fixture_slot_id, player_a_id, player_b_id, "
            "match_format, is_retirement, confirmation_status, ratings_applied_at, "
            "sets_won_a, sets_won_b, sets_won_a_actual, sets_won_b_actual "
            "FROM match WHERE match_id = %s",
            (match_id,),
        )
        match = cur.fetchone()
        if not match:
            raise ValueError("Match not found")
        if match["confirmation_status"] == "VOIDED":
            raise ValueError("Cannot edit a voided match")
        if match["ratings_applied_at"] is not None:
            raise ValueError("Cannot edit a match after ratings have been applied")

        is_retirement = body.is_retirement if body.is_retirement is not None else match["is_retirement"]
        sets_won_a = body.sets_won_a if body.sets_won_a is not None else match["sets_won_a"]
        sets_won_b = body.sets_won_b if body.sets_won_b is not None else match["sets_won_b"]
        sets_won_a_actual = body.sets_won_a_actual if body.sets_won_a_actual is not None else match["sets_won_a_actual"]
        sets_won_b_actual = body.sets_won_b_actual if body.sets_won_b_actual is not None else match["sets_won_b_actual"]

        if sets_won_a < 0 or sets_won_b < 0:
            raise ValueError("Match scores cannot be negative")

        if not is_retirement:
            required = _REQUIRED_WINNER_SETS.get(match["match_format"], 0)
            winner_sets = max(sets_won_a, sets_won_b)
            loser_sets = min(sets_won_a, sets_won_b)
            if winner_sets != required:
                raise ValueError(
                    f"{match['match_format']} match winner must have exactly {required} sets; got {sets_won_a}-{sets_won_b}"
                )
            if loser_sets >= required:
                raise ValueError(
                    f"Loser cannot have {loser_sets} sets in a {match['match_format']} match"
                )
        else:
            if max(sets_won_a, sets_won_b) < 1:
                raise ValueError("Retirement matches must include at least one set score")

        cur.execute(
            "SELECT player_id, current_rating FROM player WHERE player_id = %s",
            (match["player_a_id"],),
        )
        player_a = cur.fetchone()
        cur.execute(
            "SELECT player_id, current_rating FROM player WHERE player_id = %s",
            (match["player_b_id"],),
        )
        player_b = cur.fetchone()

        if not player_a or not player_b:
            raise ValueError("Players for this match are not available")

        gap_band = None
        if match["fixture_slot_id"]:
            cur.execute(
                "SELECT gap_band FROM fixture_slot WHERE slot_id = %s",
                (match["fixture_slot_id"],),
            )
            slot = cur.fetchone()
            gap_band = slot["gap_band"] if slot else None

        rating_eligible, not_eligible_reason = _check_eligibility(
            float(player_a["current_rating"]),
            float(player_b["current_rating"]),
            sets_won_a,
            sets_won_b,
            is_retirement,
            match["match_format"],
            gap_band,
        )

        winner_id = match["player_a_id"] if sets_won_a > sets_won_b else match["player_b_id"]
        update_fields = [
            ("sets_won_a", sets_won_a),
            ("sets_won_b", sets_won_b),
            ("sets_won_a_actual", sets_won_a_actual),
            ("sets_won_b_actual", sets_won_b_actual),
            ("is_retirement", is_retirement),
            ("winner_id", winner_id),
            ("rating_eligible", rating_eligible),
            ("not_eligible_reason", not_eligible_reason),
            ("updated_at", datetime.now(timezone.utc)),
        ]
        if body.match_date is not None:
            update_fields.append(("match_date", body.match_date))
            update_fields.append(("confirmation_deadline", end_of_day_ist(body.match_date)))

        assignments = ", ".join(f"{field} = %s" for field, _ in update_fields)
        values = [value for _, value in update_fields] + [match_id]
        cur.execute(
            f"UPDATE match SET {assignments} WHERE match_id = %s",
            tuple(values),
        )

        if getattr(body, "set_scores", None) is not None:
            store_set_scores(conn, match_id, body.set_scores)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT scheduling_mode FROM event WHERE event_id = %s",
            (match["event_id"],),
        )
        event = cur.fetchone()
        return _fetch_match(cur, match_id, event["scheduling_mode"])


def delete_match(conn, match_id: str, acting_user_id: str, reason: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT match_id, confirmation_status, ratings_applied_at, session_id, fixture_slot_id, event_id "
            "FROM match WHERE match_id = %s",
            (match_id,),
        )
        match = cur.fetchone()
        if not match:
            raise ValueError("Match not found")
        if match["confirmation_status"] == "VOIDED":
            raise ValueError("Cannot delete a voided match")
        if match["ratings_applied_at"] is not None:
            raise ValueError("Cannot delete a match after ratings have been applied")

        if match["fixture_slot_id"]:
            cur.execute(
                "UPDATE fixture_slot SET status = 'SCHEDULED', match_id = NULL WHERE slot_id = %s",
                (match["fixture_slot_id"],),
            )

        cur.execute("DELETE FROM match WHERE match_id = %s", (match_id,))

        if match["session_id"]:
            cur.execute(
                "SELECT status FROM session WHERE session_id = %s",
                (match["session_id"],),
            )
            session = cur.fetchone()
            if session and session["status"] == "COMPLETED":
                cur.execute(
                    "SELECT COUNT(*) AS played FROM fixture_slot WHERE session_id = %s AND status = 'PLAYED'",
                    (match["session_id"],),
                )
                played = cur.fetchone()["played"]
                new_status = "SCHEDULED" if played == 0 else "IN_PROGRESS"
                cur.execute(
                    "UPDATE session SET status = %s, updated_at = NOW() WHERE session_id = %s",
                    (new_status, match["session_id"]),
                )


def confirm_match(conn, match_id: str, confirmed: bool, dispute_reason: str | None,
                  acting_user_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT match_id, confirmation_status, player_b_id, event_id "
            "FROM match WHERE match_id = %s",
            (match_id,),
        )
        match = cur.fetchone()
        if not match:
            raise ValueError("Match not found")
        if match["confirmation_status"] != "PENDING":
            raise ValueError(
                f"Match is already '{match['confirmation_status']}'; cannot confirm/dispute"
            )

        cur.execute(
            "SELECT scheduling_mode FROM event WHERE event_id = %s",
            (match["event_id"],),
        )
        event = cur.fetchone()

        if confirmed:
            cur.execute(
                """
                UPDATE match
                SET confirmation_status = 'CONFIRMED',
                    confirmed_by = %s,
                    confirmed_at = NOW()
                WHERE match_id = %s
                """,
                (acting_user_id, match_id),
            )
            from app.services.webhook_service import fire
            fire("match.confirmed", {"match_id": match_id})
        else:
            # Create dispute row
            dispute_id = str(uuid.uuid4())
            # Resolution deadline: 72 hours from now
            cur.execute(
                """
                INSERT INTO dispute (dispute_id, match_id, raised_by, reason, resolution_deadline)
                VALUES (%s, %s, %s, %s, NOW() + INTERVAL '72 hours')
                """,
                (dispute_id, match_id, acting_user_id, dispute_reason),
            )
            cur.execute(
                "UPDATE match SET confirmation_status = 'DISPUTED' WHERE match_id = %s",
                (match_id,),
            )
            from app.services.webhook_service import fire
            fire("match.disputed", {"match_id": match_id, "dispute_id": dispute_id})

        return _fetch_match(cur, match_id, event["scheduling_mode"])


def void_match(conn, match_id: str, void_reason: str, acting_user_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT match_id, confirmation_status, ratings_applied_at, event_id, fixture_slot_id "
            "FROM match WHERE match_id = %s",
            (match_id,),
        )
        match = cur.fetchone()
        if not match:
            raise ValueError("Match not found")
        if match["confirmation_status"] == "VOIDED":
            raise ValueError("Match is already voided")

        if match["ratings_applied_at"] is not None:
            # Phase 3 will fill in rollback; stub for now
            pass

        cur.execute(
            """
            UPDATE match
            SET confirmation_status = 'VOIDED',
                voided_at = NOW(),
                voided_by = %s,
                void_reason = %s
            WHERE match_id = %s
            """,
            (acting_user_id, void_reason, match_id),
        )

        if match["fixture_slot_id"]:
            cur.execute(
                "UPDATE fixture_slot SET status = 'SCHEDULED', match_id = NULL WHERE slot_id = %s",
                (match["fixture_slot_id"],),
            )

        cur.execute(
            "SELECT scheduling_mode FROM event WHERE event_id = %s",
            (match["event_id"],),
        )
        event = cur.fetchone()

        from app.services.webhook_service import fire
        fire("match.voided", {"match_id": match_id})

        return _fetch_match(cur, match_id, event["scheduling_mode"])


def store_set_scores(conn, match_id: str, set_scores: list) -> None:
    """
    Insert or update per-set point scores into match_set_score table.
    Expects `set_scores` as an iterable of objects/dicts with `points_a` and `points_b`.
    """
    with conn.cursor() as cur:
        for set_num, score in enumerate(set_scores, start=1):
            # score may be a pydantic model or dict-like
            points_a = getattr(score, "points_a", None) if not isinstance(score, dict) else score.get("points_a")
            points_b = getattr(score, "points_b", None) if not isinstance(score, dict) else score.get("points_b")
            cur.execute(
                """
                INSERT INTO match_set_score (match_id, set_number, points_a, points_b)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (match_id, set_number)
                DO UPDATE SET points_a = EXCLUDED.points_a, points_b = EXCLUDED.points_b
                """,
                (match_id, set_num, points_a, points_b),
            )


def get_set_scores(cur, match_id: str) -> list | None:
    """
    Retrieve per-set point scores for a match using an open cursor.
    Returns list of dicts or None if no scores.
    """
    cur.execute(
        """
        SELECT set_number, points_a, points_b
        FROM match_set_score
        WHERE match_id = %s
        ORDER BY set_number ASC
        """,
        (match_id,),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows] if rows else None


def _fetch_match(cur, match_id: str, scheduling_mode: str) -> dict:
    cur.execute(
        """
        SELECT
            m.match_id, m.event_id, m.session_id, m.fixture_slot_id,
            json_build_object(
                'player_id', pa.player_id, 'name', pa.name, 'current_rating', pa.current_rating
            ) AS player_a,
            json_build_object(
                'player_id', pb.player_id, 'name', pb.name, 'current_rating', pb.current_rating
            ) AS player_b,
            m.match_format, m.sets_won_a, m.sets_won_b,
            m.sets_won_a_actual, m.sets_won_b_actual,
            m.is_retirement, m.winner_id,
            m.rating_eligible, m.not_eligible_reason,
            m.diminishing_signal_applied,
            m.confirmation_status, m.confirmation_deadline,
            m.ratings_applied_at, m.match_date, m.match_timestamp, m.created_at,
            m.match_category, m.gap_band, m.round_intent, m.player_a_role, m.player_b_role
        FROM match m
        JOIN player pa ON pa.player_id = m.player_a_id
        JOIN player pb ON pb.player_id = m.player_b_id
        WHERE m.match_id = %s
        """,
        (match_id,),
    )
    row = dict(cur.fetchone())
    row["ratings_trigger"] = _RATINGS_TRIGGER.get(scheduling_mode, "EVENT_COMPLETION")
    # Attach per-set scores if present
    try:
        row["set_scores"] = get_set_scores(cur, match_id)
    except Exception:
        row["set_scores"] = None
    return row
