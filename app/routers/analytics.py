from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_connection
from app.dependencies.auth import get_current_user
from schemas.leaderboard import (
    AcademyReport,
    ASIPoint,
    TierCount,
    TopMover,
    VelocityReport,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_ANY = Depends(get_current_user)

_PERIOD_DAYS = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}


@router.get("/players/{player_id}/velocity", response_model=VelocityReport)
def player_velocity(
    player_id: str,
    period: str = Query("3m", description="1m | 3m | 6m | 1y"),
    _: dict = _ANY,
):
    days = _PERIOD_DAYS.get(period)
    if days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period must be one of: 1m, 3m, 6m, 1y",
        )

    since: date = date.today() - timedelta(days=days)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM player WHERE player_id = %s", (player_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

            cur.execute(
                """
                SELECT
                    COUNT(*) AS matches_played,
                    COUNT(*) FILTER (WHERE m.winner_id::text = rh.player_id::text) AS wins,
                    COUNT(*) FILTER (WHERE rh.tier_before != rh.tier_after) AS tier_changes,
                    COUNT(*) FILTER (WHERE m.gap_band = 'STRETCH') AS stretch_matches,
                    COUNT(*) FILTER (WHERE m.gap_band = 'STRETCH'
                                      AND m.winner_id::text = rh.player_id::text) AS stretch_wins,
                    COUNT(*) FILTER (
                        WHERE (m.player_a_id = %s AND m.player_a_role = 'PEER')
                           OR (m.player_b_id = %s AND m.player_b_role = 'PEER')
                    ) AS peer_matches,
                    COUNT(*) FILTER (
                        WHERE ((m.player_a_id = %s AND m.player_a_role = 'PEER')
                               OR (m.player_b_id = %s AND m.player_b_role = 'PEER'))
                          AND m.winner_id::text = rh.player_id::text
                    ) AS peer_wins,
                    COUNT(*) FILTER (
                        WHERE (m.player_a_id = %s AND m.player_a_role = 'ANCHORING')
                           OR (m.player_b_id = %s AND m.player_b_role = 'ANCHORING')
                    ) AS anchoring_matches,
                    COUNT(*) FILTER (
                        WHERE ((m.player_a_id = %s AND m.player_a_role = 'ANCHORING')
                               OR (m.player_b_id = %s AND m.player_b_role = 'ANCHORING'))
                          AND m.winner_id::text = rh.player_id::text
                    ) AS anchoring_wins,
                    COUNT(*) FILTER (
                        WHERE (m.player_a_id = %s AND m.player_a_role = 'STRETCHING')
                           OR (m.player_b_id = %s AND m.player_b_role = 'STRETCHING')
                    ) AS stretching_matches,
                    COUNT(*) FILTER (
                        WHERE ((m.player_a_id = %s AND m.player_a_role = 'STRETCHING')
                               OR (m.player_b_id = %s AND m.player_b_role = 'STRETCHING'))
                          AND m.winner_id::text = rh.player_id::text
                    ) AS stretching_wins,
                    COUNT(*) FILTER (
                        WHERE m.gap_band = 'COMPETITIVE') AS competitive_matches,
                    COUNT(*) FILTER (
                        WHERE m.gap_band = 'COMPETITIVE'
                          AND m.winner_id::text = rh.player_id::text) AS competitive_wins,
                    COUNT(*) FILTER (
                        WHERE m.gap_band = 'OUT_OF_BAND') AS out_of_band_matches,
                    COUNT(*) FILTER (
                        WHERE m.gap_band = 'OUT_OF_BAND'
                          AND m.winner_id::text = rh.player_id::text) AS out_of_band_wins,
                    (SELECT rh2.rating_before
                     FROM rating_history rh2
                     JOIN match m2 ON m2.match_id = rh2.match_id
                     WHERE rh2.player_id = %s AND rh2.is_rollback = FALSE
                       AND m2.match_date >= %s
                     ORDER BY m2.match_date ASC, m2.match_timestamp ASC LIMIT 1) AS start_rating,
                    (SELECT rh3.rating_after
                     FROM rating_history rh3
                     JOIN match m3 ON m3.match_id = rh3.match_id
                     WHERE rh3.player_id = %s AND rh3.is_rollback = FALSE
                       AND m3.match_date >= %s
                     ORDER BY m3.match_date DESC, m3.match_timestamp DESC LIMIT 1) AS end_rating
                FROM rating_history rh
                JOIN match m ON m.match_id = rh.match_id
                WHERE rh.player_id = %s AND rh.is_rollback = FALSE
                  AND m.match_date >= %s
                """,
                [
                    player_id, player_id,
                    player_id, player_id,
                    player_id, player_id,
                    player_id, player_id,
                    player_id, player_id,
                    player_id, player_id,
                    player_id, since,
                    player_id, since,
                    player_id, since,
                ],
            )
            row = dict(cur.fetchone())

    mp = int(row["matches_played"])
    wins = int(row["wins"])
    tier_changes = int(row["tier_changes"])
    stretch_matches = int(row["stretch_matches"])
    stretch_wins = int(row["stretch_wins"])
    start_r = float(row["start_rating"]) if row["start_rating"] is not None else None
    end_r = float(row["end_rating"]) if row["end_rating"] is not None else None

    rating_change = (end_r - start_r) if (start_r is not None and end_r is not None) else 0.0
    win_rate = (wins / mp) if mp > 0 else 0.0
    stretch_win_rate = (stretch_wins / stretch_matches) if stretch_matches > 0 else None

    return VelocityReport(
        player_id=player_id,
        period=period,
        start_rating=start_r,
        end_rating=end_r,
        rating_change=round(rating_change, 2),
        matches_played=mp,
        wins=wins,
        win_rate=round(win_rate, 4),
        stretch_matches=stretch_matches,
        stretch_wins=stretch_wins,
        stretch_win_rate=round(stretch_win_rate, 4) if stretch_win_rate is not None else None,
        tier_changes=tier_changes,
        gap_band_breakdown={
            "competitive": {
                "wins": int(row["competitive_wins"]),
                "total": int(row["competitive_matches"]),
            },
            "stretch": {
                "wins": int(row["stretch_wins"]),
                "total": int(row["stretch_matches"]),
            },
            "out_of_band": {
                "wins": int(row["out_of_band_wins"]),
                "total": int(row["out_of_band_matches"]),
            },
        },
        role_breakdown={
            "peer": {
                "wins": int(row["peer_wins"]),
                "total": int(row["peer_matches"]),
            },
            "anchoring": {
                "wins": int(row["anchoring_wins"]),
                "total": int(row["anchoring_matches"]),
            },
            "stretching": {
                "wins": int(row["stretching_wins"]),
                "total": int(row["stretching_matches"]),
            },
        },
    )


