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

export interface SummaryStat {
  min: number
  avg: number
  max: number
}

export interface RoleExposureSummary {
  noStretchExposureCount: number
  stretchingSummary: SummaryStat
  anchoringSummary: SummaryStat
  peerSummary: SummaryStat
}

export interface FixturePlayerAnalytics {
  playerId: string
  name: string
  rating: number
  tier?: string
  matches: number
  uniqueOpponents: number
  byes: number
  sos: number
  maxPlayStreak: number
  peer: number
  stretching: number
  anchoring: number
  atPoolCeiling: boolean
}

export type Verdict = 'optimal' | 'good' | 'limited'

export interface QualityDimension {
  key: string
  label: string
  achieved: string
  ratio: number
  verdict: Verdict
  limitedBy?: string
}

export interface Constraints {
  playerCount: number
  parityForcesBye: boolean
  rawSpread: number | null
  coreSpread: number | null
  tierDistribution: Record<string, number>
  provisionalCount: number | null
  rounds: number
  numTables?: number
  regime: string | null
  competitiveMaxGap: number | null
  stretchMaxGap: number | null
}

export interface QualityReport {
  dimensions: QualityDimension[]
  overallScore: number
  overallLabel: 'Strong' | 'Good' | 'Fair' | 'Constrained'
}

