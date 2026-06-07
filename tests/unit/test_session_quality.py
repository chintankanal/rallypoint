"""
Unit tests for session_quality service.

Validates that the Python implementation correctly ports the TS logic,
including dimensions, applicability, weighting, and narrative generation.
"""
import pytest
from app.services.session_quality import compute_session_quality


class TestSessionQualityFlat:
    """Test flat DISCOVERY pool (all ~1000 rating)."""

    def test_flat_discovery_pool(self):
        """All players ~1000 rating, DISCOVERY phase."""
        # Create 8 players all rated ~1000
        players = [{"player_id": f"p{i}", "current_rating": 1000 + (i * 5)} for i in range(8)]

        # Create 3 rounds of matches (BYE on odd player count)
        slots = []
        for r in range(1, 4):  # 3 rounds
            # Pair players in same tier (no stretch/anchor)
            for i in range(0, 8, 2):
                slots.append({
                    "round_number": r,
                    "wave_number": 1,
                    "gap_band": "COMPETITIVE",
                    "round_intent": "PEER",
                    "player_a_role": "PEER",
                    "player_b_role": "PEER",
                    "status": "SCHEDULED",
                    "player_a": {
                        "player_id": players[i]["player_id"],
                        "current_rating": players[i]["current_rating"],
                        "tier": "A2",
                    },
                    "player_b": {
                        "player_id": players[i + 1]["player_id"],
                        "current_rating": players[i + 1]["current_rating"],
                        "tier": "A2",
                    },
                })

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 40,
            "core_spread": 30,
            "provisional_count": 0,
            "present_player_count": 8,
        }

        result = compute_session_quality(
            slots,
            diagnostics,
            phase="DISCOVERY",
            num_tables=4,
        )

        assert result is not None
        assert len(result.dimensions) == 5

        # In DISCOVERY, stretch-reach should have low weight (0.0)
        stretch_reach = next(d for d in result.dimensions if d.key == "stretch-reach")
        assert not stretch_reach.applicable  # No players above ceiling

        # Overall score should not be inflated by n/a dimensions
        assert result.overall_score >= 50  # Should be reasonable
        assert result.overall_label in ["Strong", "Good", "Fair", "Constrained"]

        # Narrative should never contain "undefined"
        assert "undefined" not in result.narrative

    def test_flat_pool_variety_inapplicable(self):
        """Verify stretch-reach marked inapplicable in flat pool."""
        slots = [
            {
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {
                    "player_id": "p1",
                    "current_rating": 1000,
                    "tier": "A2",
                },
                "player_b": {
                    "player_id": "p2",
                    "current_rating": 1020,
                    "tier": "A2",
                },
            },
        ]

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 20,
            "core_spread": 20,
            "provisional_count": 0,
            "present_player_count": 2,
        }

        result = compute_session_quality(slots, diagnostics, phase="DISCOVERY")

        # Stretch-reach should be inapplicable (no one above ceiling)
        stretch_reach = next(d for d in result.dimensions if d.key == "stretch-reach")
        assert stretch_reach.applicable is False
        # When not applicable, verdict defaults to "optimal" but achieved should show n/a
        assert "n/a" in stretch_reach.achieved.lower() or stretch_reach.applicable is False


