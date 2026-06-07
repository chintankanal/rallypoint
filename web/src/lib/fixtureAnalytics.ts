import { classifyCell } from './fixtures'
import type { FixtureSlot } from '../api/client'
import type { SessionDiagnostics } from '../api/client'

export type FixtureCategory =
  | 'competitive'
  | 'stretch'
  | 'anchor'
  | 'developmental'
  | 'outOfBand'
  | 'bye'
  | 'unknown'

export interface FixtureAnalytics {
  totalSlots: number
  counts: Record<FixtureCategory, number>
  percentages: Record<'competitive' | 'stretch' | 'anchor' | 'developmental' | 'outOfBand' | 'bye', number>
  density: number
  tightnessScore: number
  byeBalanced: boolean
  outOfBandCount: number
  byeCount: number
  rematchRate: number
  diagnostics?: SessionDiagnostics
  bootstrapPhase: string
  regime: string | null
}

const CATEGORY_MAP: Record<string, FixtureCategory> = {
  competitive: 'competitive',
  stretch: 'stretch',
  anchor: 'anchor',
  developmental: 'developmental',
  outOfBand: 'outOfBand',
  bye: 'bye',
  unknown: 'unknown',
}

function getSlotCategory(slot: FixtureSlot): FixtureCategory {
  if (!slot.player_b) return 'bye'
  const meta = classifyCell(slot as any, slot.player_a as any, slot.player_b as any)
  return CATEGORY_MAP[meta.category] ?? 'unknown'
}

function getPairingKey(slot: FixtureSlot) {
  if (!slot.player_a || !slot.player_b) return null
  const ids = [slot.player_a.player_id, slot.player_b.player_id].sort()
  return ids.join('|')
}

function clampPercentage(value: number) {
  return Math.round(Math.min(100, Math.max(0, value)))
}

export function analyzeFixtureSlots(slots: FixtureSlot[], diagnostics?: SessionDiagnostics): FixtureAnalytics {
  const counts: Record<FixtureCategory, number> = {
    competitive: 0,
    stretch: 0,
    anchor: 0,
    developmental: 0,
    outOfBand: 0,
    bye: 0,
    unknown: 0,
  }

  let filledCount = 0
  let totalDelta = 0
  let deltasCount = 0
  const pairingCounts: Record<string, number> = {}

  for (const slot of slots) {
    const category = getSlotCategory(slot)
    counts[category] = (counts[category] ?? 0) + 1

    if (slot.player_b && slot.player_a) {
      filledCount += 1
      pairingCounts[getPairingKey(slot)!] = (pairingCounts[getPairingKey(slot)!] ?? 0) + 1
      totalDelta += Math.abs(Math.round(slot.player_a.current_rating) - Math.round(slot.player_b.current_rating))
      deltasCount += 1
    }
  }

  const totalSlots = slots.length
  const asPercent = (value: number) => (totalSlots ? clampPercentage((value / totalSlots) * 100) : 0)
  const percentages = {
    competitive: asPercent(counts.competitive),
    stretch: asPercent(counts.stretch),
    anchor: asPercent(counts.anchor),
    developmental: asPercent(counts.developmental),
    outOfBand: asPercent(counts.outOfBand),
    bye: asPercent(counts.bye),
  }

  const rematchCount = Object.values(pairingCounts).filter(count => count > 1).length
  const rematchRate = filledCount > 0 ? Math.round((rematchCount / filledCount) * 100) : 0
  const density = totalSlots ? Math.round((filledCount / totalSlots) * 100) : 0
  const tightnessScore = deltasCount ? Number((totalDelta / deltasCount).toFixed(1)) : 0
  const byeBalanced = counts.bye === 0 || counts.bye <= 1

  return {
    totalSlots,
    counts,
    percentages,
    density,
    tightnessScore,
    byeBalanced,
    outOfBandCount: counts.outOfBand,
    byeCount: counts.bye,
    rematchRate,
    diagnostics,
    bootstrapPhase: diagnostics?.bootstrap_phase ?? 'STANDARD',
    regime: diagnostics?.regime ?? null,
  }
}
