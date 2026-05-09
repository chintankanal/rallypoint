"""
Weekly job — called by POST /internal/jobs/weekly at 00:00 IST Sunday.

Finds academies where ALL active players have been inactive for ≥8 weeks,
then freezes those academies and records an AcademyStatusHistory entry.
"""
import uuid

from app.database import get_connection


def run() -> dict:
    frozen_count = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Find ACTIVE academies where every active player has been inactive ≥ 56 days.
            # An academy qualifies if it has at least one active player and none of them
            # have a last_match_date within the past 56 days.
            cur.execute(
                """
                SELECT a.academy_id FROM academy a
                WHERE a.status = 'ACTIVE'
                  AND EXISTS (
                      SELECT 1 FROM player p
                      WHERE p.primary_academy_id = a.academy_id AND p.status = 'ACTIVE'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM player p
                      WHERE p.primary_academy_id = a.academy_id
                        AND p.status = 'ACTIVE'
                        AND (p.last_match_date IS NULL OR p.last_match_date >= NOW() - INTERVAL '56 days')
                  )
                """
            )
            to_freeze = [r["academy_id"] for r in cur.fetchall()]

            for academy_id in to_freeze:
                cur.execute(
                    "UPDATE academy SET status = 'FROZEN', frozen_since = CURRENT_DATE, "
                    "updated_at = NOW() WHERE academy_id = %s",
                    (academy_id,),
                )
                cur.execute(
                    """
                    INSERT INTO academy_status_history
                        (history_id, academy_id, from_status, to_status, triggered_by, changed_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (str(uuid.uuid4()), academy_id, "ACTIVE", "FROZEN", "SYSTEM"),
                )
                frozen_count += 1

    return {"academies_frozen": frozen_count}