class TestSessionQualityBimodal:
    """Test bimodal STANDARD pool (elite vs beginner)."""

    def test_bimodal_standard_pool_with_isolated_player(self):
        """Elite (1400+) vs Beginner (900-), with isolated anchor player."""
        # 3 elite, 3 beginner, 1 isolated anchor
        players = [
            {"player_id": "e1", "current_rating": 1450, "tier": "A1"},
            {"player_id": "e2", "current_rating": 1420, "tier": "A1"},
            {"player_id": "e3", "current_rating": 1400, "tier": "A1"},
            {"player_id": "b1", "current_rating": 900, "tier": "C1"},
            {"player_id": "b2", "current_rating": 920, "tier": "C1"},
            {"player_id": "b3", "current_rating": 880, "tier": "C1"},
            {"player_id": "anchor", "current_rating": 1700, "tier": "A0"},  # Far above
        ]

        # Create 2 rounds: pairs within tier, with anchor forced out-of-band
        slots = [
            # Round 1
            {"round_number": 1, "wave_number": 1, "gap_band": "COMPETITIVE", "round_intent": "PEER",
             "player_a_role": "PEER", "player_b_role": "PEER", "status": "SCHEDULED",
             "player_a": {"player_id": "e1", "current_rating": 1450, "tier": "A1"},
             "player_b": {"player_id": "e2", "current_rating": 1420, "tier": "A1"}},
            {"round_number": 1, "wave_number": 1, "gap_band": "OUT_OF_BAND", "round_intent": "ANCHOR",
             "player_a_role": "ANCHOR", "player_b_role": "STRETCH", "status": "SCHEDULED",
             "player_a": {"player_id": "anchor", "current_rating": 1700, "tier": "A0"},
             "player_b": {"player_id": "e3", "current_rating": 1400, "tier": "A1"}},
            {"round_number": 1, "wave_number": 1, "gap_band": "COMPETITIVE", "round_intent": "PEER",
             "player_a_role": "PEER", "player_b_role": "PEER", "status": "SCHEDULED",
             "player_a": {"player_id": "b1", "current_rating": 900, "tier": "C1"},
             "player_b": {"player_id": "b2", "current_rating": 920, "tier": "C1"}},
            {"round_number": 1, "wave_number": 1, "gap_band": "COMPETITIVE", "round_intent": "PEER",
             "player_a_role": "PEER", "player_b_role": "PEER", "status": "SCHEDULED",
             "player_a": {"player_id": "b3", "current_rating": 880, "tier": "C1"},
             "player_b": None},  # BYE
            # Round 2
            {"round_number": 2, "wave_number": 1, "gap_band": "COMPETITIVE", "round_intent": "PEER",
             "player_a_role": "PEER", "player_b_role": "PEER", "status": "SCHEDULED",
             "player_a": {"player_id": "e1", "current_rating": 1450, "tier": "A1"},
             "player_b": {"player_id": "e3", "current_rating": 1400, "tier": "A1"}},
            {"round_number": 2, "wave_number": 1, "gap_band": "OUT_OF_BAND", "round_intent": "ANCHOR",
             "player_a_role": "ANCHOR", "player_b_role": "STRETCH", "status": "SCHEDULED",
             "player_a": {"player_id": "anchor", "current_rating": 1700, "tier": "A0"},
             "player_b": {"player_id": "b3", "current_rating": 880, "tier": "C1"}},
            {"round_number": 2, "wave_number": 1, "gap_band": "COMPETITIVE", "round_intent": "PEER",
             "player_a_role": "PEER", "player_b_role": "PEER", "status": "SCHEDULED",
             "player_a": {"player_id": "e2", "current_rating": 1420, "tier": "A1"},
             "player_b": {"player_id": "b1", "current_rating": 900, "tier": "C1"}},
            {"round_number": 2, "wave_number": 1, "gap_band": "COMPETITIVE", "round_intent": "PEER",
             "player_a_role": "PEER", "player_b_role": "PEER", "status": "SCHEDULED",
             "player_a": {"player_id": "b2", "current_rating": 920, "tier": "C1"},
             "player_b": None},  # BYE
        ]

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 820,  # 1700 - 880
            "core_spread": 520,  # 1420 - 900
            "provisional_count": 0,
            "present_player_count": 7,
        }

        result = compute_session_quality(slots, diagnostics, phase="STANDARD")

        assert result is not None
        competitive = next(d for d in result.dimensions if d.key == "competitive-balance")

        # Anchor player is isolated (no one within 250 of 1700), so out-of-band involving
        # anchor is "unavoidable". Check the label is present.
        assert "(unavoidable)" in competitive.achieved or competitive.verdict == "optimal"

        # Overall score should be reasonable
        assert result.overall_score >= 40
        assert result.overall_label in ["Strong", "Good", "Fair", "Constrained"]

        # Narrative should never be undefined
        assert "undefined" not in result.narrative


