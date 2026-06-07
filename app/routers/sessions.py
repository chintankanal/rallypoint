import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.services.fixture_config import load_fixture_config
from app.services.rating_regime import regime_thresholds
from app.utils.rating_math import _load_config, get_tier
from app.dependencies.auth import get_current_user, require_roles
from schemas.session import (
    FixtureSlotResponse,
    GenerateFixturesRequest,
    SessionCreate,
    SessionDiagnostics,
    SessionFixturesResponse,
    SessionResponse,
    SessionStatusUpdate,
)

router = APIRouter(tags=["sessions"])

_ADMIN_COACH = Depends(require_roles("ADMIN", "COACH"))
_ANY = Depends(get_current_user)


@router.get("/events/{event_id}/sessions", response_model=list[SessionResponse])
def list_sessions(event_id: str, _: dict = _ANY):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, event_id, session_date, session_minutes, num_tables,
                       match_format, bootstrap_phase, rating_spread, matches_per_player,
                       present_player_count, status, generated_at, created_at
                FROM session
                WHERE event_id = %s
                ORDER BY session_date DESC, created_at DESC
                """,
                (event_id,),
            )
            return [SessionResponse(**dict(r)) for r in cur.fetchall()]


@router.post(
    "/events/{event_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    event_id: str,
    body: SessionCreate,
    current_user: dict = _ADMIN_COACH,
):
    session_id = str(uuid.uuid4())
    user_id = current_user["user_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_id, scheduling_mode, default_match_format FROM event WHERE event_id = %s",
                (event_id,),
            )
            event = cur.fetchone()
            if not event:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            if event["scheduling_mode"] != "INTRA_ACADEMY":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sessions can only be created for INTRA_ACADEMY events",
                )

            match_format = (
                body.match_format.value
                if body.match_format
                else event["default_match_format"]
            )
            if not match_format:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="match_format is required — the event has no default_match_format set",
                )

            cur.execute(
                """
                INSERT INTO session (
                    session_id, event_id, session_date, session_minutes, num_tables,
                    match_format, bootstrap_phase, rating_spread, matches_per_player,
                    present_player_count, status, created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    session_id, event_id, session_date, session_minutes, num_tables,
                    match_format, bootstrap_phase, rating_spread, matches_per_player,
                    present_player_count, status, generated_at, created_at
                """,
                (
                    session_id, event_id, body.session_date, body.session_minutes,
                    body.num_tables, match_format,
                    "DISCOVERY", 0.0, 0, 0,
                    "SCHEDULED", user_id, user_id,
                ),
            )
            row = dict(cur.fetchone())

    return SessionResponse(**row)


@router.post(
    "/sessions/{session_id}/generate-fixtures",
    response_model=SessionFixturesResponse,
)
def generate_session_fixtures(
    session_id: str,
    body: GenerateFixturesRequest,
    current_user: dict = _ADMIN_COACH,
):
    from app.services.fixture_engine import generate_fixtures

    user_id = current_user["user_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM session WHERE session_id = %s", (session_id,))
            session = cur.fetchone()
            if not session:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            if session["status"] == "CANCELLED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot generate fixtures for a cancelled session",
                )
            if session["generated_at"] is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Fixtures already generated for this session",
                )

            cur.execute(
                """
                SELECT player_id::text, name, current_rating,
                       rated_matches_completed, virtual_matches
                FROM player
                WHERE player_id = ANY(%s::uuid[]) AND status = 'ACTIVE'
                """,
                (body.player_ids,),
            )
            cfg = _load_config()
            players = []
            for row in cur.fetchall():
                p = dict(row)
                p["tier"] = get_tier(float(p["current_rating"]), cfg)
                players.append(p)
            if len(players) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least 2 active players required",
                )

            pids = [p["player_id"] for p in players]

            cur.execute(
                """
                SELECT DISTINCT player_a_id::text, player_b_id::text
                FROM match
                WHERE match_date >= CURRENT_DATE - INTERVAL '7 days'
                  AND player_a_id = ANY(%s::uuid[])
                  AND player_b_id = ANY(%s::uuid[])
                """,
                (pids, pids),
            )
            recent_pairs = {(r["player_a_id"], r["player_b_id"]) for r in cur.fetchall()}

            cur.execute(
                """
                SELECT COUNT(*) AS offset
                FROM session s
                WHERE s.event_id = %s
                  AND s.session_date < %s
                  AND s.generated_at IS NOT NULL
                """,
                (session["event_id"], session["session_date"]),
            )
            rotation_offset = cur.fetchone()["offset"]

            result = generate_fixtures(
                players=players,
                recent_match_pairs=recent_pairs,
                session_minutes=session["session_minutes"],
                num_tables=session["num_tables"],
                match_format=session["match_format"],
                rotation_offset=rotation_offset,
            )

            cur.execute(
                """
                UPDATE session
                SET bootstrap_phase = %s, rating_spread = %s, matches_per_player = %s,
                    present_player_count = %s, regime = %s,
                    core_spread = %s, provisional_count = %s,
                    generated_at = NOW(), generated_by = %s,
                    updated_by = %s, updated_at = NOW()
                WHERE session_id = %s
                """,
                (
                    result["phase"], result["spread"], result["matches_per_player"],
                    len(players), result["regime"], result["core_spread"], result["provisional_count"],
                    user_id, user_id, session_id,
                ),
            )

            slot_rows = []
            for slot in result["slots"]:
                slot_id = str(uuid.uuid4())
                slot_status = "BYE" if slot["player_b_id"] is None else "SCHEDULED"
                cur.execute(
                    """
                    INSERT INTO fixture_slot (
                        slot_id, session_id, round_number, wave_number, sub_round, table_number,
                        round_intent, gap_band, player_a_role, player_b_role,
                        match_category, player_a_id, player_b_id,
                        expected_rating_gap, status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
                    )
                    RETURNING slot_id, round_number, wave_number, sub_round, table_number,
                              round_intent, gap_band, player_a_role, player_b_role,
                              match_category, player_a_id::text, player_b_id::text,
                              expected_rating_gap, status, match_id
                    """,
                    (
                        slot_id, session_id,
                        slot["round_number"], slot["wave_number"], slot["sub_round"], slot["table_number"],
                        slot["round_intent"], slot["gap_band"],
                        slot["player_a_role"], slot["player_b_role"],
                        slot["match_category"], slot["player_a_id"], slot["player_b_id"],
                        slot["expected_rating_gap"], slot_status,
                    ),
                )
                slot_rows.append(dict(cur.fetchone()))

    players_by_id = {p["player_id"]: p for p in players}
    response_slots = [
        FixtureSlotResponse(
            slot_id=str(sr["slot_id"]),
            round_number=sr["round_number"],
            wave_number=sr["wave_number"],
            sub_round=sr["sub_round"],
            table_number=sr["table_number"],
            round_intent=sr["round_intent"],
            gap_band=sr["gap_band"],
            player_a_role=sr["player_a_role"],
            player_b_role=sr["player_b_role"],
            match_category=sr["match_category"],
            player_a=players_by_id.get(sr["player_a_id"]),
            player_b=players_by_id.get(sr["player_b_id"]) if sr["player_b_id"] else None,
            expected_rating_gap=float(sr["expected_rating_gap"]),
            status=sr["status"],
            match_id=str(sr["match_id"]) if sr.get("match_id") else None,
        )
        for sr in slot_rows
    ]

    from app.services.fixture_preflight import preflight_session
    warnings = preflight_session(
        players,
        num_tables=session["num_tables"],
        matches_per_player_estimate=result["matches_per_player"],
    )

    return SessionFixturesResponse(
        session_id=session_id,
        bootstrap_phase=result["phase"],
        matches_per_player=result["matches_per_player"],
        fixture_slots_created=len(response_slots),
        slots=response_slots,
        warnings=warnings,
        diagnostics=SessionDiagnostics(
            regime=result["regime"],
            bootstrap_phase=result["phase"],
            raw_spread=result["spread"],
            core_spread=result["core_spread"],
            provisional_count=result["provisional_count"],
            present_player_count=result["present_player_count"],
            competitive_max_gap=result["competitive_max_gap"],
            stretch_max_gap=result["stretch_max_gap"],
        ),
    )


@router.get("/sessions/{session_id}/fixtures", response_model=SessionFixturesResponse)
def get_session_fixtures(session_id: str, _: dict = _ANY):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM session WHERE session_id = %s", (session_id,))
            session = cur.fetchone()
            if not session:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

            cur.execute(
                """
                SELECT
                    fs.slot_id, fs.round_number, fs.wave_number, fs.sub_round, fs.table_number,
                    fs.round_intent, fs.gap_band, fs.player_a_role, fs.player_b_role,
                    fs.match_category, fs.expected_rating_gap, fs.status, fs.match_id,
                    json_build_object(
                        'player_id', pa.player_id, 'name', pa.name,
                        'current_rating', pa.current_rating
                    ) AS player_a,
                    CASE WHEN fs.player_b_id IS NULL THEN NULL
                         ELSE json_build_object(
                             'player_id', pb.player_id, 'name', pb.name,
                             'current_rating', pb.current_rating
                         )
                    END AS player_b,
                    CASE WHEN m.match_id IS NULL THEN NULL
                         ELSE json_build_object(
                             'sets_won_a', m.sets_won_a,
                             'sets_won_b', m.sets_won_b,
                             'winner_id', m.winner_id::text,
                             'confirmation_status', m.confirmation_status,
                             'is_retirement', m.is_retirement
                         )
                    END AS match_result
                FROM fixture_slot fs
                JOIN player pa ON pa.player_id = fs.player_a_id
                LEFT JOIN player pb ON pb.player_id = fs.player_b_id
                LEFT JOIN match m ON m.match_id = fs.match_id
                WHERE fs.session_id = %s
                ORDER BY fs.round_number, fs.wave_number, CASE WHEN fs.player_b_id IS NULL THEN 1 ELSE 0 END, fs.table_number
                """,
                (session_id,),
            )
            slots = [dict(r) for r in cur.fetchall()]
            # Load config to compute authoritative tiers for returned players
            cfg = _load_config()

            response_slots = [
        FixtureSlotResponse(
            slot_id=str(s["slot_id"]),
            round_number=s["round_number"],
            wave_number=s["wave_number"],
            sub_round=s["sub_round"],
            table_number=s["table_number"],
            round_intent=s["round_intent"],
            gap_band=s["gap_band"],
            player_a_role=s["player_a_role"],
            player_b_role=s["player_b_role"],
            match_category=s["match_category"],
            player_a={**s["player_a"], "tier": get_tier(float(s["player_a"]["current_rating"]), cfg)},
            player_b=( {**s["player_b"], "tier": get_tier(float(s["player_b"]["current_rating"]), cfg)} if s["player_b"] else None ),
            expected_rating_gap=float(s["expected_rating_gap"]),
            status=s["status"],
            match_id=str(s["match_id"]) if s.get("match_id") else None,
            match_result=s.get("match_result"),
        )
        for s in slots
    ]

    diagnostics = None
    if session.get("regime") is not None:
        thresholds = regime_thresholds(session["regime"], cfg=load_fixture_config())
        diagnostics = SessionDiagnostics(
            regime=session["regime"],
            bootstrap_phase=session["bootstrap_phase"],
            raw_spread=float(session["rating_spread"]),
            core_spread=float(session["core_spread"]) if session["core_spread"] is not None else None,
            provisional_count=session["provisional_count"],
            present_player_count=session["present_player_count"],
            competitive_max_gap=thresholds.competitive_max_gap,
            stretch_max_gap=thresholds.stretch_max_gap,
        )
    else:
        diagnostics = SessionDiagnostics(
            regime=None,
            bootstrap_phase=session["bootstrap_phase"],
            raw_spread=float(session["rating_spread"]),
            core_spread=float(session["core_spread"]) if session["core_spread"] is not None else None,
            provisional_count=session["provisional_count"],
            present_player_count=session["present_player_count"],
            competitive_max_gap=None,
            stretch_max_gap=None,
        )

    return SessionFixturesResponse(
        session_id=str(session["session_id"]),
        bootstrap_phase=session["bootstrap_phase"],
        matches_per_player=session["matches_per_player"],
        fixture_slots_created=len(response_slots),
        slots=response_slots,
        diagnostics=diagnostics,
    )


@router.post("/sessions/{session_id}/apply-ratings")
def apply_session_ratings(
    session_id: str,
    current_user: dict = _ADMIN_COACH,
):
    from app.services.rating_engine import apply_ratings_batch
    from app.services.webhook_service import fire

    user_id = current_user["user_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.session_id, e.scheduling_mode "
                "FROM session s JOIN event e ON e.event_id = s.event_id "
                "WHERE s.session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            if row["scheduling_mode"] != "INTRA_ACADEMY":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="On-demand rating is only available for INTRA_ACADEMY sessions",
                )

            # Auto-confirm all PENDING eligible matches in this session
            cur.execute(
                """
                UPDATE match
                SET confirmation_status = 'AUTO_CONFIRMED',
                    confirmed_at = NOW(),
                    updated_at = NOW()
                WHERE session_id = %s
                  AND confirmation_status = 'PENDING'
                  AND rating_eligible = TRUE
                  AND ratings_applied_at IS NULL
                RETURNING match_id::text
                """,
                (session_id,),
            )
            auto_confirmed_count = len(cur.fetchall())

            # Collect all confirmed + eligible + unrated matches
            cur.execute(
                """
                SELECT match_id::text FROM match
                WHERE session_id = %s
                  AND confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')
                  AND rating_eligible = TRUE
                  AND ratings_applied_at IS NULL
                """,
                (session_id,),
            )
            match_ids = [r["match_id"] for r in cur.fetchall()]

        if not match_ids:
            return {
                "session_id": session_id,
                "matches_rated": 0,
                "matches_auto_confirmed": auto_confirmed_count,
                "tier_changes": [],
                "already_up_to_date": True,
            }

        tier_changes = apply_ratings_batch(conn, match_ids)

    for tc in tier_changes:
        fire("player.tier_changed", tc)

    return {
        "session_id": session_id,
        "matches_rated": len(match_ids),
        "matches_auto_confirmed": auto_confirmed_count,
        "tier_changes": tier_changes,
        "already_up_to_date": False,
    }


@router.patch("/sessions/{session_id}/status", response_model=SessionResponse)
def update_session_status(
    session_id: str,
    body: SessionStatusUpdate,
    _: dict = _ADMIN_COACH,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT session_id FROM session WHERE session_id = %s", (session_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

            cur.execute(
                """
                UPDATE session SET status = %s, updated_at = NOW()
                WHERE session_id = %s
                RETURNING
                    session_id, event_id, session_date, session_minutes, num_tables,
                    match_format, bootstrap_phase, rating_spread, matches_per_player,
                    present_player_count, status, generated_at, created_at
                """,
                (body.status, session_id),
            )
            row = dict(cur.fetchone())

    return SessionResponse(**row)