@router.get("/academies/{academy_id}/report", response_model=AcademyReport)
def academy_report(
    academy_id: str,
    season_id: str | None = Query(None),
    period: str = Query("3m", description="1m | 3m | 6m | 1y"),
    _: dict = _ANY,
):
    days = _PERIOD_DAYS.get(period)
    if days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period must be one of: 1m, 3m, 6m, 1y",
        )

    since: date = date.today() - timedelta(days=days)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT academy_id FROM academy WHERE academy_id = %s", (academy_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Academy not found"
                )

            season_filter = ""
            season_params: list = []
            if season_id:
                season_filter = "AND e.season_id = %s"
                season_params = [season_id]

            # Total rated matches and cross-academy stats
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_rated,
                    COUNT(*) FILTER (
                        WHERE m.player_a_academy_id != m.player_b_academy_id
                    ) AS cross_count
                FROM match m
                JOIN event e ON e.event_id = m.event_id
                WHERE (m.player_a_academy_id = %s OR m.player_b_academy_id = %s)
                  AND m.ratings_applied_at IS NOT NULL
                  AND m.match_date >= %s
                  {season_filter}
                """,
                [academy_id, academy_id, since] + season_params,
            )
            match_row = dict(cur.fetchone())

            # Confirmation rate
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_submitted,
                    COUNT(*) FILTER (
                        WHERE m.confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')
                    ) AS confirmed_count
                FROM match m
                JOIN event e ON e.event_id = m.event_id
                WHERE (m.player_a_academy_id = %s OR m.player_b_academy_id = %s)
                  AND m.match_date >= %s
                  AND m.confirmation_status != 'VOIDED'
                  {season_filter}
                """,
                [academy_id, academy_id, since] + season_params,
            )
            conf_row = dict(cur.fetchone())

            # Tier distribution of active players
            cur.execute(
                """
                SELECT
                    CASE
                        WHEN current_rating < 900  THEN 'BEGINNER'
                        WHEN current_rating < 1100 THEN 'INTERMEDIATE'
                        WHEN current_rating < 1300 THEN 'ADVANCED'
                        WHEN current_rating < 1500 THEN 'ELITE'
                        ELSE 'NATIONAL_TRACK'
                    END AS tier,
                    COUNT(*) AS cnt
                FROM player
                WHERE primary_academy_id = %s AND status = 'ACTIVE'
                GROUP BY tier
                ORDER BY MIN(current_rating)
                """,
                (academy_id,),
            )
            tier_dist = [TierCount(tier=r["tier"], count=r["cnt"]) for r in cur.fetchall()]

            # Top movers (by absolute total delta) in period
            cur.execute(
                """
                SELECT rh.player_id::text, p.name,
                    SUM(rh.delta)::float AS total_delta,
                    COUNT(*) AS matches
                FROM rating_history rh
                JOIN player p ON p.player_id = rh.player_id
                WHERE p.primary_academy_id = %s
                  AND rh.is_rollback = FALSE
                  AND rh.created_at::date >= %s
                GROUP BY rh.player_id, p.name
                ORDER BY ABS(SUM(rh.delta)) DESC
                LIMIT 5
                """,
                (academy_id, since),
            )
            top_movers = [
                TopMover(
                    player_id=r["player_id"],
                    name=r["name"],
                    total_delta=round(float(r["total_delta"]), 2),
                    matches=r["matches"],
                )
                for r in cur.fetchall()
            ]

            # ASI trend (last 6 entries)
            cur.execute(
                """
                SELECT asi_value, calculation_basis, calculated_at
                FROM academy_asi_history
                WHERE academy_id = %s
                ORDER BY calculated_at DESC
                LIMIT 6
                """,
                (academy_id,),
            )
            asi_trend = [
                ASIPoint(
                    asi_value=float(r["asi_value"]) if r["asi_value"] is not None else None,
                    calculation_basis=r["calculation_basis"],
                    calculated_at=r["calculated_at"],
                )
                for r in cur.fetchall()
            ]

    total_rated = int(match_row["total_rated"])
    cross_count = int(match_row["cross_count"])
    total_submitted = int(conf_row["total_submitted"])
    confirmed_count = int(conf_row["confirmed_count"])

    cross_pct = (cross_count / total_rated * 100) if total_rated > 0 else 0.0
    conf_rate = (confirmed_count / total_submitted) if total_submitted > 0 else 0.0

    return AcademyReport(
        academy_id=academy_id,
        period_days=days,
        total_rated_matches=total_rated,
        cross_academy_count=cross_count,
        cross_academy_pct=round(cross_pct, 2),
        confirmed_count=confirmed_count,
        total_submitted=total_submitted,
        confirmation_rate=round(conf_rate, 4),
        tier_distribution=tier_dist,
        top_movers=top_movers,
        asi_trend=asi_trend,
    )