export interface FixtureAnalytics {
  totalSlots: number
  counts: Record<FixtureCategory, number>
  percentages: Record<'competitive' | 'stretch' | 'anchor' | 'developmental' | 'outOfBand' | 'bye', number>
  density: number
  tightnessScore: number
  byeBalanced: boolean
  outOfBandCount: number
  byeCount: number
  diagnostics?: SessionDiagnostics
  bootstrapPhase: string
  regime: string | null
  fairnessIndex: number
  sosSpread: number
  criticalTraps: number
  warningTraps: number
  matchesSummary: SummaryStat
  uniqueOpponentsSummary: SummaryStat
  byesSummary: SummaryStat
  roleExposureSummary: RoleExposureSummary
  perPlayer: FixturePlayerAnalytics[]
  constraints: Constraints
  quality: QualityReport
  narrative: string
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

function clampPercentage(value: number) {
  return Math.round(Math.min(100, Math.max(0, value)))
}

function summaryStat(values: number[]): SummaryStat {
  if (!values.length) return { min: 0, avg: 0, max: 0 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length
  return { min, max, avg: Math.round(avg * 10) / 10 }
}

function normalizeRole(role?: string | null) {
  const value = (role ?? '').trim().toUpperCase()
  if (value === 'PEER') return 'PEER'
  if (value.includes('STRETCH')) return 'STRETCHING'
  if (value.includes('ANCHOR')) return 'ANCHORING'
  return 'PEER'
}

function getNextChronoPhase(phase: { round_number: number; wave_number: number }, maxWave: number) {
  if (phase.wave_number < maxWave) {
    return { round_number: phase.round_number, wave_number: phase.wave_number + 1 }
  }
  return { round_number: phase.round_number + 1, wave_number: 1 }
}

export function analyzeFixtureSlots(
  slots: FixtureSlot[],
  diagnostics?: SessionDiagnostics,
  sessionContext?: { numTables?: number; sessionMinutes?: number }
): FixtureAnalytics {
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

  const maxWavePerRound: Record<number, number> = {}
  const playerStats: Record<string, {
    playerId: string
    name: string
    rating: number
    tier?: string
    matches: number
    opponents: Set<string>
    byes: number
    opponentRatings: number[]
    phases: { round_number: number; wave_number: number }[]
    peer: number
    stretching: number
    anchoring: number
  }> = {}

  const ensurePlayer = (player: FixtureSlot['player_a']) => {
    if (!playerStats[player.player_id]) {
      playerStats[player.player_id] = {
        playerId: player.player_id,
        name: player.name,
        rating: player.current_rating,
        tier: player.tier,
        matches: 0,
        opponents: new Set(),
        byes: 0,
        opponentRatings: [],
        phases: [],
        peer: 0,
        stretching: 0,
        anchoring: 0,
      }
    }
    return playerStats[player.player_id]
  }

  for (const slot of slots) {
    const category = getSlotCategory(slot)
    counts[category] = (counts[category] ?? 0) + 1

    maxWavePerRound[slot.round_number] = Math.max(maxWavePerRound[slot.round_number] ?? 0, slot.wave_number)

    const a = slot.player_a
    const aStats = ensurePlayer(a)

    const isBye = slot.status === 'BYE' || !slot.player_b
    if (isBye) {
      aStats.byes += 1
      continue
    }

    const b = slot.player_b!
    const bStats = ensurePlayer(b)

    if (slot.player_b && slot.player_a) {
      filledCount += 1
      totalDelta += Math.abs(Math.round(a.current_rating) - Math.round(b.current_rating))
      deltasCount += 1
    }

    const phase = { round_number: slot.round_number, wave_number: slot.wave_number }
    aStats.phases.push(phase)
    bStats.phases.push(phase)

    const recordMatch = (selfStats: typeof aStats, opponent: FixtureSlot['player_a'], roleValue?: string) => {
      selfStats.matches += 1
      selfStats.opponents.add(opponent.player_id)
      selfStats.opponentRatings.push(opponent.current_rating)
      const role = normalizeRole(roleValue)
      if (role === 'PEER') selfStats.peer += 1
      else if (role === 'STRETCHING') selfStats.stretching += 1
      else if (role === 'ANCHORING') selfStats.anchoring += 1
    }

    recordMatch(aStats, b, slot.player_a_role)
    recordMatch(bStats, a, slot.player_b_role)
  }

  const playerIds = Object.keys(playerStats)
  const perPlayer = playerIds.map(pid => {
    const stats = playerStats[pid]
    const sos = stats.opponentRatings.length
      ? stats.opponentRatings.reduce((sum, value) => sum + value, 0) / stats.opponentRatings.length
      : 0
    const phases = stats.phases.slice().sort((a, b) =>
      a.round_number === b.round_number
        ? a.wave_number - b.wave_number
        : a.round_number - b.round_number,
    )
    let currentStreak = 0
    let maxPlayStreak = 0
    let prevPhase: { round_number: number; wave_number: number } | null = null
    for (const phase of phases) {
      if (!prevPhase) {
        currentStreak = 1
      } else {
        const nextPhase = getNextChronoPhase(prevPhase, maxWavePerRound[prevPhase.round_number] ?? phase.wave_number)
        if (phase.round_number === nextPhase.round_number && phase.wave_number === nextPhase.wave_number) {
          currentStreak += 1
        } else {
          currentStreak = 1
        }
      }
      maxPlayStreak = Math.max(maxPlayStreak, currentStreak)
      prevPhase = phase
    }

    return {
      playerId: stats.playerId,
      name: stats.name,
      rating: stats.rating,
      tier: stats.tier,
      matches: stats.matches,
      uniqueOpponents: stats.opponents.size,
      byes: stats.byes,
      sos: Math.round(sos * 10) / 10,
      maxPlayStreak,
      peer: stats.peer,
      stretching: stats.stretching,
      anchoring: stats.anchoring,
      atPoolCeiling: false, // will be computed after pool is complete
    }
  })

  const matchesSummary = summaryStat(perPlayer.map(p => p.matches))
  const uniqueOpponentsSummary = summaryStat(perPlayer.map(p => p.uniqueOpponents))
  const byesSummary = summaryStat(perPlayer.map(p => p.byes))

  // Compute atPoolCeiling for each player: true if no other player is rated high enough to be a stretch
  const maxPlayerRating = Math.max(...perPlayer.map(p => p.rating), 1000)
  const stretchThreshold = diagnostics?.competitive_max_gap ?? 150 // use existing competitive gap as proxy
  
  const perPlayerWithCeiling = perPlayer.map(player => ({
    ...player,
    atPoolCeiling: !perPlayer.some(other =>
      other.playerId !== player.playerId &&
      other.rating > player.rating + stretchThreshold
    ),
  }))

  // Intra-fairness: SoS balance + opponent variety + games equity (NO rest, NO table-rotation)
  const filterableStats = perPlayerWithCeiling.filter(p => p.matches >= 2)
  const ratingRelativeOffsets = filterableStats.map(player =>
    Math.abs(player.rating - player.sos)
  )
  const sosSpread = ratingRelativeOffsets.length ? Math.max(...ratingRelativeOffsets) : 0
  const dynamicCeiling = maxPlayerRating * 0.25
  const sosBalanceScore = Math.max(0, 100 - Math.round((sosSpread / dynamicCeiling) * 100))

  // Opponent variety: how many unique opponents each player faced / total matches
  const opponentVarietyScores = filterableStats.map(player =>
    player.matches > 0 ? (player.uniqueOpponents / player.matches) : 0
  )
  const avgOpponentVariety = opponentVarietyScores.length
    ? opponentVarietyScores.reduce((sum, score) => sum + score, 0) / opponentVarietyScores.length
    : 0
  const opponentVarietyScore = Math.round(avgOpponentVariety * 100)

  // Games equity: how evenly distributed matches are
  const matchDelta = matchesSummary.max - matchesSummary.min
  const gamesEquityScore = Math.max(0, 100 - Math.round((matchDelta / Math.max(matchesSummary.avg, 1)) * 50))

  // Fairness is weighted average: SoS (50%) + variety (30%) + games equity (20%)
  const fairnessIndex = Math.round(sosBalanceScore * 0.5 + opponentVarietyScore * 0.3 + gamesEquityScore * 0.2)

  const criticalTraps = perPlayerWithCeiling.filter(player => player.maxPlayStreak >= 3).length
  const warningTraps = perPlayerWithCeiling.filter(player => player.maxPlayStreak === 2).length

  const roleExposureSummary: RoleExposureSummary = {
    noStretchExposureCount: perPlayerWithCeiling.filter(
      player => player.stretching === 0 && !player.atPoolCeiling
    ).length,
    stretchingSummary: summaryStat(perPlayerWithCeiling.map(player => player.stretching)),
    anchoringSummary: summaryStat(perPlayerWithCeiling.map(player => player.anchoring)),
    peerSummary: summaryStat(perPlayerWithCeiling.map(player => player.peer)),
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

  const density = totalSlots ? Math.round((filledCount / totalSlots) * 100) : 0
  const tightnessScore = deltasCount ? Number((totalDelta / deltasCount).toFixed(1)) : 0
  const byeBalanced = counts.bye === 0 || counts.bye <= 1

  // ──── Constraints ────
  const playerCount = playerIds.length
  const tierDistribution: Record<string, number> = {}
  for (const player of perPlayerWithCeiling) {
    const tier = player.tier || 'Unrated'
    tierDistribution[tier] = (tierDistribution[tier] ?? 0) + 1
  }
  const rounds = Math.max(...slots.map(s => s.round_number), 0)
  const parityForcesBye = playerCount % 2 === 1

  const constraints: Constraints = {
    playerCount,
    parityForcesBye,
    rawSpread: diagnostics?.raw_spread ?? null,
    coreSpread: diagnostics?.core_spread ?? null,
    tierDistribution,
    provisionalCount: diagnostics?.provisional_count ?? null,
    rounds,
    numTables: sessionContext?.numTables,
    regime: diagnostics?.regime ?? null,
    competitiveMaxGap: diagnostics?.competitive_max_gap ?? null,
    stretchMaxGap: diagnostics?.stretch_max_gap ?? null,
  }

  // ──── Quality dimensions (ratios benchmarked against achievable) ────
  const eligibleForStretch = perPlayerWithCeiling.filter(p => !p.atPoolCeiling).length
  const achievedStretchCount = perPlayerWithCeiling.filter(p => p.stretching > 0).length
  const stretchReachRatio = eligibleForStretch > 0 ? achievedStretchCount / eligibleForStretch : 1.0
  const stretchReachVerdict: Verdict = stretchReachRatio >= 0.9 ? 'optimal' : stretchReachRatio >= 0.7 ? 'good' : 'limited'
  const stretchReachLimitedBy = stretchReachRatio < 0.9 ? 'few higher-rated opponents in pool' : undefined

  const competitiveTarget = diagnostics?.competitive_max_gap ?? 150
  const filledSlots = Math.max(0, totalSlots - counts.bye)
  const outOfBandFraction = filledSlots > 0 ? counts.outOfBand / filledSlots : 0
  const competitiveRatio = Math.max(0, Math.min(1, 1 - outOfBandFraction))
  const competitiveVerdict: Verdict = competitiveRatio >= 0.85 ? 'optimal' : competitiveRatio >= 0.65 ? 'good' : 'limited'
  const competitiveLimitedBy = competitiveVerdict === 'limited'
    ? 'wide rating spread forced some out-of-band pairings'
    : undefined

  const varietyDenominator = rounds > 0 ? Math.min(rounds, Math.max(0, playerCount - 1)) : 1
  const opponentVarietyRatio = rounds > 0 ? Math.min(1, uniqueOpponentsSummary.avg / Math.max(1, varietyDenominator)) : 1.0
  const varietyVerdict: Verdict = opponentVarietyRatio >= 0.8 ? 'optimal' : opponentVarietyRatio >= 0.6 ? 'good' : 'limited'
  const varietyLimitedBy = varietyVerdict === 'limited'
    ? 'small pool forces rematches across rounds'
    : undefined

  const gameEquityRatio = matchesSummary.max > 0 ? matchesSummary.min / matchesSummary.max : 1.0
  const equityVerdict: Verdict = gameEquityRatio >= 0.85 ? 'optimal' : gameEquityRatio >= 0.7 ? 'good' : 'limited'
  const equityLimitedBy = equityVerdict === 'limited'
    ? 'table/round capacity yields uneven match counts'
    : undefined

  const unavoidableByes = parityForcesBye ? rounds : 0
  const byesRatio = counts.bye <= unavoidableByes ? 1.0 : (unavoidableByes / counts.bye)
  const byesVerdict: Verdict = counts.bye === unavoidableByes ? 'optimal' : counts.bye <= unavoidableByes + 1 ? 'good' : 'limited'
  const byesLimitedBy = counts.bye > unavoidableByes ? 'odd player count' : undefined

  const dimensions: QualityDimension[] = [
    {
      key: 'competitive-balance',
      label: 'Competitive balance',
      achieved: `${counts.outOfBand} out-of-band (${tightnessScore} avg gap, target ≤${competitiveTarget})`,
      ratio: Math.max(0, Math.min(1, competitiveRatio)),
      verdict: competitiveVerdict,
      limitedBy: competitiveLimitedBy,
    },
    {
      key: 'opponent-variety',
      label: 'Opponent variety',
      achieved: `${uniqueOpponentsSummary.avg.toFixed(1)} unique per player`,
      ratio: Math.max(0, Math.min(1, opponentVarietyRatio)),
      verdict: varietyVerdict,
      limitedBy: varietyLimitedBy,
    },
    {
      key: 'game-equity',
      label: 'Game equity',
      achieved: `${gameEquityRatio.toFixed(2)} ratio (min/max)`,
      ratio: Math.max(0, Math.min(1, gameEquityRatio)),
      verdict: equityVerdict,
      limitedBy: equityLimitedBy,
    },
    {
      key: 'rest-distribution',
      label: 'Rest distribution',
      achieved: `${counts.bye} bye${counts.bye !== 1 ? 's' : ''}${unavoidableByes > 0 ? ` (${unavoidableByes} unavoidable)` : ''}`,
      ratio: Math.max(0, Math.min(1, byesRatio)),
      verdict: byesVerdict,
      limitedBy: byesLimitedBy,
    },
    {
      key: 'stretch-reach',
      label: 'Stretch reach',
      achieved: `${achievedStretchCount} of ${eligibleForStretch} players`,
      ratio: Math.max(0, Math.min(1, stretchReachRatio)),
      verdict: stretchReachVerdict,
      limitedBy: stretchReachLimitedBy,
    },
  ]

  const ratios = dimensions.map(d => d.ratio)
  const overallScore = ratios.length > 0 ? Math.round((ratios.reduce((sum, r) => sum + r, 0) / ratios.length) * 100) : 50
  const overallLabel: 'Strong' | 'Good' | 'Fair' | 'Constrained' =
    overallScore >= 90 ? 'Strong' : overallScore >= 75 ? 'Good' : overallScore >= 50 ? 'Fair' : 'Constrained'

  const quality: QualityReport = {
    dimensions,
    overallScore,
    overallLabel,
  }

  // ──── Narrative ────
  const strengths: string[] = []
  if (competitiveVerdict === 'optimal') strengths.push('excellent competitive balance')
  if (varietyVerdict === 'optimal') strengths.push('strong opponent variety')
  if (equityVerdict === 'optimal') strengths.push('strong game equity')
  if (byesVerdict === 'optimal') strengths.push('balanced rest distribution')

  const limitedDimensions = dimensions.filter(d => d.verdict === 'limited')
  const limitingDim = limitedDimensions
    .filter(d => d.limitedBy)
    .sort((a, b) => a.ratio - b.ratio)[0]
    ?? limitedDimensions[0]
  const limitingConstraint = limitingDim?.limitedBy ?? null

  let narrativeText = `Fixture quality is **${overallLabel}**. `
  if (strengths.length > 0) {
    narrativeText += `Highlights: ${strengths.join(', ')}. `
  }
  if (limitedDimensions.length > 0) {
    const limitedNames = limitedDimensions.map(d => d.label.toLowerCase()).join(', ')
    if (limitingConstraint) {
      narrativeText += `Limited by **${limitingConstraint}**: ${limitedNames} affected.`
    } else {
      narrativeText += `Limited: ${limitedNames} affected.`
    }
  } else {
    narrativeText += 'Excellent fixture quality across all dimensions.'
  }
  const narrative = narrativeText

  return {
    totalSlots,
    counts,
    percentages,
    density,
    tightnessScore,
    byeBalanced,
    outOfBandCount: counts.outOfBand,
    byeCount: counts.bye,
    diagnostics,
    bootstrapPhase: diagnostics?.bootstrap_phase ?? 'STANDARD',
    regime: diagnostics?.regime ?? null,
    fairnessIndex,
    sosSpread: Math.round(sosSpread * 10) / 10,
    criticalTraps,
    warningTraps,
    matchesSummary,
    uniqueOpponentsSummary,
    byesSummary,
    roleExposureSummary,
    perPlayer: [...perPlayerWithCeiling].sort((a, b) => b.rating - a.rating),
    constraints,
    quality,
    narrative,
  }
}

