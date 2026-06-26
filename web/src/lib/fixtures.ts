export type MatrixPlayer = {
  player_id: string
  name: string
  current_rating: number
  tier?: string
}

export type Accent = {
  bg: string
  text: string
}

export interface MatrixCell {
  opponent: MatrixPlayer | null
  isBye: boolean
  label: string
  stripClass: string
  tooltip: string
  category: string
  match_id?: string
  slot_id?: string
  status?: string
}

export interface MatrixSection {
  id: string
  label: string
  accent: Accent
  players: MatrixPlayer[]
}

export interface MatrixModel {
  sections: MatrixSection[]
  rounds: number[]
  schedule: Record<string, Record<number, MatrixCell>>
}

export interface LegendItem {
  label: string
  bg: string
}

export type ClassifiableSlot<P extends MatrixPlayer> = {
  round_number: number
  status: string
  player_a_role?: string | null
  player_b_role?: string | null
  round_intent?: string | null
  gap_band?: string | null
  match_category?: string | null
  player_a: P
  player_b: P | null
}

export const TIER_META: Record<string, { label: string; rank: number; accent: Accent }> = {
  BEGINNER: { label: 'Beginner', rank: 1, accent: { bg: 'bg-gray-700', text: 'text-gray-100' } },
  INTERMEDIATE: { label: 'Intermediate', rank: 2, accent: { bg: 'bg-blue-700', text: 'text-blue-50' } },
  ADVANCED: { label: 'Advanced', rank: 3, accent: { bg: 'bg-emerald-700', text: 'text-emerald-50' } },
  ELITE: { label: 'Elite', rank: 4, accent: { bg: 'bg-purple-700', text: 'text-purple-50' } },
  NATIONAL_TRACK: { label: 'National Track', rank: 5, accent: { bg: 'bg-red-700', text: 'text-red-50' } },
}

export const GAP_BAND_LEGEND: LegendItem[] = [
  { label: 'Competitive', bg: 'bg-blue-500' },
  { label: 'Stretch', bg: 'bg-fuchsia-500' },
  { label: 'Anchor', bg: 'bg-amber-500' },
  { label: 'Developmental', bg: 'bg-slate-400' },
  { label: 'Out of band', bg: 'bg-red-500' },
]

export const MATCH_CAT_BADGE: Record<string, string> = {
  COMPETITIVE: 'bg-blue-500/10 text-blue-300 border-blue-500/20',
  STRETCH: 'bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/20',
  ANCHOR: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
  DEVELOPMENTAL: 'bg-slate-500/10 text-slate-300 border-slate-500/20',
  OUT_OF_BAND: 'bg-red-500/10 text-red-300 border-red-500/20',
  BYE: 'bg-gray-700/10 text-gray-300 border-gray-700/30',
  UNKNOWN: 'bg-gray-700/10 text-gray-300 border-gray-700/30',
}

function normalizeGapBand(value?: string | null) {
  return (value ?? 'COMPETITIVE').toString().trim().toUpperCase().replace(/\s+/g, '_').replace(/__+/g, '_')
}

export function getFirstName(fullName: string) {
  return fullName.trim().split(/\s+/)[0] ?? fullName
}

export function getOpponentLabel(opponent: MatrixPlayer, firstNameCounts: Record<string, number>) {
  const parts = opponent.name.trim().split(/\s+/)
  const first = parts[0]
  if ((firstNameCounts[first] ?? 0) <= 1 || parts.length < 2) return first
  const second = parts[1]
  const suffix = second.slice(0, 2)
  return `${first} ${suffix}.`
}

