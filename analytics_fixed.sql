WITH evt AS (

    SELECT e.event_id, e.name
    FROM event e
    WHERE e.scheduling_mode = 'INTER_ACADEMY'
      AND e.event_type IN ('TOURNAMENT_MANAGED', 'TOURNAMENT_EXTERNAL')
      AND EXISTS (
            SELECT 1
            FROM match m
            WHERE m.event_id = e.event_id
              AND m.match_date::date BETWEEN CURRENT_DATE - 2 AND CURRENT_DATE
      )
    ORDER BY e.end_date DESC NULLS LAST,
             e.start_date DESC
    LIMIT 1

    -- If the wrong event is picked, replace this whole CTE with:
    -- SELECT event_id, name
    -- FROM event
    -- WHERE event_id = 'PASTE-UUID-HERE'
),

parts AS (

    SELECT DISTINCT pid
    FROM (
        SELECT m.player_a_id AS pid
        FROM match m
        JOIN evt ON m.event_id = evt.event_id

        UNION

        SELECT m.player_b_id
        FROM match m
        JOIN evt ON m.event_id = evt.event_id
    ) z
),

labeled AS (

    SELECT
        p.player_id,
        p.name,
        a.name AS academy,
        p.current_rating,

        CASE
            WHEN p.current_rating < 900 THEN 1
            WHEN p.current_rating < 1100 THEN 2
            WHEN p.current_rating < 1300 THEN 3
            WHEN p.current_rating < 1500 THEN 4
            ELSE 5
        END AS band_no,

        CASE
            WHEN p.current_rating < 900 THEN 'Beginner'
            WHEN p.current_rating < 1100 THEN 'Intermediate'
            WHEN p.current_rating < 1300 THEN 'Advanced'
            WHEN p.current_rating < 1500 THEN 'Elite'
            ELSE 'National Track'
        END AS tier

    FROM parts
    JOIN player p
      ON p.player_id = parts.pid
    JOIN academy a
      ON a.academy_id = p.primary_academy_id
),

chg AS (

    SELECT
        rh.player_id,
        SUM(rh.delta) AS event_delta,
        COUNT(*) AS rated_matches

    FROM rating_history rh
    JOIN match m
      ON m.match_id = rh.match_id
    JOIN evt
      ON m.event_id = evt.event_id

    WHERE rh.is_rollback = FALSE
    GROUP BY rh.player_id
),

mh AS (

    SELECT
        rh.match_id,
        rh.player_id,
        rh.rating_before

    FROM rating_history rh
    JOIN match m
      ON m.match_id = rh.match_id
    JOIN evt
      ON m.event_id = evt.event_id

    WHERE rh.is_rollback = FALSE
),

head AS (

    SELECT

        (SELECT name FROM evt)
            AS tournament,

        (SELECT COUNT(*)
         FROM event_player_registration r, evt
         WHERE r.event_id = evt.event_id)
            AS reg,

        (SELECT COUNT(*)
         FROM event_player_registration r, evt
         WHERE r.event_id = evt.event_id
           AND r.status IN ('REGISTERED', 'CHECKED_IN'))
            AS active,

        (SELECT COUNT(*)
         FROM event_player_registration r, evt
         WHERE r.event_id = evt.event_id
           AND r.status = 'WITHDRAWN')
            AS withdrawn,

        (SELECT COUNT(*)
         FROM event_player_registration r, evt
         WHERE r.event_id = evt.event_id
           AND r.status = 'NO_SHOW')
            AS no_show,

        (SELECT COUNT(DISTINCT ac)
         FROM (
              SELECT m.player_a_academy_id AS ac
              FROM match m, evt
              WHERE m.event_id = evt.event_id

              UNION

              SELECT m.player_b_academy_id
              FROM match m, evt
              WHERE m.event_id = evt.event_id
         ) x)
            AS academies,

        (SELECT COUNT(*)
         FROM match m, evt
         WHERE m.event_id = evt.event_id)
            AS total_m,

        (SELECT COUNT(*)
         FROM match m, evt
         WHERE m.event_id = evt.event_id
           AND m.player_a_academy_id <> m.player_b_academy_id)
            AS cross_m,

        (SELECT COUNT(*)
         FROM match m, evt
         WHERE m.event_id = evt.event_id
           AND m.rating_eligible)
            AS eligible_m,

        (SELECT COUNT(*)
         FROM match m, evt
         WHERE m.event_id = evt.event_id
           AND m.ratings_applied_at IS NOT NULL)
            AS rated_m,

        (SELECT COUNT(*)
         FROM match m, evt
         WHERE m.event_id = evt.event_id
           AND m.is_retirement)
            AS retired_m
),

top_gainers AS (

    SELECT
        ROW_NUMBER() OVER (
            ORDER BY chg.event_delta DESC, p.name
        ) AS ord,
        p.name,
        a.name AS academy,
        '+' || ROUND(chg.event_delta::numeric, 1)::text
            || ' (' || chg.rated_matches || ' matches)' AS value

    FROM chg
    JOIN player p
      ON p.player_id = chg.player_id
    JOIN academy a
      ON a.academy_id = p.primary_academy_id
),

