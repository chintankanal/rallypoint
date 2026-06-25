"""
Shared SQL fragments for leaderboard-style player listings.

Used by both the global leaderboard (leaderboard_service)
and the per-academy roster (academy_service)
so their enrichment metrics and ordering stay identical.

All fragments assume the player table is aliased as `p`.
"""

LEADERBOARD_ENRICHMENT_JOINS = """

LEFT JOIN LATERAL (

    SELECT COUNT(*) FILTER (WHERE m.winner_id = p.player_id) AS wins

    FROM match m

    WHERE (m.player_a_id = p.player_id
        OR m.player_b_id = p.player_id)

      AND m.confirmation_status <> 'VOIDED'

      AND m.rating_eligible = TRUE

      AND m.ratings_applied_at IS NOT NULL

) ws ON TRUE

LEFT JOIN LATERAL (

    SELECT rh.delta AS last_rating_change

    FROM rating_history rh

    JOIN match mr
      ON mr.match_id = rh.match_id

    WHERE rh.player_id = p.player_id

      AND rh.is_rollback = FALSE

      AND mr.confirmation_status <> 'VOIDED'

    ORDER BY
        mr.match_timestamp DESC,
        rh.created_at DESC

    LIMIT 1

) tr ON TRUE

LEFT JOIN LATERAL (

    SELECT
        ROUND(AVG(x.set_margin), 2) AS dominance,
        COUNT(*) AS dominance_sample

    FROM (

        SELECT
            CASE
                WHEN mm.player_a_id = p.player_id
                THEN mm.sets_won_a - mm.sets_won_b
                ELSE mm.sets_won_b - mm.sets_won_a
            END AS set_margin

        FROM match mm

        WHERE (
                mm.player_a_id = p.player_id
             OR mm.player_b_id = p.player_id
        )

          AND mm.confirmation_status <> 'VOIDED'

          AND mm.rating_eligible = TRUE

          AND mm.ratings_applied_at IS NOT NULL

          AND mm.is_retirement = FALSE

        ORDER BY
            mm.match_timestamp DESC

        LIMIT 5

    ) x

) dom ON TRUE

"""

LEADERBOARD_ENRICHMENT_COLUMNS = """

CASE
    WHEN p.rated_matches_completed > 0
    THEN ROUND(
        ws.wins::numeric
        / p.rated_matches_completed
        * 100,
        1
    )
    ELSE NULL
END AS win_pct,

tr.last_rating_change::float AS last_rating_change,

dom.dominance::float AS dominance,

dom.dominance_sample AS dominance_sample

"""

LEADERBOARD_ORDER_BY = """

(p.rated_matches_completed = 0) ASC,

p.current_rating DESC,

p.rated_matches_completed DESC,

p.name ASC

"""
