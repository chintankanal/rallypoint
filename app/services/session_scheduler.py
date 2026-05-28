"""
session_scheduler — wave + table assignment for a list of round pairings.

Per docs/fixture_engine_phased_impl_plan.md Phase 3, the fixture engine
produces pure pairings; this module converts those pairings into executable
(wave_number, table_number) assignments respecting physical table capacity.

A "wave" is one concurrent block of matches. If a round contains more pairs
than there are tables, the pairs are split across multiple sequential waves.
For two-wave rounds the legacy display label `sub_round` is "A" / "B"; for
three or more waves the sub_round display falls back to None and consumers
should use `wave_number` directly.

The module is pure Python with zero DB access, mirroring fixture_engine.py.
"""
from typing import Optional


def derive_sub_round_label(wave_number: int, total_waves: int) -> Optional[str]:
    """
    Legacy display label per critique §11. Two-wave rounds map to A/B for
    operator familiarity; three or more waves drop the label so the UI is
    forced to render the numeric wave_number explicitly.
    """
    if total_waves <= 1:
        return None
    if total_waves == 2:
        return "A" if wave_number == 1 else "B"
    return None


def schedule_round(
    pairs: list[tuple],
    num_tables: int,
    pair_to_slot: callable,
) -> list[dict]:
    """
    Assign `pairs` to (wave_number, table_number) slots respecting `num_tables`.

    pair_to_slot is a callable
        (pid_a, pid_b | None, wave_number, table_number, sub_round) -> slot dict
    that the fixture engine provides; it owns the slot construction (intent,
    roles, gap_band, etc.). This module only owns the wave/table mapping.

    Returns the assembled slot list. Empty `pairs` returns [].
    """
    if not pairs:
        return []
    if num_tables < 1:
        raise ValueError(f"num_tables must be >= 1, got {num_tables}")

    # Wave count = ceil(len(pairs) / num_tables). Compute via integer math so
    # behavior is deterministic across platforms.
    total_pairs = len(pairs)
    total_waves = (total_pairs + num_tables - 1) // num_tables

    slots: list[dict] = []
    for i, pair in enumerate(pairs):
        wave_number = (i // num_tables) + 1
        table_number = (i % num_tables) + 1
        sub_round = derive_sub_round_label(wave_number, total_waves)
        pid_a, pid_b = pair
        slots.append(pair_to_slot(pid_a, pid_b, wave_number, table_number, sub_round))
    return slots


def schedule_event(
    pairs_by_round: list[list[tuple]],
    num_tables: int,
    pair_to_slot: callable,
) -> list[dict]:
    """
    Convenience: schedule an entire event whose pairings are already grouped by
    round. Each round is independently waved/tabled.
    """
    out: list[dict] = []
    for round_pairs in pairs_by_round:
        out.extend(schedule_round(round_pairs, num_tables, pair_to_slot))
    return out