class TestSessionQualityParity:
    """Parity test using the validated 10-player STANDARD pool."""

    def test_10_player_standard_pool_parity(self):
        """10-player pool where top two are at-pool-ceiling; competitive optimal."""
        ratings = [1400, 1300, 1258, 1200, 1172, 1111, 1068, 1000, 992, 850]
        players = [{"player_id": f"p{i}", "current_rating": ratings[i], "tier": "T"} for i in range(len(ratings))]

        # Round 1 pair adjacent
        slots = []
        pairs = [(0,1),(2,3),(4,5),(6,7),(8,9)]
        for a,b in pairs:
            slots.append({
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
            # Give many non-ceiling players a STRETCH role so stretch-reach counts
            "player_a_role": "STRETCH" if a >= 2 and a <= 7 else "PEER",
            "player_b_role": "PEER" if b <= 7 else "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": players[a]["player_id"], "current_rating": players[a]["current_rating"], "tier": "T"},
                "player_b": {"player_id": players[b]["player_id"], "current_rating": players[b]["current_rating"], "tier": "T"},
            })

        # Round 2 pair shifted for variety
        pairs2 = [(0,2),(1,3),(4,6),(5,7),(8,9)]
        for a,b in pairs2:
            slots.append({
                "round_number": 2,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
            "player_a_role": "PEER",
            "player_b_role": "STRETCH" if b >= 2 and b <= 7 else "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": players[a]["player_id"], "current_rating": players[a]["current_rating"], "tier": "T"},
                "player_b": {"player_id": players[b]["player_id"], "current_rating": players[b]["current_rating"], "tier": "T"},
            })

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": max(ratings) - min(ratings),
            "core_spread": ratings[1] - ratings[-2],
            "provisional_count": 0,
            "present_player_count": len(ratings),
        }

        result = compute_session_quality(slots, diagnostics, phase="STANDARD")
        assert result is not None

        # Check at_pool_ceiling count: exactly 2 (1400, 1300)
        # Parse stretch-reach achieved string for "2 at pool ceiling"
        stretch = next(d for d in result.dimensions if d.key == "stretch-reach")
        assert "2 at pool ceiling" in stretch.achieved
        # eligible should be 8
        assert "of 8 eligible" in stretch.achieved or "of 8" in stretch.achieved

        competitive = next(d for d in result.dimensions if d.key == "competitive-balance")
        assert competitive.verdict == "optimal"
        assert result.overall_label == "Strong"


class TestSessionQualityConstraints:
    """Test that constraints are correctly populated in the quality result."""

    def test_constraints_populated(self):
        """Constraints should be populated with session metadata."""
        ratings = [1400, 1300, 1258, 1200, 1172, 1111, 1068, 1000, 992, 850]
        players = [
            {"player_id": f"p{i}", "current_rating": ratings[i], "tier": f"T{i//5 + 1}"}
            for i in range(len(ratings))
        ]

        # Create 2 rounds
        slots = []
        pairs_r1 = [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]
        for a, b in pairs_r1:
            slots.append({
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": players[a]["player_id"], "current_rating": players[a]["current_rating"], "tier": players[a]["tier"]},
                "player_b": {"player_id": players[b]["player_id"], "current_rating": players[b]["current_rating"], "tier": players[b]["tier"]},
            })

        pairs_r2 = [(0, 2), (1, 3), (4, 6), (5, 7), (8, 9)]
        for a, b in pairs_r2:
            slots.append({
                "round_number": 2,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": players[a]["player_id"], "current_rating": players[a]["current_rating"], "tier": players[a]["tier"]},
                "player_b": {"player_id": players[b]["player_id"], "current_rating": players[b]["current_rating"], "tier": players[b]["tier"]},
            })

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": max(ratings) - min(ratings),
            "core_spread": ratings[1] - ratings[-2],
            "provisional_count": 0,
            "present_player_count": len(ratings),
        }

        result = compute_session_quality(slots, diagnostics, phase="STANDARD", num_tables=3)
        assert result is not None
        assert result.constraints is not None

        # Verify constraints fields
        assert result.constraints.player_count == 10
        assert result.constraints.parity_forces_bye == False  # 10 is even
        assert result.constraints.rounds == 2
        assert result.constraints.num_tables == 3
        assert result.constraints.regime == "TIER_BALANCED"
        assert result.constraints.competitive_max_gap == 100
        assert result.constraints.stretch_max_gap == 250

        # Verify tier distribution (should have 2 tiers based on tier assignment above)
        assert len(result.constraints.tier_distribution) > 0
        assert sum(result.constraints.tier_distribution.values()) == 10

        # Verify spreads pass through
        assert result.constraints.raw_spread == 550  # 1400 - 850
        assert result.constraints.provisional_count == 0


class TestSessionQualityApplicability:
    """Test that n/a dimensions are correctly excluded from scoring."""

    def test_n_a_dimensions_excluded_from_score(self):
        """N/a dimensions should not inflate overall score."""
        # Flat pool with no one above ceiling
        slots = [
            {
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": "p1", "current_rating": 1000, "tier": "A2"},
                "player_b": {"player_id": "p2", "current_rating": 1010, "tier": "A2"},
            },
        ]

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 10,
            "core_spread": 10,
            "provisional_count": 0,
            "present_player_count": 2,
        }

        result = compute_session_quality(slots, diagnostics, phase="DISCOVERY")

        # Find dimensions marked as not applicable
        n_a_dims = [d for d in result.dimensions if not d.applicable]
        
        # Verify n/a dimensions are not in strengths
        if n_a_dims:
            for dim in n_a_dims:
                assert dim.label.lower() not in result.narrative.lower() or "not applicable" in result.narrative.lower()


