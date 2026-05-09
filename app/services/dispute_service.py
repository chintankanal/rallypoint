from app.database import get_connection
from app.services.rating_engine import apply_ratings_batch, rollback_match
from app.services.webhook_service import fire


def _fetch_dispute(cur, dispute_id: str) -> dict | None:
    cur.execute(
        """
        SELECT dispute_id, match_id, raised_by, reason, status, resolution,
               corrected_sets_won_a, corrected_sets_won_b,
               resolved_by, resolution_notes, resolution_deadline,
               created_at, resolved_at
        FROM dispute WHERE dispute_id = %s
        """,
        (dispute_id,),
    )
    return cur.fetchone()


def list_disputes(
    dispute_status: str | None, event_id: str | None, limit: int, offset: int
) -> dict:
    conditions = []
    params: list = []

    if dispute_status:
        conditions.append("d.status = %s")
        params.append(dispute_status)
    if event_id:
        conditions.append("m.event_id = %s")
        params.append(event_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM dispute d
                JOIN match m ON m.match_id = d.match_id
                {where}
                """,
                params,
            )
            total = cur.fetchone()["cnt"]

            cur.execute(
                f"""
                SELECT d.dispute_id, d.match_id, d.raised_by, d.reason, d.status,
                       d.resolution, d.corrected_sets_won_a, d.corrected_sets_won_b,
                       d.resolved_by, d.resolution_notes, d.resolution_deadline,
                       d.created_at, d.resolved_at
                FROM dispute d
                JOIN match m ON m.match_id = d.match_id
                {where}
                ORDER BY d.created_at DESC
                LIMIT %s OFFSET %s
                """,
                [*params, limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

    return {"total": total, "limit": limit, "offset": offset, "items": rows}


def get_dispute(dispute_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            row = _fetch_dispute(cur, dispute_id)
    return dict(row) if row else None


def set_under_review(dispute_id: str) -> dict | None:
    """
    Transitions a dispute from OPEN → UNDER_REVIEW.
    Returns the updated dispute dict, or None if not found.
    Raises ValueError if the dispute is not in OPEN status.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dispute_id, status FROM dispute WHERE dispute_id = %s",
                (dispute_id,),
            )
            dispute = cur.fetchone()
            if not dispute:
                return None
            if dispute["status"] != "OPEN":
                raise ValueError(
                    f"Cannot move dispute from '{dispute['status']}' to UNDER_REVIEW"
                )
            cur.execute(
                "UPDATE dispute SET status = 'UNDER_REVIEW', reviewed_at = NOW() "
                "WHERE dispute_id = %s",
                (dispute_id,),
            )
            row = _fetch_dispute(cur, dispute_id)
    return dict(row)


def resolve_dispute(dispute_id: str, body, resolved_by_user_id: str) -> dict | None:
    """
    Resolves a dispute with one of: CONFIRMED_ORIGINAL, CORRECTED, VOIDED.
    Returns the updated dispute dict, or None if not found.
    Raises ValueError if the dispute is already resolved/expired.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.dispute_id, d.match_id, d.status,
                       m.ratings_applied_at, m.rating_eligible
                FROM dispute d
                JOIN match m ON m.match_id = d.match_id
                WHERE d.dispute_id = %s
                """,
                (dispute_id,),
            )
            dispute = cur.fetchone()
            if not dispute:
                return None
            if dispute["status"] not in ("OPEN", "UNDER_REVIEW"):
                raise ValueError(f"Dispute is already '{dispute['status']}'")

            match_id = dispute["match_id"]
            was_rated = dispute["ratings_applied_at"] is not None

            if body.resolution == "CONFIRMED_ORIGINAL":
                cur.execute(
                    "UPDATE match SET confirmation_status = 'CONFIRMED' WHERE match_id = %s",
                    (match_id,),
                )

            elif body.resolution == "CORRECTED":
                if was_rated:
                    rollback_match(conn, match_id)

                cur.execute(
                    """
                    UPDATE match
                    SET sets_won_a = %s, sets_won_b = %s,
                        winner_id = CASE
                            WHEN %s > %s THEN player_a_id
                            ELSE player_b_id
                        END,
                        confirmation_status = 'CONFIRMED'
                    WHERE match_id = %s
                    """,
                    (
                        body.corrected_sets_won_a,
                        body.corrected_sets_won_b,
                        body.corrected_sets_won_a,
                        body.corrected_sets_won_b,
                        match_id,
                    ),
                )

                if dispute["rating_eligible"]:
                    tier_changes = apply_ratings_batch(conn, [match_id])
                    for tc in tier_changes:
                        fire("player.tier_changed", tc)

            elif body.resolution == "VOIDED":
                if was_rated:
                    rollback_match(conn, match_id)

                cur.execute(
                    """
                    UPDATE match
                    SET confirmation_status = 'VOIDED',
                        voided_at = NOW(),
                        voided_by = %s,
                        void_reason = 'Dispute resolved as VOIDED'
                    WHERE match_id = %s
                    """,
                    (resolved_by_user_id, match_id),
                )

            cur.execute(
                """
                UPDATE dispute
                SET status = 'RESOLVED',
                    resolution = %s,
                    corrected_sets_won_a = %s,
                    corrected_sets_won_b = %s,
                    resolved_by = %s,
                    resolution_notes = %s,
                    resolved_at = NOW()
                WHERE dispute_id = %s
                """,
                (
                    body.resolution,
                    body.corrected_sets_won_a,
                    body.corrected_sets_won_b,
                    resolved_by_user_id,
                    body.resolution_notes,
                    dispute_id,
                ),
            )
            row = _fetch_dispute(cur, dispute_id)

    fire("dispute.resolved", {"dispute_id": dispute_id, "resolution": body.resolution})
    return dict(row)