biggest_upsets AS (

    SELECT
        ROW_NUMBER() OVER (
            ORDER BY (lh.rating_before - wh.rating_before) DESC, m.match_id
        ) AS ord,
        wp.name || ' beat ' || lp.name AS label,
        m.sets_won_a || '-' || m.sets_won_b
            || ' ('
            || ROUND(wh.rating_before::numeric, 0)::text
            || ' vs '
            || ROUND(lh.rating_before::numeric, 0)::text
            || ')' AS detail,
        '+' || ROUND((lh.rating_before - wh.rating_before)::numeric, 0)::text
            || ' gap' AS value

    FROM match m
    JOIN evt
      ON m.event_id = evt.event_id
    JOIN mh wh
      ON wh.match_id = m.match_id
     AND wh.player_id = m.winner_id
    JOIN mh lh
      ON lh.match_id = m.match_id
     AND lh.player_id <> m.winner_id
    JOIN player wp
      ON wp.player_id = m.winner_id
    JOIN player lp
      ON lp.player_id = lh.player_id

    WHERE lh.rating_before > wh.rating_before
),

most_active AS (

    SELECT
        ROW_NUMBER() OVER (
            ORDER BY mp.c DESC, p.name
        ) AS ord,
        p.name,
        a.name AS academy,
        mp.c AS match_count

    FROM (

        SELECT pid, COUNT(*) AS c
        FROM (

            SELECT m.player_a_id AS pid
            FROM match m
            JOIN evt
              ON m.event_id = evt.event_id

            UNION ALL

            SELECT m.player_b_id
            FROM match m
            JOIN evt
              ON m.event_id = evt.event_id

        ) z

        GROUP BY pid

    ) mp
    JOIN player p
      ON p.player_id = mp.pid
    JOIN academy a
      ON a.academy_id = p.primary_academy_id
)

SELECT section, label, detail, value
FROM (

    SELECT
        1 AS seq,
        v.ord,
        'A - Headline' AS section,
        v.label,
        NULL::text AS detail,
        v.val AS value

    FROM head,
    LATERAL (
        VALUES
          (1, 'Tournament', head.tournament),
          (2, 'Players registered', head.reg::text),
          (3, 'Active (reg / checked-in)', head.active::text),
          (4, 'Withdrawn', head.withdrawn::text),
          (5, 'No-show', head.no_show::text),
          (6, 'Academies in play', head.academies::text),
          (7, 'Total matches', head.total_m::text),
          (8, 'Cross-academy matches', head.cross_m::text),
          (9, 'Rating-eligible matches', head.eligible_m::text),
          (10, 'Rated matches', head.rated_m::text),
          (11, 'Retirements', head.retired_m::text)
    ) v(ord, label, val)

    UNION ALL

    SELECT
        2 AS seq,
        t.band_no AS ord,
        'B - Matches by tier' AS section,
        t.tier_band AS label,
        NULL::text AS detail,
        COUNT(*)::text AS value

    FROM (

        SELECT
            m.match_id,

            CASE
                WHEN (pa.current_rating + pb.current_rating) / 2 < 900 THEN 1
                WHEN (pa.current_rating + pb.current_rating) / 2 < 1100 THEN 2
                WHEN (pa.current_rating + pb.current_rating) / 2 < 1300 THEN 3
                WHEN (pa.current_rating + pb.current_rating) / 2 < 1500 THEN 4
                ELSE 5
            END AS band_no,

            CASE
                WHEN (pa.current_rating + pb.current_rating) / 2 < 900
                    THEN 'Beginner (<900)'
                WHEN (pa.current_rating + pb.current_rating) / 2 < 1100
                    THEN 'Intermediate (900-1099)'
                WHEN (pa.current_rating + pb.current_rating) / 2 < 1300
                    THEN 'Advanced (1100-1299)'
                WHEN (pa.current_rating + pb.current_rating) / 2 < 1500
                    THEN 'Elite (1300-1499)'
                ELSE 'National Track (1500+)'
            END AS tier_band

        FROM match m
        JOIN evt ON m.event_id = evt.event_id
        JOIN player pa ON pa.player_id = m.player_a_id
        JOIN player pb ON pb.player_id = m.player_b_id

    ) t

    GROUP BY t.band_no, t.tier_band

    UNION ALL

    SELECT
        3 AS seq,
        band_no AS ord,
        'C - Participants by tier' AS section,
        tier AS label,
        NULL::text AS detail,
        COUNT(*)::text AS value

    FROM labeled
    GROUP BY band_no, tier

    UNION ALL

    SELECT
        4 AS seq,
        band_no * 10 + rn AS ord,
        'D - Top rated per tier' AS section,
        name AS label,
        tier || ' - ' || academy AS detail,
        current_rating::text AS value

    FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY band_no
                   ORDER BY current_rating DESC, name
               ) AS rn
        FROM labeled
    ) r
    WHERE rn <= 3

    UNION ALL

    SELECT
        5 AS seq,
        ord,
        'E - Biggest gainers' AS section,
        name AS label,
        academy AS detail,
        value
    FROM top_gainers
    WHERE ord <= 5

    UNION ALL

    SELECT
        6 AS seq,
        ord,
        'F - Biggest upsets' AS section,
        label,
        detail,
        value
    FROM biggest_upsets
    WHERE ord <= 5

    UNION ALL

    SELECT
        7 AS seq,
        ord,
        'G - Most active' AS section,
        name AS label,
        academy AS detail,
        match_count::text || ' matches' AS value
    FROM most_active
    WHERE ord <= 5

) all_stats
ORDER BY seq, ord;
