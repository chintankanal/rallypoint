"""
Daily job — called by POST /internal/jobs/daily at 23:58 IST.

Steps:
1. Auto-confirm all PENDING matches whose confirmation_deadline has passed.
2. Expire disputes whose resolution_deadline has passed.
3. Apply EOD ratings for all eligible INTRA_ACADEMY confirmed matches.
4. Recalculate ASI for every ACTIVE and FROZEN academy.
5. Update global_average_rating in system_configuration.
"""
import uuid

from app.database import get_connection


def run() -> dict:
    auto_confirmed = 0
    disputes_expired = 0
    matches_rated = 0
    academies_recalculated = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Auto-confirm
            cur.execute(
                """
                UPDATE match
                SET confirmation_status = 'AUTO_CONFIRMED', confirmed_at = NOW(), updated_at = NOW()
                WHERE confirmation_status = 'PENDING'
                  AND confirmation_deadline < NOW()
                """
            )
            auto_confirmed = cur.rowcount

            # 2. Expire disputes
            cur.execute(
                """
                UPDATE dispute
                SET status = 'EXPIRED', resolved_at = NOW()
                WHERE status IN ('OPEN', 'UNDER_REVIEW')
                  AND resolution_deadline < NOW()
                """
            )
            disputes_expired = cur.rowcount

            # 3. Collect eligible INTRA_ACADEMY matches to rate
            cur.execute(
                """
                SELECT m.match_id FROM match m
                JOIN event e ON e.event_id = m.event_id
                WHERE e.scheduling_mode = 'INTRA_ACADEMY'
                  AND m.rating_eligible = TRUE
                  AND m.ratings_applied_at IS NULL
                  AND m.confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')
                """
            )
            match_ids = [r["match_id"] for r in cur.fetchall()]

        if match_ids:
            from app.services.rating_engine import apply_ratings_batch
            from app.services.webhook_service import fire
            tier_changes = apply_ratings_batch(conn, match_ids)
            matches_rated = len(match_ids)
            for tc in tier_changes:
                fire("player.tier_changed", tc)

        # 4 & 5. Full ASI recalculation for all academies
        with conn.cursor() as cur:
            cur.execute(
                "SELECT AVG(current_rating) AS avg FROM player WHERE status = 'ACTIVE'"
            )
            row = cur.fetchone()
            global_avg = float(row["avg"]) if row["avg"] else 1000.0

            cur.execute(
                "UPDATE system_configuration SET value = %s, updated_at = NOW() "
                "WHERE key = 'global_average_rating'",
                (str(global_avg),),
            )

            cur.execute("SELECT academy_id, status FROM academy WHERE status IN ('ACTIVE', 'FROZEN')")
            academies = cur.fetchall()

            for academy in academies:
                academy_id = academy["academy_id"]
                academy_status = academy["status"]

                if academy_status == "FROZEN":
                    # Copy the last ASI value (or None if never computed)
                    cur.execute(
                        """
                        SELECT asi_value FROM academy_asi_history
                        WHERE academy_id = %s
                        ORDER BY calculated_at DESC LIMIT 1
                        """,
                        (academy_id,),
                    )
                    last = cur.fetchone()
                    asi_value = float(last["asi_value"]) if last and last["asi_value"] else None
                    basis = "FROZEN"
                    count = 0
                else:
                    cur.execute(
                        """
                        SELECT AVG(current_rating) AS avg_rating, COUNT(*) AS cnt
                        FROM player
                        WHERE primary_academy_id = %s
                          AND status = 'ACTIVE'
                          AND rated_matches_completed >= 15
                          AND last_match_date >= NOW() - INTERVAL '56 days'
                        """,
                        (academy_id,),
                    )
                    r = cur.fetchone()
                    count = int(r["cnt"]) if r["cnt"] else 0
                    if count >= 5:
                        asi_value = float(r["avg_rating"])
                        basis = "COMPUTED"
                    else:
                        asi_value = None
                        basis = "DEFAULTED"

                cur.execute(
                    """
                    INSERT INTO academy_asi_history
                        (history_id, academy_id, asi_value, qualifying_player_count,
                         calculation_basis, global_average_at_calculation)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), academy_id, asi_value, count, basis, global_avg),
                )
                academies_recalculated += 1

    return {
        "auto_confirmed": auto_confirmed,
        "disputes_expired": disputes_expired,
        "matches_rated": matches_rated,
        "academies_recalculated": academies_recalculated,
        "global_average_rating": global_avg,
    }