export function classifyCell<P extends MatrixPlayer>(slot: ClassifiableSlot<P>, self: P, opp: P | null) {
  const type = normalizeGapBand(slot.gap_band ?? slot.match_category ?? slot.round_intent)
  let label = ''
  let category = 'competitive'
  let stripClass = 'bg-gray-600'

  if (type === 'COMPETITIVE') {
    label = 'Competitive'
    category = 'competitive'
    stripClass = 'bg-blue-500'
  } else if (type === 'DEVELOPMENTAL') {
    label = 'Developmental'
    category = 'developmental'
    stripClass = 'bg-slate-400'
  } else if (type === 'OUT_OF_BAND' || type.replace(/_/g, '') === 'OUTOFBAND') {
    label = 'Out of band'
    category = 'outOfBand'
    stripClass = 'bg-red-500'
  } else if (type === 'ANCHOR') {
    label = 'Anchor'
    category = 'anchor'
    stripClass = 'bg-amber-500'
  } else if (type === 'STRETCH') {
    if (opp) {
      if (self.current_rating < opp.current_rating) {
        label = 'Stretch'
        category = 'stretch'
        stripClass = 'bg-fuchsia-500'
      } else if (self.current_rating > opp.current_rating) {
        label = 'Anchor'
        category = 'anchor'
        stripClass = 'bg-amber-500'
      } else {
        label = 'Stretch'
        category = 'stretch'
        stripClass = 'bg-fuchsia-500'
      }
    } else {
      label = 'Stretch'
      category = 'stretch'
      stripClass = 'bg-fuchsia-500'
    }
  } else {
    label = type ?? 'Unknown'
    category = 'competitive'
    stripClass = 'bg-slate-400'
  }

  const tooltip = opp ? `${opp.name} (${Math.round(opp.current_rating)}) — ${label}` : 'BYE'
  return { label, category, stripClass, tooltip }
}

export function buildMatrixModel<P extends MatrixPlayer>(
  slots: ClassifiableSlot<P>[],
  opts: {
    sectionOf: (p: P) => string
    sectionMeta: (sectionId: string, players: P[]) => { label: string; accent: Accent }
    cellOf: (slot: ClassifiableSlot<P>, self: P, opp: P | null) => { label: string; stripClass: string; category?: string; tooltip?: string }
    totalRounds?: number
    sectionSort?: (a: MatrixSection, b: MatrixSection) => number
  }
): MatrixModel {
  const schedule: Record<string, Record<number, MatrixCell>> = {}
  const playerById: Record<string, P> = {}

  for (const slot of slots) {
    const pa = slot.player_a
    const pb = slot.player_b
    playerById[pa.player_id] = pa
    if (pb) playerById[pb.player_id] = pb

    if (!schedule[pa.player_id]) schedule[pa.player_id] = {}
    const paMeta = opts.cellOf(slot, pa, pb)
    schedule[pa.player_id][slot.round_number] = {
      opponent: pb ?? null,
      isBye: !pb,
      label: paMeta.label,
      stripClass: paMeta.stripClass,
      tooltip: (paMeta as any).tooltip ?? paMeta.label,
      category: (paMeta as any).category ?? 'competitive',
      match_id: (paMeta as any).match_id,
      slot_id: (paMeta as any).slot_id,
      status: (paMeta as any).status,
    }

    if (pb) {
      if (!schedule[pb.player_id]) schedule[pb.player_id] = {}
      const pbMeta = opts.cellOf(slot, pb, pa)
      schedule[pb.player_id][slot.round_number] = {
        opponent: pa,
        isBye: false,
        label: pbMeta.label,
        stripClass: pbMeta.stripClass,
        tooltip: (pbMeta as any).tooltip ?? pbMeta.label,
        category: (pbMeta as any).category ?? 'competitive',
        match_id: (pbMeta as any).match_id,
        slot_id: (pbMeta as any).slot_id,
        status: (pbMeta as any).status,
      }
    }
  }

  // Group players into sections
  const sectionsMap: Record<string, P[]> = {}
  for (const p of Object.values(playerById)) {
    const sid = opts.sectionOf(p)
    ;(sectionsMap[sid] ??= []).push(p)
  }

  const sections: MatrixSection[] = []
  for (const sid of Object.keys(sectionsMap)) {
    const players = sectionsMap[sid]
    players.sort((a, b) => b.current_rating - a.current_rating)
    const meta = opts.sectionMeta(sid, players)
    sections.push({ id: sid, label: meta.label, accent: meta.accent, players })
  }

  if (opts.sectionSort) sections.sort(opts.sectionSort)

  let rounds: number[]
  if (opts.totalRounds !== undefined) {
    // League path: render rounds 1..totalRounds
    rounds = Array.from({ length: opts.totalRounds }, (_, i) => i + 1)
  } else {
    // Intra/session path: render only the distinct rounds actually present, sorted
    const present = [...new Set(
      Object.values(schedule).flatMap(r =>
        Object.keys(r).map(Number)
      )
    )].sort((a, b) => a - b)
    rounds = present
  }

  return { sections, rounds, schedule }
}
