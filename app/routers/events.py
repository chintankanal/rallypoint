import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.dependencies.auth import get_current_user, require_roles
from app.services import event_service, event_player_service
from app.services.fixture_engine import generate_league_fixtures
from app.services.rating_engine import apply_ratings_batch
from app.services.webhook_service import fire
from schemas.event import (
    AddAcademyToEvent,
    AssignRefereeRequest,
    AssignUmpireRequest,
    EventCreate,
    EventFixturePlayer,
    EventFixtureSlotResponse,
    EventFixturesResponse,
    EventPlayerRegister,
    EventRosterResponse,
    EventResponse,
    EventStatusUpdate,
    GenerateEventFixturesRequest,
    FixtureQualityReport,
    RefereeAssignmentResponse,
    UmpireAssignmentResponse,
)

router = APIRouter(prefix="/events", tags=["events"])

_ADMIN = Depends(require_roles("ADMIN"))
_ADMIN_COACH = Depends(require_roles("ADMIN", "COACH"))
_ANY = Depends(get_current_user)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("ADMIN", "COACH"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins and coaches only")
    try:
        row = event_service.create_event(body, current_user["role"], current_user.get("academy_id"), current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return EventResponse(**row)


@router.get("", tags=["events"])
def list_events(current_user: dict = Depends(get_current_user)):
    """List events — admin sees all, coach sees events for their academy."""
    return {"items": event_service.list_events(current_user["role"], current_user.get("academy_id"))}


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: str, _: dict = _ADMIN_COACH):
    row = event_service.get_event(event_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse(**row)


@router.get("/{event_id}/fixture-quality", response_model=FixtureQualityReport)
def get_event_fixture_quality(event_id: str, _: dict = _ADMIN_COACH):
    quality = event_service.get_fixture_quality_report(event_id)
    if not quality:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return FixtureQualityReport(**quality)


@router.post("/{event_id}/academies", response_model=EventResponse)
def add_academy_to_event(event_id: str, body: AddAcademyToEvent, _: dict = _ADMIN):
    row = event_service.add_academy_to_event(event_id, body.academy_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse(**row)


@router.patch("/{event_id}/status", response_model=EventResponse)
def update_event_status(event_id: str, body: EventStatusUpdate, _: dict = _ADMIN):
    try:
        row = event_service.update_event_status(event_id, body.status.value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.args[0])
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse(**row)


@router.post(
    "/{event_id}/referees",
    response_model=RefereeAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_referee(event_id: str, body: AssignRefereeRequest, _: dict = _ADMIN):
    row = event_service.assign_referee(event_id, body.user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return RefereeAssignmentResponse(**row)


@router.post(
    "/{event_id}/umpires",
    response_model=UmpireAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_umpire(event_id: str, body: AssignUmpireRequest, _: dict = _ADMIN):
    row = event_service.assign_umpire(event_id, body.user_id, body.table_number)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return UmpireAssignmentResponse(**row)


# ── Player registration ───────────────────────────────────────────────────────

@router.get("/{event_id}/players", response_model=EventRosterResponse)
def list_event_players(event_id: str, _: dict = _ANY):
    items = event_player_service.list_players(event_id)
    return EventRosterResponse(event_id=event_id, total=len(items), items=items)


@router.post(
    "/{event_id}/players",
    response_model=EventRosterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_event_player(
    event_id: str,
    body: EventPlayerRegister,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in ("ADMIN", "COACH", "PLAYER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised")
    try:
        row = event_player_service.register_player(
            event_id=event_id,
            player_id=body.player_id,
            registered_by=current_user["user_id"],
            caller_role=current_user["role"],
            caller_academy_id=current_user.get("academy_id"),
            caller_user_id=current_user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event or player not found")
    items = event_player_service.list_players(event_id)
    return EventRosterResponse(event_id=event_id, total=len(items), items=items)


@router.delete("/{event_id}/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_event_player(
    event_id: str,
    player_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in ("ADMIN", "COACH", "PLAYER"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised")
    try:
        removed = event_player_service.remove_player(
            event_id=event_id,
            player_id=player_id,
            withdrawn_by=current_user["user_id"],
            caller_role=current_user["role"],
            caller_academy_id=current_user.get("academy_id"),
            caller_user_id=current_user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")


# ── Inter-academy league fixtures ─────────────────────────────────────────────

def _require_host_coach_or_admin(current_user: dict, event: dict) -> None:
    """Raise 403 unless caller is ADMIN or the host-academy COACH."""
    if current_user["role"] == "ADMIN":
        return
    if current_user["role"] == "COACH":
        host = str(event.get("host_academy_id") or "")
        if host and host == current_user.get("academy_id"):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the host academy coach or an admin can generate fixtures",
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised")


@router.post("/{event_id}/generate-fixtures", response_model=EventFixturesResponse)
def generate_event_fixtures(
    event_id: str,
    body: GenerateEventFixturesRequest,
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Fetch and validate event
            cur.execute(
                """
                SELECT event_id, scheduling_mode, event_type, status, fixture_state,
                       host_academy_id, season_id, start_date
                FROM event WHERE event_id = %s
                """,
                (event_id,),
            )
            event = cur.fetchone()
            if not event:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            if event["scheduling_mode"] != "INTER_ACADEMY" or event["event_type"] != "LEAGUE":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Fixture generation is only supported for INTER_ACADEMY LEAGUE events",
                )
            if event["status"] not in ("SCHEDULED", "IN_PROGRESS"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot generate fixtures for a completed or cancelled event",
                )

            fixture_state = event["fixture_state"]
            if fixture_state in ("FIXTURE_FROZEN", "RATINGS_APPLIED"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot generate fixtures: fixtures are {fixture_state.lower().replace('_', ' ')}. "
                           "Unlock fixtures first to allow regeneration.",
                )

            # Block regeneration if any fixture slots already have matches linked
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM event_fixture_slot WHERE event_id = %s AND match_id IS NOT NULL",
                (event_id,),
            )
            match_count = cur.fetchone()["cnt"]
            if match_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot regenerate fixtures: {match_count} match result(s) already recorded. "
                           "Clear match results first or create a new event.",
                )

            _require_host_coach_or_admin(current_user, dict(event))

            # Fetch registered players with academy info
            cur.execute(
                """
                SELECT p.player_id::text, p.name, p.current_rating,
                       p.primary_academy_id::text AS academy_id,
                       a.name AS academy_name
                FROM event_player_registration epr
                JOIN player p ON p.player_id = epr.player_id
                JOIN academy a ON a.academy_id = p.primary_academy_id
                WHERE epr.event_id = %s
                  AND epr.status IN ('REGISTERED', 'CHECKED_IN')
                  AND p.status = 'ACTIVE'
                ORDER BY p.current_rating DESC
                """,
                (event_id,),
            )
            all_players = [dict(r) for r in cur.fetchall()]

            if len(all_players) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least 2 registered active players required to generate fixtures",
                )

            # Group players by academy
            players_by_academy: dict[str, list[dict]] = {}
            for p in all_players:
                players_by_academy.setdefault(p["academy_id"], []).append(p)

            academies_with_players = len(players_by_academy)
            if academies_with_players < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least 2 different academies must have registered players",
                )

            # Fetch played_pairs from immediate prior league event in same season
            played_pairs: set[tuple] = set()
            season_id = event["season_id"]
            if season_id:
                cur.execute(
                    """
                    SELECT e2.event_id
                    FROM event e2
                    WHERE e2.season_id = %s
                      AND e2.scheduling_mode = 'INTER_ACADEMY'
                      AND e2.event_type = 'LEAGUE'
                      AND e2.end_date < %s
                    ORDER BY e2.end_date DESC
                    LIMIT 1
                    """,
                    (str(season_id), event["start_date"]),
                )
                prior = cur.fetchone()
                if prior:
                    pids = [p["player_id"] for p in all_players]
                    cur.execute(
                        """
                        SELECT DISTINCT player_a_id::text, player_b_id::text
                        FROM match
                        WHERE event_id = %s
                          AND player_a_id = ANY(%s::uuid[])
                          AND player_b_id = ANY(%s::uuid[])
                        """,
                        (str(prior["event_id"]), pids, pids),
                    )
                    played_pairs = {
                        (r["player_a_id"], r["player_b_id"]) for r in cur.fetchall()
                    }

            # Wipe existing unplayed fixture slots for this event before regenerating
            cur.execute(
                "DELETE FROM event_fixture_slot WHERE event_id = %s AND status IN ('SCHEDULED', 'BYE')",
                (event_id,),
            )

            # Generate fixtures. num_tables drives the wave scheduler (Phase 3).
            result = generate_league_fixtures(
                players_by_academy=players_by_academy,
                played_pairs=played_pairs,
                strategy=body.fixture_strategy,
                num_tables=body.num_tables,
            )

            # Persist fixture slots
            players_by_id = {p["player_id"]: p for p in all_players}
            slot_rows: list[dict] = []
            for slot in result["slots"]:
                slot_id = str(uuid.uuid4())
                slot_status = "BYE" if slot["player_b_id"] is None else "SCHEDULED"
                cur.execute(
                    """
                    INSERT INTO event_fixture_slot (
                        slot_id, event_id, round_number, wave_number, table_number,
                        round_intent, gap_band, player_a_role, player_b_role,
                        match_category, player_a_id, player_b_id,
                        expected_rating_gap, status, fixture_strategy
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                    RETURNING slot_id::text, round_number, wave_number, table_number,
                              round_intent, gap_band, player_a_role, player_b_role,
                              match_category, player_a_id::text, player_b_id::text,
                              expected_rating_gap, status, match_id, fixture_strategy
                    """,
                    (
                        slot_id, event_id,
                        slot["round_number"], slot["wave_number"], slot["table_number"],
                        slot["round_intent"], slot["gap_band"],
                        slot["player_a_role"], slot["player_b_role"],
                        slot["match_category"],
                        slot["player_a_id"], slot["player_b_id"],
                        slot["expected_rating_gap"], slot_status,
                        body.fixture_strategy,
                    ),
                )
                slot_rows.append(dict(cur.fetchone()))

            # Transition fixture_state to FIXTURES_READY (locks roster, allows regeneration)
            cur.execute(
                "UPDATE event SET fixture_state = 'FIXTURES_READY' WHERE event_id = %s",
                (event_id,),
            )

    response_slots = _build_slot_responses(slot_rows, players_by_id)

    from app.services.fixture_preflight import preflight_event
    warnings = preflight_event(
        players_by_academy,
        strategy=body.fixture_strategy,
        num_tables=body.num_tables,
    )

    return EventFixturesResponse(
        event_id=event_id,
        total_rounds=result["total_rounds"],
        total_slots=len(response_slots),
        cross_academy_pct=result["cross_academy_pct"],
        fixture_state="FIXTURES_READY",
        slots=response_slots,
        warnings=warnings,
    )


@router.get("/{event_id}/fixture-slots", response_model=EventFixturesResponse)
def get_event_fixtures(event_id: str, _: dict = _ANY):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT event_id, fixture_state FROM event WHERE event_id = %s", (event_id,))
            ev = cur.fetchone()
            if not ev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            current_fixture_state = ev["fixture_state"]

            cur.execute(
                """
                SELECT efs.slot_id::text, efs.round_number, efs.wave_number, efs.table_number,
                       efs.round_intent, efs.gap_band,
                       efs.player_a_role, efs.player_b_role,
                       efs.match_category, efs.expected_rating_gap, efs.status,
                       efs.match_id::text, efs.fixture_strategy,
                       efs.player_a_id::text, pa.name AS player_a_name,
                       pa.current_rating AS player_a_rating,
                       pa.primary_academy_id::text AS player_a_academy_id,
                       aa.name AS player_a_academy_name,
                       efs.player_b_id::text, pb.name AS player_b_name,
                       pb.current_rating AS player_b_rating,
                       pb.primary_academy_id::text AS player_b_academy_id,
                       ab.name AS player_b_academy_name
                FROM event_fixture_slot efs
                JOIN player pa ON pa.player_id = efs.player_a_id
                JOIN academy aa ON aa.academy_id = pa.primary_academy_id
                LEFT JOIN player pb ON pb.player_id = efs.player_b_id
                LEFT JOIN academy ab ON ab.academy_id = pb.primary_academy_id
                WHERE efs.event_id = %s
                ORDER BY efs.round_number, efs.wave_number, CASE WHEN efs.player_b_id IS NULL THEN 1 ELSE 0 END, efs.table_number
                """,
                (event_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]

    total_rounds = max((r["round_number"] for r in rows), default=0)
    cross_count = sum(
        1 for r in rows
        if r["player_b_id"] and r["player_a_academy_id"] != r["player_b_academy_id"]
    )
    real_count = sum(1 for r in rows if r["player_b_id"])
    cross_pct = round(cross_count / real_count * 100, 1) if real_count > 0 else 0.0

    slots = [
        EventFixtureSlotResponse(
            slot_id=r["slot_id"],
            round_number=r["round_number"],
            wave_number=r["wave_number"],
            table_number=r["table_number"],
            round_intent=r["round_intent"],
            gap_band=r["gap_band"],
            player_a_role=r["player_a_role"],
            player_b_role=r["player_b_role"],
            match_category=r["match_category"],
            player_a=EventFixturePlayer(
                player_id=r["player_a_id"],
                name=r["player_a_name"],
                current_rating=float(r["player_a_rating"]),
                academy_id=r["player_a_academy_id"],
                academy_name=r["player_a_academy_name"],
            ),
            player_b=EventFixturePlayer(
                player_id=r["player_b_id"],
                name=r["player_b_name"],
                current_rating=float(r["player_b_rating"]),
                academy_id=r["player_b_academy_id"],
                academy_name=r["player_b_academy_name"],
            ) if r["player_b_id"] else None,
            expected_rating_gap=float(r["expected_rating_gap"]),
            status=r["status"],
            fixture_strategy=r["fixture_strategy"],
            match_id=r["match_id"],
        )
        for r in rows
    ]

    return EventFixturesResponse(
        event_id=event_id,
        total_rounds=total_rounds,
        total_slots=len(slots),
        cross_academy_pct=cross_pct,
        fixture_state=current_fixture_state,
        slots=slots,
    )


@router.get("/{event_id}/fixtures/status")
def get_fixture_status(event_id: str, _: dict = _ANY):
    """Return current fixture_state and whether regeneration is allowed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fixture_state FROM event WHERE event_id = %s",
                (event_id,),
            )
            ev = cur.fetchone()
            if not ev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            fs = ev["fixture_state"]

            can_regenerate = fs in ("ROSTER_OPEN", "FIXTURES_READY")
            reason = None
            if fs == "FIXTURE_FROZEN":
                reason = "Fixtures are frozen. Unlock to allow regeneration."
            elif fs == "RESULTS_SUBMITTED":
                reason = "All results submitted — apply ratings to complete the event."
            elif fs == "RATINGS_APPLIED":
                reason = "Event complete — ratings have been applied."
            elif fs is None:
                reason = "Fixture lifecycle not applicable for this event type."

    return {"fixture_state": fs, "can_regenerate": can_regenerate, "reason": reason}


@router.post("/{event_id}/fixtures/lock")
def lock_fixtures(event_id: str, current_user: dict = Depends(get_current_user)):
    """Transition FIXTURES_READY → FIXTURE_FROZEN. Prevents further regeneration."""
    if current_user["role"] not in ("ADMIN", "COACH"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins and coaches only")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fixture_state, host_academy_id FROM event WHERE event_id = %s",
                (event_id,),
            )
            ev = cur.fetchone()
            if not ev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            if ev["fixture_state"] != "FIXTURES_READY":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot lock: fixture state is {ev['fixture_state']}, expected FIXTURES_READY.",
                )
            if current_user["role"] == "COACH":
                host = str(ev["host_academy_id"] or "")
                if not host or host != current_user.get("academy_id"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Only the host academy coach or an admin can lock fixtures",
                    )
            cur.execute(
                "UPDATE event SET fixture_state = 'FIXTURE_FROZEN' WHERE event_id = %s",
                (event_id,),
            )
    return {"fixture_state": "FIXTURE_FROZEN"}


@router.post("/{event_id}/apply-ratings")
def apply_event_ratings(event_id: str, current_user: dict = Depends(get_current_user)):
    """Apply Elo ratings for all confirmed matches in a FIXTURE_FROZEN LEAGUE event."""
    if current_user["role"] not in ("ADMIN", "COACH"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins and coaches only")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fixture_state, scheduling_mode, event_type FROM event WHERE event_id = %s",
                (event_id,),
            )
            ev = cur.fetchone()
            if not ev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            if ev["fixture_state"] not in ("FIXTURE_FROZEN", "RESULTS_SUBMITTED"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot apply ratings: fixture state is {ev['fixture_state']}. "
                           "Fixtures must be locked (FIXTURE_FROZEN or RESULTS_SUBMITTED) before applying ratings.",
                )

            # Ensure all fixture slots are resolved (none still SCHEDULED)
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM event_fixture_slot WHERE event_id = %s AND status = 'SCHEDULED'",
                (event_id,),
            )
            scheduled = cur.fetchone()["cnt"]
            if scheduled > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot apply ratings: {scheduled} fixture slot(s) still have no result. "
                           "Enter all match results first.",
                )

            # Auto-confirm any PENDING matches for this event — the admin "Apply Ratings"
            # action is the authoritative sign-off for inter-academy league events, so
            # matches that were submitted but not yet individually confirmed by the opponent
            # are auto-confirmed here before rating calculation.
            cur.execute(
                """
                UPDATE match
                SET confirmation_status = 'AUTO_CONFIRMED',
                    confirmed_by = %s,
                    confirmed_at = NOW()
                WHERE event_id = %s
                  AND confirmation_status = 'PENDING'
                  AND rating_eligible = TRUE
                """,
                (current_user["user_id"], event_id),
            )

            cur.execute(
                """
                SELECT match_id FROM match
                WHERE event_id = %s
                  AND rating_eligible = TRUE
                  AND ratings_applied_at IS NULL
                  AND confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')
                """,
                (event_id,),
            )
            eligible_ids = [str(r["match_id"]) for r in cur.fetchall()]

        if eligible_ids:
            tier_changes = apply_ratings_batch(conn, eligible_ids)
            for tc in tier_changes:
                fire("player.tier_changed", tc)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE event SET fixture_state = 'RATINGS_APPLIED' WHERE event_id = %s",
                (event_id,),
            )

    return {"fixture_state": "RATINGS_APPLIED", "matches_processed": len(eligible_ids)}


def _build_slot_responses(
    slot_rows: list[dict],
    players_by_id: dict,
) -> list[EventFixtureSlotResponse]:
    result = []
    for sr in slot_rows:
        pa = players_by_id.get(sr["player_a_id"])
        pb = players_by_id.get(sr["player_b_id"]) if sr["player_b_id"] else None
        result.append(
            EventFixtureSlotResponse(
                slot_id=sr["slot_id"],
                round_number=sr["round_number"],
                wave_number=sr["wave_number"],
                table_number=sr["table_number"],
                round_intent=sr["round_intent"],
                gap_band=sr["gap_band"],
                player_a_role=sr["player_a_role"],
                player_b_role=sr["player_b_role"],
                match_category=sr["match_category"],
                player_a=EventFixturePlayer(
                    player_id=pa["player_id"],
                    name=pa["name"],
                    current_rating=float(pa["current_rating"]),
                    academy_id=pa["academy_id"],
                    academy_name=pa["academy_name"],
                ),
                player_b=EventFixturePlayer(
                    player_id=pb["player_id"],
                    name=pb["name"],
                    current_rating=float(pb["current_rating"]),
                    academy_id=pb["academy_id"],
                    academy_name=pb["academy_name"],
                ) if pb else None,
                expected_rating_gap=float(sr["expected_rating_gap"]),
                status=sr["status"],
                fixture_strategy=sr["fixture_strategy"],
                match_id=sr.get("match_id"),
            )
        )
    return result