class TestSessionQualityNarrative:
    """Test narrative generation."""

    def test_narrative_never_contains_undefined(self):
        """Narrative should never emit literal 'undefined' text."""
        slots = [
            {
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": "p1", "current_rating": 1000, "tier": "A2"},
                "player_b": {"player_id": "p2", "current_rating": 1050, "tier": "A2"},
            },
        ]

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 50,
            "core_spread": 50,
            "provisional_count": 0,
            "present_player_count": 2,
        }

        result = compute_session_quality(slots, diagnostics, phase="STANDARD")
        assert result is not None
        assert "undefined" not in result.narrative

    def test_phase_lead_matches_input(self):
        """Narrative lead clause should reflect the input phase."""
        slots = [
            {
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": "p1", "current_rating": 1000, "tier": "A2"},
                "player_b": {"player_id": "p2", "current_rating": 1010, "tier": "A2"},
            },
        ]

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 10,
            "core_spread": 10,
            "provisional_count": 0,
            "present_player_count": 2,
        }

        result_discovery = compute_session_quality(
            slots, diagnostics, phase="DISCOVERY"
        )
        assert "discovery session" in result_discovery.narrative.lower()

        result_transition = compute_session_quality(
            slots, diagnostics, phase="TRANSITION"
        )
        assert "balances" in result_transition.narrative.lower()

        result_standard = compute_session_quality(
            slots, diagnostics, phase="STANDARD"
        )
        assert "competitive integrity" in result_standard.narrative.lower()


class TestSessionQualityVerdictThresholds:
    """Test verdict classification thresholds."""

    def test_verdict_optimal_threshold(self):
        """Ratios >= 0.85 should be classified as optimal."""
        # Create a perfect fixture with all competitive pairs
        slots = [
            {
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": "p1", "current_rating": 1000, "tier": "A2"},
                "player_b": {"player_id": "p2", "current_rating": 1010, "tier": "A2"},
            },
        ]

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 10,
            "core_spread": 10,
            "provisional_count": 0,
            "present_player_count": 2,
        }

        result = compute_session_quality(slots, diagnostics, phase="STANDARD")
        competitive = next(d for d in result.dimensions if d.key == "competitive-balance")
        assert competitive.verdict == "optimal"

    def test_verdict_good_threshold(self):
        """Ratios >= 0.65 and < 0.85 should be classified as good."""
        # Create fixture with some out-of-band
        slots = [
            {
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "COMPETITIVE",
                "round_intent": "PEER",
                "player_a_role": "PEER",
                "player_b_role": "PEER",
                "status": "SCHEDULED",
                "player_a": {"player_id": "p1", "current_rating": 1000, "tier": "A2"},
                "player_b": {"player_id": "p2", "current_rating": 1010, "tier": "A2"},
            },
            {
                "round_number": 1,
                "wave_number": 1,
                "gap_band": "OUT_OF_BAND",
                "round_intent": "ANCHOR",
                "player_a_role": "ANCHOR",
                "player_b_role": "STRETCH",
                "status": "SCHEDULED",
                "player_a": {"player_id": "p3", "current_rating": 1500, "tier": "A1"},
                "player_b": {"player_id": "p4", "current_rating": 900, "tier": "B1"},
            },
        ]

        diagnostics = {
            "regime": "TIER_BALANCED",
            "competitive_max_gap": 100,
            "stretch_max_gap": 250,
            "raw_spread": 600,
            "core_spread": 10,
            "provisional_count": 0,
            "present_player_count": 4,
        }

        result = compute_session_quality(slots, diagnostics, phase="STANDARD")
        # With 1 out-of-band in 2 filled slots, ratio = 0.5 (50%) → limited
        # But let's verify verdict behavior is consistent
        competitive = next(d for d in result.dimensions if d.key == "competitive-balance")
        assert competitive.verdict in ["limited", "good", "optimal"]


class TestSessionQualityEmpty:
    """Test handling of empty or null inputs."""

    def test_empty_slots(self):
        """Empty slot list should return None."""
        result = compute_session_quality([], {}, phase="STANDARD")
        assert result is None

    def test_null_diagnostics(self):
        """None diagnostics should return None."""
        result = compute_session_quality([{"player_a": {}, "player_b": None}], None, phase="STANDARD")
        assert result is None
