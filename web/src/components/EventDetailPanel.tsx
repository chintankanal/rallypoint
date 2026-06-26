  import { useState, useEffect } from 'react'
  import { useQuery, useMutation } from '@tanstack/react-query'
  import {
    eventsApi, playersApi, matchesApi,
    type EventRoster, type EventFixtures, type EventFixtureSlot,
    type PlayerDirectoryItem, type MatchResponse,
  } from '../api/client'
  import { Spinner, ErrorMsg } from './Layout'
  import { SetPointsInput } from './SetPointsInput'
  import FixtureMatrixGrid from './FixtureMatrixGrid'
  import { buildMatrixModel, classifyCell, type MatrixCell } from '../lib/fixtures'

  type FixtureState = 'ROSTER_OPEN' | 'FIXTURES_READY' | 'FIXTURE_FROZEN' | 'RESULTS_SUBMITTED' | 'RATINGS_APPLIED' | null

  function getGapBandCategory(slot: any) {
    const raw = (slot.gap_band ?? slot.match_category ?? slot.round_intent ?? '').toString().trim().toUpperCase().replace(/\s+/g, '_')
    if (raw === 'COMPETITIVE') return 'competitive'
    if (raw === 'DEVELOPMENTAL') return 'developmental'
    if (raw === 'OUT_OF_BAND' || raw.replace(/_/g, '') === 'OUTOFBAND') return 'out_of_band'
    if (raw === 'ANCHOR') return 'anchor'
    if (raw === 'STRETCH') return 'stretch'
    return 'competitive'
  }

  function getMatchTypeMeta(slot: any) {
    try {
      const meta = classifyCell(slot as any, slot.player_a as any, slot.player_b as any)
      const label = meta.label ?? 'Match'
      const shortLabel = (label[0] ?? 'M').toUpperCase()
      const className = label === 'Competitive' ? 'text-blue-300' : label === 'Stretch' ? 'text-purple-300' : label === 'Anchor' ? 'text-amber-300' : label === 'Developmental' ? 'text-gray-400' : label === 'Out of band' ? 'text-orange-300' : 'text-gray-300'
      return { className, title: label, shortLabel }
    } catch (e) {
      return { className: 'text-gray-300', title: 'Match', shortLabel: 'M' }
    }
  }

  export const ACADEMY_PALETTE = [
    { bg: 'bg-blue-800', text: 'text-blue-100' },
    { bg: 'bg-purple-800', text: 'text-purple-100' },
    { bg: 'bg-green-800', text: 'text-green-100' },
    { bg: 'bg-amber-700', text: 'text-amber-100' },
    { bg: 'bg-red-800', text: 'text-red-100' },
    { bg: 'bg-cyan-800', text: 'text-cyan-100' },
    { bg: 'bg-pink-800', text: 'text-pink-100' },
    { bg: 'bg-indigo-800', text: 'text-indigo-100' },
  ]

  export const ACADEMY_PALETTE_EXTENDED = [
    ...ACADEMY_PALETTE,
    { bg: 'bg-blue-700', text: 'text-blue-50' },
    { bg: 'bg-purple-700', text: 'text-purple-50' },
    { bg: 'bg-green-700', text: 'text-green-50' },
    { bg: 'bg-amber-600', text: 'text-amber-50' },
    { bg: 'bg-red-700', text: 'text-red-50' },
    { bg: 'bg-cyan-700', text: 'text-cyan-50' },
    { bg: 'bg-pink-700', text: 'text-pink-50' },
    { bg: 'bg-indigo-700', text: 'text-indigo-50' },
  ]

  const MAX_SETS_MAP: Record<string, number> = { BEST_OF_1: 1, BEST_OF_3: 2, BEST_OF_5: 3, BEST_OF_7: 4 }

  const MATCH_DURATION_MIN: Record<string, number> = { BEST_OF_1: 10, BEST_OF_3: 18, BEST_OF_5: 30, BEST_OF_7: 45 }

  // Shared helpers and matrix grid are provided by web/src/lib/fixtures and FixtureMatrixGrid

  export function EventDetailPanel({ eventId, canManage }: { eventId: string; canManage: boolean }) {
    // default to fixtures view for read-only coach embeds, roster for admin managers
    const [section, setSection] = useState<'roster' | 'fixtures'>(canManage ? 'roster' : 'fixtures')
    const [roster, setRoster] = useState<EventRoster | null>(null)
    const [allPlayers, setAllPlayers] = useState<PlayerDirectoryItem[]>([])
    const [fixtures, setFixtures] = useState<EventFixtures | null>(null)
    const [rosterLoading, setRosterLoading] = useState(false)
    const [rosterError, setRosterError] = useState<string | null>(null)
    const [dirLoading, setDirLoading] = useState(false)
    const [fixturesLoading, setFixturesLoading] = useState(false)
    const [fixturesError, setFixturesError] = useState<string | null>(null)
    const [resultStatusFilter, setResultStatusFilter] = useState<'PENDING' | 'PLAYED' | 'ALL'>('PENDING')
    const [resultPlayerQuery, setResultPlayerQuery] = useState('')
    const [dirFilterAcademy, setDirFilterAcademy] = useState<string | null>(null)
    const [numTables, setNumTables] = useState(4)
    const [fixtureStrategy, setFixtureStrategy] = useState('TIER_MATCHED')
    const [fixtureState, setFixtureState] = useState<FixtureState>(null)
    const [generating, setGenerating] = useState(false)
    const [genError, setGenError] = useState<string | null>(null)
    const [confirmRegenerate, setConfirmRegenerate] = useState(false)
    const [confirmLock, setConfirmLock] = useState(false)
    const [locking, setLocking] = useState(false)
    const [lockError, setLockError] = useState<string | null>(null)
    const [applyingRatings, setApplyingRatings] = useState(false)
    const [applyError, setApplyError] = useState<string | null>(null)
    const [markingUnplayed, setMarkingUnplayed] = useState(false)
    const [resultSlot, setResultSlot] = useState<EventFixtureSlot | null>(null)

    const eventQ = useQuery({ queryKey: ['event-detail', eventId], queryFn: () => eventsApi.get(eventId) })

    useEffect(() => {
      if (eventQ.data) setFixtureState((eventQ.data.fixture_state as FixtureState) ?? null)
    }, [eventQ.data])

    const loadRoster = async () => {
      setRosterLoading(true); setRosterError(null)
      try { setRoster(await eventsApi.listPlayers(eventId)) }
      catch (e) { setRosterError((e as Error).message) }
      finally { setRosterLoading(false) }
    }

    const loadDirectory = async () => {
      setDirLoading(true)
      try { setAllPlayers((await playersApi.listAll()).items) }
      catch { /* silently ignore */ }
      finally { setDirLoading(false) }
    }

    const loadFixtures = async () => {
      setFixturesLoading(true); setFixturesError(null)
      try {
        const result = await eventsApi.getFixtures(eventId)
        setFixtures(result)
        if (result.fixture_state) setFixtureState(result.fixture_state as FixtureState)
        if (result.slots[0]?.fixture_strategy) setFixtureStrategy(result.slots[0].fixture_strategy)
      }
      catch (e) { setFixturesError((e as Error).message) }
      finally { setFixturesLoading(false) }
    }

    useEffect(() => { loadRoster(); loadDirectory() }, [eventId])
    useEffect(() => { if (section === 'fixtures') loadFixtures() }, [section, eventId])

    const registeredIds = new Set(roster?.items.map(p => p.player_id) ?? [])

    const handleAdd = async (playerId: string) => {
      try { await eventsApi.registerPlayer(eventId, playerId); await loadRoster() }
      catch (e) { setRosterError((e as Error).message) }
    }

    const handleRemove = async (playerId: string) => {
      try { await eventsApi.removePlayer(eventId, playerId); await loadRoster() }
      catch (e) { setRosterError((e as Error).message) }
    }

    const handleGenerate = async () => {
      setGenerating(true); setGenError(null); setConfirmRegenerate(false)
      try {
        const result = await eventsApi.generateFixtures(eventId, numTables, fixtureStrategy)
        setFixtures(result)
        setFixtureState(result.fixture_state as FixtureState)
        if (result.slots[0]?.fixture_strategy) setFixtureStrategy(result.slots[0].fixture_strategy)
        // after generating fixtures, show the fixtures matrix for immediate review
        setSection('fixtures')
      }
      catch (e) { setGenError((e as Error).message) }
      finally { setGenerating(false) }
    }

    const handleLock = async () => {
      setLocking(true); setLockError(null); setConfirmLock(false)
      try {
        const result = await eventsApi.lockFixtures(eventId)
        setFixtureState(result.fixture_state as FixtureState)
      }
      catch (e) { setLockError((e as Error).message) }
      finally { setLocking(false) }
    }

    const handleApplyRatings = async () => {
      setApplyingRatings(true); setApplyError(null)
      try {
        const result = await eventsApi.applyRatings(eventId)
        setFixtureState(result.fixture_state as FixtureState)
        await loadFixtures()
      }
      catch (e) { setApplyError((e as Error).message) }
      finally { setApplyingRatings(false) }
    }

    const handleMarkUnplayed = async (slot: EventFixtureSlot, unplayed: boolean) => {
      if (unplayed && !window.confirm('Mark as not played? It won\'t affect either player\'s rating.')) {
        return
      }
      setMarkingUnplayed(true)
      try {
        await eventsApi.markSlotUnplayed(eventId, slot.slot_id, unplayed)
        await loadFixtures()
      }
      catch (e) {
        setApplyError((e as Error).message)
      }
      finally {
        setMarkingUnplayed(false)
      }
    }

    // 1. Identify active academies involved in the current event roster or fixtures
    const eventAcademyIds = new Set<string>()
    const addAcademyId = (id?: string | null) => {
      if (id) eventAcademyIds.add(id)
    }

    if (roster?.items) {
      roster.items.forEach(p => addAcademyId(p.academy_id))
    }
    if (fixtures?.slots) {
      fixtures.slots.forEach(s => {
        addAcademyId(s.player_a?.academy_id)
        addAcademyId(s.player_b?.academy_id)
      })
    }

    const prioritizedIds = Array.from(eventAcademyIds).sort((a, b) => a.localeCompare(b))

    // 2. Keep the master list strictly alphabetical so UI elements/chips don't shift positions layout-wise
    const allAcademyIds = [...new Set((allPlayers || []).map(p => p.academy_id))].sort((a, b) => a.localeCompare(b))

    // Fallback wrapper if roster/fixtures load before the full global player directory does
    let missingIdsAdded = false
    prioritizedIds.forEach(id => {
      if (!allAcademyIds.includes(id)) {
        allAcademyIds.push(id)
        missingIdsAdded = true
      }
    })

    // Re-sort if any fallback IDs were appended to preserve alphabetical layout stability
    if (missingIdsAdded) {
      allAcademyIds.sort((a, b) => a.localeCompare(b))
    }

    // 3. Build a collision-free colorMap
    const colorMap: Record<string, typeof ACADEMY_PALETTE[number]> = {}
    const activePalette = ACADEMY_PALETTE_EXTENDED
    const clonePaletteEntry = (entry: typeof ACADEMY_PALETTE[number]) => ({ bg: entry.bg, text: entry.text })

    // First pass: Assign guaranteed unique colors sequentially to active participating academies
    prioritizedIds.forEach((id, i) => {
      colorMap[id] = clonePaletteEntry(activePalette[i] ?? ACADEMY_PALETTE[0])
    })

    // Second pass: Assign stable fallback colors to the remaining inactive directory academies
    allAcademyIds.forEach((id) => {
      if (!(id in colorMap)) {
        const globalIndex = allAcademyIds.indexOf(id)
        colorMap[id] = clonePaletteEntry(ACADEMY_PALETTE[globalIndex % ACADEMY_PALETTE.length] ?? ACADEMY_PALETTE[0])
      }
    })

    // Group directory by academy
    const dirByAcademy: Record<string, PlayerDirectoryItem[]> = {}
    for (const p of allPlayers) (dirByAcademy[p.academy_id] ??= []).push(p)
    const visibleAcademyIds = dirFilterAcademy ? [dirFilterAcademy] : allAcademyIds

    

    return (
      <div className="bg-gray-900/60 border border-gray-800 border-t-0 rounded-b-xl p-4 space-y-4">
        <div className="flex gap-0 border-b border-gray-700">
          {(['roster', 'fixtures'] as const).map(s => (
            <button key={s} onClick={() => setSection(s)}
              className={`px-4 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                section === s ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-white'
              }`}>
              {s === 'roster' ? `Roster${roster ? ` (${roster.total})` : ''}` : 'Fixtures'}
            </button>
          ))}
        </div>

        {section === 'roster' && (
          <div className="space-y-4">
            {rosterError && <ErrorMsg message={rosterError} />}

            {/* Roster lock banner */}
            {fixtureState && fixtureState !== 'ROSTER_OPEN' && (
              <div className="flex items-center gap-2 px-3 py-2 bg-amber-900/30 border border-amber-700/50 rounded-lg">
                <span className="text-amber-400 text-sm">🔒</span>
                <span className="text-xs text-amber-300">
                  Roster locked — fixtures have been generated ({fixtureState.replace(/_/g, ' ')}).
                  {!canManage && ' Contact the host academy coach to regenerate fixtures if needed.'}
                </span>
              </div>
            )}

            {/* Player directory — all players grouped by academy (admin only) */}
            {canManage && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">All Players</p>
                  {dirLoading && <span className="text-xs text-gray-600">Loading…</span>}
                </div>

                {/* Academy filter chips */}
                {allAcademyIds.length > 1 && (
                  <div className="flex gap-1.5 flex-wrap">
                    <button onClick={() => setDirFilterAcademy(null)}
                      className={`px-2 py-0.5 text-xs rounded transition-colors ${!dirFilterAcademy ? 'bg-white text-gray-900 font-medium' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
                      All
                    </button>
                    {allAcademyIds.map(id => {
                      const color = colorMap[id] ?? ACADEMY_PALETTE[0]
                      const label = dirByAcademy[id]?.[0]?.academy_name ?? id
                      return (
                        <button key={id} onClick={() => setDirFilterAcademy(dirFilterAcademy === id ? null : id)}
                          className={`px-2 py-0.5 text-xs rounded transition-colors ${dirFilterAcademy === id ? `${color.bg} ${color.text} font-medium` : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
                          {label}
                        </button>
                      )
                    })}
                  </div>
                )}

                <div className="border border-gray-700 rounded-lg divide-y divide-gray-800 max-h-72 overflow-y-auto">
                  {visibleAcademyIds.map(academyId => {
                    const players = dirByAcademy[academyId] ?? []
                    const color = colorMap[academyId] ?? ACADEMY_PALETTE[0]
                    const regCount = players.filter(p => registeredIds.has(p.player_id)).length
                    return (
                      <div key={academyId}>
                        <div className={`flex items-center gap-2 px-3 py-1.5 bg-gray-800/60 sticky top-0`}>
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${color.bg}`} />
                          <span className={`text-xs font-semibold ${color.text}`}>{players[0]?.academy_name}</span>
                          <span className="text-xs text-gray-500 ml-auto">{regCount}/{players.length} registered</span>
                        </div>
                        {players.map(p => {
                          const isRegistered = registeredIds.has(p.player_id)
                          const isInactive = p.status !== 'ACTIVE'
                          const rosterLocked = Boolean(fixtureState && fixtureState !== 'ROSTER_OPEN')
                          return (
                            <div key={p.player_id} className={`flex items-center justify-between px-3 py-1.5 ${isInactive ? 'opacity-50' : ''}`}>
                              <div className="flex items-center gap-2 min-w-0">
                                <span className={`text-sm truncate ${isInactive ? 'text-gray-400' : 'text-white'}`}>{p.name}</span>
                                <span className="text-xs text-gray-500 flex-shrink-0">{Math.round(p.current_rating)}</span>
                                {isInactive && <span className="text-[10px] bg-gray-700 text-gray-400 px-1 rounded flex-shrink-0">INACTIVE</span>}
                              </div>
                              {isRegistered ? (
                                <div className="flex items-center gap-2 flex-shrink-0">
                                  <span className="text-[10px] bg-green-900 text-green-300 px-1.5 py-0.5 rounded font-medium">Registered</span>
                                  {!rosterLocked && (
                                    <button onClick={() => handleRemove(p.player_id)}
                                      className="text-xs text-gray-600 hover:text-red-400 transition-colors">✕</button>
                                  )}
                                </div>
                              ) : (
                                <button onClick={() => !isInactive && !rosterLocked && handleAdd(p.player_id)}
                                  disabled={isInactive || rosterLocked}
                                  title={rosterLocked ? 'Roster locked — regenerate fixtures to modify' : undefined}
                                  className="text-xs px-2 py-0.5 bg-blue-700 hover:bg-blue-600 text-white rounded flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                                  Add
                                </button>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )
                  })}
                  {allPlayers.length === 0 && !dirLoading && (
                    <p className="text-sm text-gray-600 px-3 py-3">No players found.</p>
                  )}
                </div>
              </div>
            )}

            {/* Registered roster summary */}
            {rosterLoading && <Spinner />}
            {!canManage && roster && roster.items.length === 0 && <p className="text-sm text-gray-500">No players registered yet.</p>}
            {!canManage && roster && (() => {
              const byAcademy: Record<string, typeof roster.items> = {}
              for (const p of roster.items) (byAcademy[p.academy_id] ??= []).push(p)
              return Object.entries(byAcademy).map(([academyId, players]) => {
                const color = colorMap[academyId] ?? ACADEMY_PALETTE[0]
                return (
                  <div key={academyId} className="space-y-1">
                    <div className={`flex items-center gap-1.5 text-xs font-semibold ${color.text}`}>
                      <span className={`inline-block w-2 h-2 rounded-full ${color.bg}`} />
                      {players[0].academy_name}
                      <span className="text-gray-500 font-normal ml-1">({players.length})</span>
                    </div>
                    {players.map(p => (
                      <div key={p.player_id} className="flex items-center justify-between bg-gray-800/50 rounded px-3 py-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-white">{p.name}</span>
                          <span className="text-xs text-gray-500">{Math.round(p.current_rating)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )
              })
            })()}
          </div>
        )}

        {section === 'fixtures' && (
          <div className="space-y-4">
            {canManage && (() => {
              const isLocked = fixtureState === 'FIXTURE_FROZEN' || fixtureState === 'RESULTS_SUBMITTED' || fixtureState === 'RATINGS_APPLIED'
              const hasFixtures = Boolean(fixtures && fixtures.slots.length > 0)
              const scheduledCount = fixtures?.slots.filter(s => s.status === 'SCHEDULED').length ?? 0

              return (
                <div className="space-y-3">
                  {/* Fixture state banner */}
                  {fixtureState === 'FIXTURES_READY' && (
                    <div className="flex items-center gap-2 px-3 py-2 bg-blue-900/30 border border-blue-700/50 rounded-lg">
                      <span className="text-xs text-blue-300">
                        Fixtures generated — review pairings, try a different strategy, or lock when satisfied.
                      </span>
                    </div>
                  )}
                  {fixtureState === 'FIXTURE_FROZEN' && (
                    <div className="flex items-center gap-2 px-3 py-2 bg-purple-900/30 border border-purple-700/50 rounded-lg">
                      <span className="text-xs text-purple-300">
                        🔒 Fixtures locked — no further regeneration allowed. Enter match results to proceed.
                      </span>
                    </div>
                  )}
                  {fixtureState === 'RESULTS_SUBMITTED' && (
                    <div className="flex items-center gap-2 px-3 py-2 bg-green-900/20 border border-green-700/40 rounded-lg">
                      <span className="text-xs text-green-300">
                        ✓ All match results submitted — click Apply Ratings to update player Elo ratings.
                      </span>
                    </div>
                  )}
                  {fixtureState === 'RATINGS_APPLIED' && (
                    <div className="flex items-center gap-2 px-3 py-2 bg-green-900/30 border border-green-700/50 rounded-lg">
                      <span className="text-xs text-green-300">
                        ✓ Event complete — ratings applied for all confirmed matches.
                      </span>
                    </div>
                  )}

                  {/* Generation controls (hidden once locked) */}
                  {!isLocked && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-3 flex-wrap">
                        <div className="flex items-center gap-2">
                          <label className="text-sm text-gray-400">Tables:</label>
                          <input type="number" min={1} max={20} value={numTables}
                            onChange={e => setNumTables(Number(e.target.value))}
                            className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-white text-sm" />
                        </div>
                        <div className="flex items-center gap-2">
                          <label className="text-sm text-gray-400">Strategy:</label>
                          <select value={fixtureStrategy} onChange={e => setFixtureStrategy(e.target.value)}
                            className="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 text-sm">
                            <option value="TIER_MATCHED">Tier-Matched Cross-Academy</option>
                            <option value="CROSS_ACADEMY_ONLY">Cross-Academy Only</option>
                            <option value="TEAM_FORMAT">Academy Team Format</option>
                            <option value="FULL_ROUND_ROBIN">Full Round-Robin (Advanced)</option>
                          </select>
                        </div>
                        {/* Generate / Regenerate button */}
                        {hasFixtures && fixtureState === 'FIXTURES_READY' ? (
                          <button onClick={() => setConfirmRegenerate(true)} disabled={generating}
                            className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm font-medium rounded-lg disabled:opacity-50">
                            {generating ? 'Generating…' : 'Regenerate'}
                          </button>
                        ) : (
                          <button onClick={handleGenerate} disabled={generating}
                            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-50">
                            {generating ? 'Generating…' : 'Generate Fixtures'}
                          </button>
                        )}
                        {genError && <span className="text-xs text-red-400">{genError}</span>}
                      </div>
                      {fixtures?.warnings && fixtures.warnings.length > 0 && (
                        <div className="space-y-1 mt-2">
                          {fixtures.warnings.map((w, i) => {
                            const colorClass =
                              w.severity === 'ERROR' ? 'text-red-400' :
                              w.severity === 'WARN'  ? 'text-yellow-400' :
                                                      'text-gray-400'
                            return (
                              <p key={`${w.code}-${i}`} className={`text-xs ${colorClass}`}>
                                <span className="font-semibold">{w.severity}:</span> {w.message}
                              </p>
                            )
                          })}
                        </div>
                      )}
                      {fixtureStrategy === 'TIER_MATCHED' && (
                        <p className="text-xs text-gray-500">Players are grouped by rating tier. Cross-academy round-robin within each tier — maximises competitive matches.</p>
                      )}
                      {fixtureStrategy === 'CROSS_ACADEMY_ONLY' && (
                        <p className="text-xs text-gray-500">Circle method with same-academy pairs replaced by BYEs. Every scheduled match is cross-academy.</p>
                      )}
                      {fixtureStrategy === 'TEAM_FORMAT' && (
                        <p className="text-xs text-gray-500">Each academy pair plays a positional matchup (#1 vs #1, #2 vs #2 …). Produces clear team scores per matchup.</p>
                      )}
                      {fixtureStrategy === 'FULL_ROUND_ROBIN' && (
                        <p className="text-xs text-yellow-600">Every player plays every other player. Produces many stretch matches when academies have different rating levels.</p>
                      )}
                    </div>
                  )}

                  {/* Lock Fixtures button — only when FIXTURES_READY */}
                  {fixtureState === 'FIXTURES_READY' && hasFixtures && (
                    <div className="flex items-center gap-3">
                      <button onClick={() => setConfirmLock(true)} disabled={locking}
                        className="px-4 py-1.5 bg-purple-700 hover:bg-purple-600 text-white text-sm font-medium rounded-lg disabled:opacity-50">
                        {locking ? 'Locking…' : '🔒 Lock Fixtures'}
                      </button>
                      <span className="text-xs text-gray-500">Prevent further regeneration and roster changes.</span>
                      {lockError && <span className="text-xs text-red-400">{lockError}</span>}
                    </div>
                  )}

                  {/* Apply Ratings button — when all results are in (RESULTS_SUBMITTED or FIXTURE_FROZEN with no pending slots) */}
                  {(fixtureState === 'RESULTS_SUBMITTED' || (fixtureState === 'FIXTURE_FROZEN' && scheduledCount === 0)) && hasFixtures && (
                    <div className="flex items-center gap-3">
                      <button onClick={handleApplyRatings} disabled={applyingRatings}
                        className="px-4 py-1.5 bg-green-700 hover:bg-green-600 text-white text-sm font-medium rounded-lg disabled:opacity-50">
                        {applyingRatings ? 'Applying…' : '✅ Apply Ratings'}
                      </button>
                      <span className="text-xs text-gray-500">Update player Elo ratings for all confirmed matches.</span>
                      {applyError && <span className="text-xs text-red-400">{applyError}</span>}
                    </div>
                  )}
                  {fixtureState === 'FIXTURE_FROZEN' && scheduledCount > 0 && (
                    <p className="text-xs text-gray-500">
                      {scheduledCount} match result{scheduledCount !== 1 ? 's' : ''} still pending — enter all results to enable Apply Ratings.
                    </p>
                  )}

                  {/* Confirm Regenerate dialog */}
                  {confirmRegenerate && (
                    <div className="bg-gray-800 border border-amber-700/50 rounded-lg p-4 space-y-3">
                      <p className="text-sm text-amber-300 font-medium">Regenerate fixtures?</p>
                      <p className="text-xs text-gray-400">This will delete the current pairings and generate new ones. Any match results already entered will be lost.</p>
                      <div className="flex gap-2">
                        <button onClick={handleGenerate} disabled={generating}
                          className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-sm rounded-lg disabled:opacity-50">
                          {generating ? 'Generating…' : 'Yes, Regenerate'}
                        </button>
                        <button onClick={() => setConfirmRegenerate(false)}
                          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded-lg">
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Confirm Lock dialog */}
                  {confirmLock && (
                    <div className="bg-gray-800 border border-purple-700/50 rounded-lg p-4 space-y-3">
                      <p className="text-sm text-purple-300 font-medium">Lock these fixtures?</p>
                      <p className="text-xs text-gray-400">Once locked, you cannot regenerate or modify the fixture list. Match results can still be entered.</p>
                      <div className="flex gap-2">
                        <button onClick={handleLock} disabled={locking}
                          className="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 text-white text-sm rounded-lg disabled:opacity-50">
                          {locking ? 'Locking…' : 'Yes, Lock'}
                        </button>
                        <button onClick={() => setConfirmLock(false)}
                          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded-lg">
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })()}
            {fixturesLoading && <Spinner />}
            {fixturesError && <ErrorMsg message={fixturesError} />}
            {fixtures && fixtures.slots.length === 0 && (
              <p className="text-sm text-gray-500">No fixtures yet. Register players and click Generate Fixtures.</p>
            )}
            {fixtures && fixtures.slots.length > 0 && (
              <div className="space-y-4">
                <FixtureStats
                  fixtures={fixtures}
                  matchFormat={eventQ.data?.default_match_format ?? 'BEST_OF_3'}
                  numTables={numTables}
                />
                {(() => {
                  const model = buildMatrixModel(fixtures.slots as any, {
                    sectionOf: (p: any) => p.academy_id,
                    sectionMeta: (id: string, players: any[]) => ({
                      label: players[0]?.academy_name ?? id,
                      accent: colorMap[id] ?? ACADEMY_PALETTE[0],
                    }),
                    cellOf: (slot: any, self: any, opp: any) => {
                      const meta = classifyCell(slot as any, self as any, opp as any)
                      const opponentStrip = opp ? (colorMap[opp.academy_id]?.bg ?? '') : ''
                      return { label: meta.label, stripClass: opponentStrip, category: meta.category, tooltip: meta.tooltip }
                    },
                    totalRounds: fixtures.total_rounds,
                    sectionSort: (a, b) => a.label.localeCompare(b.label),
                  })

                  const legend = model.sections.map(s => ({ label: s.label, bg: s.accent.bg }))

                  return (
                    <FixtureMatrixGrid
                      model={model}
                      legend={legend}
                      sectionFilter={true}
                      onCellClick={(cell: MatrixCell) => {
                        const slotId = cell.slot_id
                        if (!slotId) return
                        const slot = fixtures.slots.find(s => s.slot_id === slotId)
                        if (slot && slot.status === 'SCHEDULED' && canManage) {
                          setResultSlot(slot)
                        }
                      }}
                    />
                  )
                })()}
                <SlotResultList
                  fixtures={fixtures}
                  colorMap={colorMap}
                  onEnterResult={setResultSlot}
                  onMarkUnplayed={handleMarkUnplayed}
                  markingUnplayed={markingUnplayed}
                  canManage={canManage}
                  resultStatusFilter={resultStatusFilter}
                  resultPlayerQuery={resultPlayerQuery}
                  setResultStatusFilter={setResultStatusFilter}
                  setResultPlayerQuery={setResultPlayerQuery}
                />
              </div>
            )}
          </div>
        )}

        {resultSlot && (
          <EventResultModal
            slot={resultSlot}
            eventId={eventId}
            matchFormat={eventQ.data?.default_match_format ?? 'BEST_OF_3'}
            onClose={() => setResultSlot(null)}
            onSuccess={() => { setResultSlot(null); loadFixtures() }}
          />
        )}
      </div>
    )
  }

  // ── Fixture statistics panel ──────────────────────────────────────────────────

  function generateCoachSummary(fairnessIndex: number, avgMaxPlayStreak: number, sosSpread: number) {
    // Sentence 1: Match Fairness / Skill Variance
    let skillAssessment = `Match fairness shows an Elo rating variance of **${Math.round(sosSpread)} points** between players and their average opponent pool, which is **excellent**.`;
    if (sosSpread >= 100 && sosSpread < 250) {
      skillAssessment = `Match fairness shows an Elo rating variance of **${Math.round(sosSpread)} points** between players and their average opponent pool, which is **manageable**.`;
    } else if (sosSpread >= 250) {
      skillAssessment = `Match fairness shows an Elo rating variance of **${Math.round(sosSpread)} points** between players and their average opponent pool, which is **high and concerning**.`;
    }

    // Sentence 2: Physical Strain / Continuous Round Streaks
    let streakAssessment = `Players face an average continuous play streak of **${avgMaxPlayStreak.toFixed(1)} consecutive rounds**, ensuring adequate rest between matches.`;
    if (avgMaxPlayStreak > 1.2 && avgMaxPlayStreak <= 2.0) {
      streakAssessment = `Players face an average continuous play streak of **${avgMaxPlayStreak.toFixed(1)} consecutive rounds**, resulting in occasional back-to-back scheduling.`;
    } else if (avgMaxPlayStreak > 2.0) {
      streakAssessment = `Players face an average continuous play streak of **${avgMaxPlayStreak.toFixed(1)} consecutive rounds**, creating extended periods without rest.`;
    }

    // Sentence 3: Overall Schedule Health Grade
    const healthGrade = fairnessIndex >= 75 ? 'highly balanced' : fairnessIndex >= 50 ? 'moderately balanced' : 'unbalanced';
    const healthSentence = `Overall schedule health assessment: **${healthGrade} (${fairnessIndex}%)**.`;

    // Sentence 4: Table Rotation Logistics
    const tableLogistics = `Table rotation logistics ensure players rotate across multiple physical courts throughout the event.`;

    return `${skillAssessment} ${streakAssessment} ${healthSentence} ${tableLogistics}`;
  }

  function FixtureStats({ fixtures, matchFormat, numTables }: {
    fixtures: EventFixtures
    matchFormat: string
    numTables: number
  }) {
    const CHANGEOVER = 3 // minutes between rounds

    const playerStats: Record<string, {
      total: number; cross: number; intra: number
      competitive: number; stretch: number; anchor: number; out_of_band: number; byes: number
      opponents: Set<string>
    }> = {}


    const playerMatchPhases: Record<string, Array<{ round_number: number; wave_number: number }>> = {}
    const opponentRatings: Record<string, number[]> = {}
    const tableSets: Record<string, Set<number>> = {}
    const playerAcademy: Record<string, string> = {}
    const academyNames: Record<string, string> = {}
    const playerRatings: Record<string, number> = {}
    const maxWavePerRound: Record<number, number> = {}
    const roundIntentCounts: Record<string, number> = {}

    const upsertStats = (pid: string) => {
      if (!playerStats[pid]) playerStats[pid] = { total: 0, cross: 0, intra: 0, competitive: 0, stretch: 0, anchor: 0, out_of_band: 0, byes: 0, opponents: new Set() }
      if (!playerMatchPhases[pid]) playerMatchPhases[pid] = []
      if (!opponentRatings[pid]) opponentRatings[pid] = []
      if (!tableSets[pid]) tableSets[pid] = new Set()
    }

    const getNextChronoPhase = (phase: { round_number: number; wave_number: number }) => {
      const maxWave = maxWavePerRound[phase.round_number] ?? phase.wave_number
      if (phase.wave_number < maxWave) {
        return { round_number: phase.round_number, wave_number: phase.wave_number + 1 }
      }
      return { round_number: phase.round_number + 1, wave_number: 1 }
    }

    for (const slot of fixtures.slots) {
      const isBye = slot.status === 'BYE' || !slot.player_b
      const isCross = !isBye && slot.player_a.academy_id !== slot.player_b!.academy_id
      maxWavePerRound[slot.round_number] = Math.max(maxWavePerRound[slot.round_number] ?? 0, slot.wave_number)

      const aId = slot.player_a.player_id
      upsertStats(aId)
      playerAcademy[aId] = slot.player_a.academy_id
      academyNames[slot.player_a.academy_id] = slot.player_a.academy_name
      playerRatings[aId] = slot.player_a.current_rating

      if (isBye) {
        playerStats[aId].byes++
        if (slot.round_intent) roundIntentCounts[slot.round_intent] = (roundIntentCounts[slot.round_intent] ?? 0) + 1
        continue
      }

      const pb = slot.player_b!
      const bId = pb.player_id
      upsertStats(bId)
      playerAcademy[bId] = pb.academy_id
      academyNames[pb.academy_id] = pb.academy_name
      playerRatings[bId] = pb.current_rating

      const category = getGapBandCategory(slot)
      if (slot.round_intent) roundIntentCounts[slot.round_intent] = (roundIntentCounts[slot.round_intent] ?? 0) + 1

      const phase = { round_number: slot.round_number, wave_number: slot.wave_number }
      playerMatchPhases[aId].push(phase)
      playerMatchPhases[bId].push(phase)

      for (const [pid, oppId] of [
        [aId, bId],
        [bId, aId],
      ] as [string, string][]) {
        const s = playerStats[pid]
        const oppRating = playerRatings[oppId]
        s.total++
        s.opponents.add(oppId)
        if (isCross) s.cross++; else s.intra++
        if (category === 'competitive') s.competitive++
        else if (category === 'stretch') s.stretch++
        else if (category === 'anchor') s.anchor++
        else if (category === 'out_of_band') s.out_of_band++
        opponentRatings[pid].push(oppRating)
        tableSets[pid].add(slot.table_number)
      }
    }

    const allPlayerIds = Object.keys(playerStats)
    if (allPlayerIds.length === 0) return null

    const stat = (arr: number[]) => {
      if (!arr || arr.length === 0) return { min: 0, max: 0, avg: 0 }
      const min = Math.min(...arr), max = Math.max(...arr)
      const avg = arr.reduce((a, b) => a + b, 0) / arr.length
      return { min, max, avg: Math.round(avg * 10) / 10 }
    }

    const playerIds = Object.keys(playerStats)
    const maxPlayStreakByPlayer: Record<string, number> = {}
    const sosByPlayer: Record<string, number> = {}
    const tableCountByPlayer: Record<string, number> = {}

    for (const pid of playerIds) {
      const phases = (playerMatchPhases[pid] ?? []).slice()
      phases.sort((a, b) => a.round_number === b.round_number ? a.wave_number - b.wave_number : a.round_number - b.round_number)

      let currentStreak = 0
      let maxStreak = 0
      let prevPhase: { round_number: number; wave_number: number } | null = null

      for (const phase of phases) {
        if (!prevPhase) {
          currentStreak = 1
        } else {
          const nextPhase = getNextChronoPhase(prevPhase)
          if (phase.round_number === nextPhase.round_number && phase.wave_number === nextPhase.wave_number) {
            currentStreak += 1
          } else {
            currentStreak = 1
          }
        }
        maxStreak = Math.max(maxStreak, currentStreak)
        prevPhase = phase
      }

      maxPlayStreakByPlayer[pid] = maxStreak
      const sosRatings = opponentRatings[pid]
      sosByPlayer[pid] = sosRatings.length ? sosRatings.reduce((a, b) => a + b, 0) / sosRatings.length : 0
      tableCountByPlayer[pid] = tableSets[pid]?.size ?? 0
    }

    const avgMaxPlayStreak = stat(Object.values(maxPlayStreakByPlayer)).avg
    const restBalanceScore = Math.max(0, 100 - Math.round((avgMaxPlayStreak - 1) * 20))
    
    // Compute rating-relative offsets and dynamic fairness ceiling
    const maxPlayerRating = Math.max(...Object.values(playerRatings).filter(r => r > 0), 1000)
    const dynamicCeiling = maxPlayerRating * 0.25
    const ratingRelativeOffsets = Object.entries(sosByPlayer)
      .filter(([pid]) => (opponentRatings[pid]?.length ?? 0) >= 2)
      .map(([pid]) => Math.abs((playerRatings[pid] ?? 0) - sosByPlayer[pid]))
    const dynamicSpread = ratingRelativeOffsets.length > 0 ? Math.max(...ratingRelativeOffsets) : 0
    const sosSpread = dynamicSpread
    const sosBalanceScore = Math.max(0, 100 - Math.round((dynamicSpread / dynamicCeiling) * 100))
    const fairnessIndex = Math.round((restBalanceScore + sosBalanceScore) / 2)

    const coachSummary = generateCoachSummary(fairnessIndex, avgMaxPlayStreak, sosSpread)
    const coachParts = coachSummary.split('**')

    const criticalTraps = playerIds.filter(pid => maxPlayStreakByPlayer[pid] >= 3)
    const warningTraps = playerIds.filter(pid => maxPlayStreakByPlayer[pid] === 2)

    const tierBuckets: Record<number, number[]> = {}
    for (const pid of playerIds) {
      const tier = Math.floor((playerRatings[pid] ?? 0) / 100)
      ;(tierBuckets[tier] ??= []).push(sosByPlayer[pid])
    }
    const severeTierVariance = Object.entries(tierBuckets)
      .map(([, values]) => values.length > 1 ? Math.max(...values) - Math.min(...values) : 0)
      .filter(v => v >= 100)
    const hasSevereTierVariance = severeTierVariance.length > 0

    const academyTableAverages: Record<string, number[]> = {}
    for (const pid of playerIds) {
      const academy = playerAcademy[pid] ?? 'UNKNOWN'
      ;(academyTableAverages[academy] ??= []).push(tableCountByPlayer[pid])
    }
    const academyTableSummary = Object.entries(academyTableAverages).map(([academy, counts]) => ({
      academyId: academy,
      academyName: (academyNames[academy] ?? academy),
      avgTables: counts.length ? Math.round((counts.reduce((a, b) => a + b, 0) / counts.length) * 10) / 10 : 0,
    }))
    const academyAvgTables = Object.values(academyTableAverages).map(counts =>
      counts.length ? counts.reduce((a, b) => a + b, 0) / counts.length : 0
    )
    const tableEquityWarning = academyAvgTables.length > 1
      ? Math.max(...academyAvgTables) - Math.min(...academyAvgTables) > 0.5
      : false

    const vals = Object.values(playerStats)
    const matchesPS = stat(vals.map(v => v.total))
    const crossPS = stat(vals.map(v => v.cross))
    const intraPS = stat(vals.map(v => v.intra))
    const compPS = stat(vals.map(v => v.competitive))
    const strPS = stat(vals.map(v => v.stretch))
    const ancPS = stat(vals.map(v => v.anchor))
    const outPS = stat(vals.map(v => v.out_of_band))
    const oppPS = stat(vals.map(v => v.opponents.size))
    const hasAnchor = vals.some(v => v.anchor > 0)

    const duration = MATCH_DURATION_MIN[matchFormat] ?? 18
    const estMin = fixtures.total_rounds * (duration + CHANGEOVER)
    const hours = Math.floor(estMin / 60), mins = estMin % 60

    const StatRow = ({ label, s, accent }: { label: string; s: { min: number; max: number; avg: number }; accent?: string }) => (
      <div className="flex items-center justify-between py-1.5 border-b border-gray-800/60 last:border-0">
        <span className={`text-xs ${accent ?? 'text-gray-400'}`}>{label}</span>
        <div className="flex gap-4 text-xs font-mono">
          <span className="text-gray-500">min <span className="text-white">{s.min}</span></span>
          <span className="text-gray-500">avg <span className="text-blue-300">{s.avg}</span></span>
          <span className="text-gray-500">max <span className="text-white">{s.max}</span></span>
        </div>
      </div>
    )

    return (
      <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs border-b border-gray-800 pb-3">
          <span className="text-gray-400">{fixtures.total_rounds} rounds · {fixtures.total_slots} matches · {vals.length} players</span>
          <span className="text-green-400 font-medium">{fixtures.cross_academy_pct}% cross-academy</span>
          <span className="text-yellow-400 font-medium">~{hours > 0 ? `${hours}h ` : ''}{mins}m estimated ({numTables} tables · {duration}min/match)</span>
          <div className="w-full text-xs text-gray-400 mt-1">
            {Object.keys(roundIntentCounts || {}).length > 0 && (
              <div className="flex gap-2 flex-wrap">
                <span className="font-semibold text-gray-300">Round intents:</span>
                {Object.entries(roundIntentCounts).map(([k, v]) => (
                  <span key={k} className="text-xs bg-gray-800 px-2 py-0.5 rounded">
                    {k}: <span className="text-white ml-1">{v}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-x-8 gap-y-4">
          <div className="xl:col-span-2 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
              <div>
                <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Matches per player</p>
                <StatRow label="Total matches" s={matchesPS} />
                <StatRow label="Cross-academy" s={crossPS} accent="text-green-400" />
                <StatRow label="Intra-academy" s={intraPS} accent="text-blue-400" />
                <StatRow label="Unique opponents" s={oppPS} />
              </div>
              <div>
                <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">By gap band</p>
                <StatRow label="Competitive" s={compPS} accent="text-blue-400" />
                <StatRow label="Stretch" s={strPS} accent="text-purple-400" />
                <StatRow label="Out of band" s={outPS} accent="text-orange-400" />
                {hasAnchor && <StatRow label="Anchor" s={ancPS} accent="text-green-400" />}
              </div>
            </div>
            <div className="bg-gray-800/60 border border-gray-700 rounded-lg p-4">
              <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Schedule Narrative</p>
              <div className="text-xs text-gray-400 leading-relaxed space-y-2">
                {coachParts.map((part: string, i: number) => i % 2 === 1 ? <span key={i} className="font-semibold text-blue-300">{part}</span> : <span key={i}>{part}</span>)}
              </div>
            </div>
          </div>
          <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-3">
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-2">Fixture Fairness Insight</p>
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wide">Overall fairness</p>
                <p className="text-2xl font-semibold text-white">{fairnessIndex}%</p>
              </div>
              <span className={`px-2 py-1 text-[10px] font-semibold rounded ${fairnessIndex >= 75 ? 'bg-green-900 text-green-200' : fairnessIndex >= 50 ? 'bg-yellow-900 text-yellow-200' : 'bg-red-900 text-red-200'}`}>
                {fairnessIndex >= 75 ? 'Balanced' : fairnessIndex >= 50 ? 'Moderate' : 'Unbalanced'}
              </span>
            </div>
            <div className="space-y-2 text-[10px] text-gray-300">
              <div className="flex items-center justify-between">
                <span>Match Fairness Delta</span>
                <span>{Math.round(sosSpread)} pts</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Avg. Back-to-Back Games</span>
                <span>{avgMaxPlayStreak.toFixed(1)} matches</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Table Rotation Variety</span>
                <span>{Math.round(Object.values(tableCountByPlayer).reduce((a, b) => a + b, 0) / playerIds.length)} tables / player</span>
              </div>
            </div>
            <div className="mt-3 space-y-2">
              {criticalTraps.length > 0 && (
                <div className="inline-flex items-center gap-2 rounded-lg bg-red-900/80 px-3 py-2 text-[10px] text-red-200">
                  <span className="font-semibold">Critical Traps:</span>
                  <span>{criticalTraps.length} player{criticalTraps.length !== 1 ? 's' : ''}</span>
                </div>
              )}
              {warningTraps.length > 0 && (
                <div className="inline-flex items-center gap-2 rounded-lg bg-amber-900/80 px-3 py-2 text-[10px] text-amber-200">
                  <span className="font-semibold">Warning Traps:</span>
                  <span>{warningTraps.length} player{warningTraps.length !== 1 ? 's' : ''}</span>
                </div>
              )}
              {tableEquityWarning && (
                <div className="inline-flex items-center gap-2 rounded-lg bg-blue-900/80 px-3 py-2 text-[10px] text-blue-200">
                  <span className="font-semibold">Table equity alert</span>
                  <span>One academy has a narrow table distribution.</span>
                </div>
              )}
              {hasSevereTierVariance && (
                <div className="inline-flex items-center gap-2 rounded-lg bg-purple-900/80 px-3 py-2 text-[10px] text-purple-200">
                  <span className="font-semibold">SoS variance</span>
                  <span>Severe same-tier opponent imbalances detected.</span>
                </div>
              )}
            </div>
            {academyTableSummary.length > 0 && (
              <div className="mt-3 text-[10px] text-gray-400 space-y-1">
                <div className="font-semibold text-gray-300">Table equity by academy</div>
                {academyTableSummary.map(summary => (
                  <div key={summary.academyId} className="flex items-center justify-between">
                    <span>{summary.academyName}</span>
                    <span>{summary.avgTables.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── Round-by-round slot list with Enter Result buttons ────────────────────────

  function PlayedResultDisplay({ matchId }: { matchId: string }) {
    const matchQ = useQuery({
      queryKey: ['match', matchId],
      queryFn: () => matchesApi.get(matchId),
      enabled: !!matchId,
      staleTime: 0, // Always refetch to get latest data
      retry: 1,
    })

    if (matchQ.isLoading) return <span className="text-xs text-gray-500">Loading…</span>

    const m = matchQ.data as MatchResponse | undefined
    let scoreDisplay = ''
    if (m) {
      if (Array.isArray(m.set_scores) && m.set_scores.length > 0) {
        const detail = m.set_scores
          .slice()
          .sort((a, b) => a.set_number - b.set_number)
          .map(s => `${s.points_a}-${s.points_b}`)
          .join(' ')
        scoreDisplay = `${m.sets_won_a}-${m.sets_won_b} (${detail})`
      } else if (typeof m.sets_won_a === 'number' && typeof m.sets_won_b === 'number') {
        scoreDisplay = `${m.sets_won_a}-${m.sets_won_b}`
      }
    }

    return (
      <div className="text-right">
        <div className="text-xs text-green-400 font-medium">✓ Played</div>
        {scoreDisplay && <div className="text-[10px] text-gray-500 font-mono">{scoreDisplay}</div>}
        {!scoreDisplay && m && <div className="text-[10px] text-gray-600 italic">scores pending</div>}
      </div>
    )
  }

  function SlotResultList({ fixtures, colorMap, onEnterResult, onMarkUnplayed, markingUnplayed, canManage, resultStatusFilter, resultPlayerQuery, setResultStatusFilter, setResultPlayerQuery }: {
    fixtures: EventFixtures
    colorMap: Record<string, { bg: string; text: string }>
    onEnterResult: (slot: EventFixtureSlot) => void
    onMarkUnplayed: ((slot: EventFixtureSlot, unplayed: boolean) => void)
    markingUnplayed: boolean
    canManage: boolean
    resultStatusFilter: 'PENDING' | 'PLAYED' | 'ALL'
    resultPlayerQuery: string
    setResultStatusFilter: React.Dispatch<React.SetStateAction<'PENDING' | 'PLAYED' | 'ALL'>>
    setResultPlayerQuery: React.Dispatch<React.SetStateAction<string>>
  }) {
    const q = resultPlayerQuery.trim().toLowerCase()
    const filteredSlots = fixtures.slots.filter(s => {
      if (resultStatusFilter === 'PENDING' && s.status !== 'SCHEDULED') return false
      if (resultStatusFilter === 'PLAYED' && s.status !== 'PLAYED') return false
      if (q) {
        const a = s.player_a?.name?.toLowerCase() ?? ''
        const b = s.player_b?.name?.toLowerCase() ?? ''
        if (!a.includes(q) && !b.includes(q)) return false
      }
      return true
    })

    const byRound = filteredSlots.reduce<Record<number, EventFixtureSlot[]>>((acc, s) => {
      ;(acc[s.round_number] ??= []).push(s)
      return acc
    }, {})

    const scheduledCount = filteredSlots.filter(s => s.status === 'SCHEDULED').length

    const [expandedByes, setExpandedByes] = useState<Record<number, boolean>>({})

    return (
      <div className="space-y-3">
        <div className="space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <input
                type="text"
                value={resultPlayerQuery}
                onChange={e => setResultPlayerQuery(e.target.value)}
                placeholder="Search by player name..."
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white w-full sm:w-80"
              />
              <div className="flex flex-wrap gap-2">
                {(['PENDING', 'PLAYED', 'ALL'] as const).map(status => (
                  <button key={status}
                    type="button"
                    onClick={() => setResultStatusFilter(status)}
                    className={`px-3 py-1 text-xs rounded-lg transition ${resultStatusFilter === status ? 'bg-white text-gray-900 font-semibold' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
                    {status === 'PENDING' ? 'Pending' : status === 'PLAYED' ? 'Played' : 'All'}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Enter Results</p>
              {scheduledCount > 0 && (
                <span className="text-xs text-yellow-400">{scheduledCount} match{scheduledCount !== 1 ? 'es' : ''} pending</span>
              )}
              {scheduledCount === 0 && (
                <span className="text-xs text-green-400">All matches completed</span>
              )}
            </div>
          </div>
          {filteredSlots.length === 0 && (
            <div className="rounded-lg border border-gray-800 bg-gray-900/60 px-4 py-3 text-sm text-gray-400">No matches match this filter.</div>
          )}
        </div>
        {Object.entries(byRound).map(([rn, slots]) => {
          const rnNum = Number(rn)
          const byeSlots = slots.filter(s => s.status === 'BYE' || !s.player_b)
          const visibleSlots = slots.filter(s => !(s.status === 'BYE' || !s.player_b))
          const expanded = !!expandedByes[rnNum]

          return (
            <div key={rn}>
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-500 mb-1.5 font-semibold uppercase tracking-wide">Round {rn}</div>
                {byeSlots.length > 0 && (
                  <button onClick={() => setExpandedByes(prev => ({ ...prev, [rnNum]: !prev[rnNum] }))}
                    className="text-xs text-gray-400 hover:text-white bg-gray-800 px-2 py-1 rounded">
                    {expanded ? `Hide BYEs (${byeSlots.length})` : `Show BYEs (${byeSlots.length})`}
                  </button>
                )}
              </div>
              <div className="space-y-1">
                {visibleSlots.map(slot => {
                  const pb = slot.player_b!
                  const aColor = colorMap[slot.player_a.academy_id] ?? ACADEMY_PALETTE[0]
                  const bColor = colorMap[pb.academy_id] ?? ACADEMY_PALETTE[0]
                  const isCross = slot.player_a.academy_id !== pb.academy_id
                  const matchTypeMeta = getMatchTypeMeta(slot)
                  return (
                    <div key={slot.slot_id}
                      className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
                      <span className="text-xs text-gray-600 w-10 font-mono shrink-0">T{slot.table_number}</span>
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md border border-gray-800 bg-gray-800/40 shrink-0 ${matchTypeMeta.className}`}
                        title={matchTypeMeta.title}
                      >
                        {matchTypeMeta.shortLabel}
                      </span>
                      <div className="flex items-center gap-1.5 flex-1 min-w-0">
                        <span className={`text-sm font-medium truncate ${aColor.text}`}>{slot.player_a.name}</span>
                        <span className="text-[10px] text-gray-500">({Math.round(slot.player_a.current_rating)})</span>
                        {isCross && <span className={`text-[10px] px-1 rounded shrink-0 ${aColor.bg} ${aColor.text}`}>{slot.player_a.academy_name}</span>}
                        <span className="text-gray-600 text-xs shrink-0">vs</span>
                        <span className={`text-sm font-medium truncate ${bColor.text}`}>{pb.name}</span>
                        <span className="text-[10px] text-gray-500">({Math.round(pb.current_rating)})</span>
                        {isCross && <span className={`text-[10px] px-1 rounded shrink-0 ${bColor.bg} ${bColor.text}`}>{pb.academy_name}</span>}
                      </div>
                      <div className="shrink-0 ml-auto flex items-center gap-2">
                        {slot.status === 'SCHEDULED' && canManage && (
                          <>
                            <button onClick={() => onEnterResult(slot)}
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition-colors">
                              Enter Result
                            </button>
                            <button onClick={() => onMarkUnplayed(slot, true)}
                              disabled={markingUnplayed}
                              className="px-2.5 py-1 bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium rounded-lg transition-colors">
                              Mark no-show
                            </button>
                          </>
                        )}
                        {slot.status === 'SCHEDULED' && !canManage && (
                          <span className="text-xs text-yellow-400">Result Pending</span>
                        )}
                        {slot.status === 'PLAYED' && slot.match_id && <PlayedResultDisplay matchId={slot.match_id} />}
                        {slot.status === 'UNPLAYED' && (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">Unplayed</span>
                            {canManage && (
                              <button onClick={() => onMarkUnplayed(slot, false)}
                                disabled={markingUnplayed}
                                className="px-2.5 py-1 bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium rounded-lg transition-colors">
                                Undo
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}

                {expanded && byeSlots.map(slot => (
                  <div key={slot.slot_id} className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 opacity-40">
                    <span className="text-xs text-gray-500 w-16 shrink-0">T{slot.table_number}</span>
                    <span className="text-sm text-gray-400">{slot.player_a.name}</span>
                    <span className="text-xs text-gray-600">{slot.player_a.academy_name}</span>
                    <span className="text-xs text-gray-600 italic">BYE</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // ── Inter-academy result entry modal ──────────────────────────────────────────

  function EventResultModal({ slot, eventId, matchFormat, onClose, onSuccess }: {
    slot: EventFixtureSlot
    eventId: string
    matchFormat: string
    onClose: () => void
    onSuccess: () => void
  }) {
    const [setsA, setSetsA] = useState('')
    const [setsB, setSetsB] = useState('')
    const [isRetirement, setIsRetirement] = useState(false)
    const [setScores, setSetScores] = useState<Array<{ points_a: number; points_b: number }> | null>(null)
    const [matchDate, setMatchDate] = useState(new Date().toISOString().slice(0, 10))
    const [error, setError] = useState<string | null>(null)

    const max = MAX_SETS_MAP[matchFormat] ?? 2
    const nA = Number(setsA), nB = Number(setsB)
    const isValid = setsA !== '' && setsB !== '' && nA !== nB && (
      isRetirement
        ? (nA + nB > 0 && nA <= max && nB <= max)
        : ((nA === max && nB < max) || (nB === max && nA < max))
    )

    const mut = useMutation({
      mutationFn: () => matchesApi.submit({
        event_id: eventId,
        fixture_slot_id: slot.slot_id,
        player_a_id: slot.player_a.player_id,
        player_b_id: slot.player_b!.player_id,
        match_format: matchFormat,
        sets_won_a: nA,
        sets_won_b: nB,
        match_date: matchDate,
        is_retirement: isRetirement,
        set_scores: setScores,
      }),
      onSuccess: () => onSuccess(),
      onError: (e: Error) => setError(e.message),
    })

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 w-full max-w-sm mx-4 space-y-4"
          onClick={e => e.stopPropagation()}>
          <div>
            <h3 className="text-white font-semibold">Enter Result</h3>
            <p className="text-sm text-gray-300 mt-1">
              <span className="text-white">{slot.player_a.name}</span>
              <span className="text-gray-600 text-xs ml-1">{slot.player_a.academy_name} · {Math.round(slot.player_a.current_rating)}</span>
              <span className="text-gray-500 mx-1">vs</span>
              <span className="text-white">{slot.player_b!.name}</span>
              <span className="text-gray-600 text-xs ml-1">{slot.player_b!.academy_name} · {Math.round(slot.player_b!.current_rating)}</span>
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              {matchFormat.replace(/_/g, ' ')} · Table {slot.table_number} · first to {max} sets
            </p>
            <p className="text-xs text-yellow-600 mt-1">
              Result will be pending confirmation by the other player.
            </p>
          </div>

          {error && <ErrorMsg message={error} />}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1 truncate">{slot.player_a.name.split(' ')[0]} sets won</label>
              <input type="number" min={0} max={max} value={setsA} onChange={e => setSetsA(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-3 text-white text-center text-2xl font-mono focus:outline-none focus:border-blue-500" />
              <div className="text-center text-xs text-gray-600 mt-1 font-mono">{Math.round(slot.player_a.current_rating)}</div>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1 truncate">{slot.player_b!.name.split(' ')[0]} sets won</label>
              <input type="number" min={0} max={max} value={setsB} onChange={e => setSetsB(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-3 text-white text-center text-2xl font-mono focus:outline-none focus:border-blue-500" />
              <div className="text-center text-xs text-gray-600 mt-1 font-mono">{Math.round(slot.player_b!.current_rating)}</div>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Match date</label>
            <input type="date" value={matchDate} onChange={e => setMatchDate(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input type="checkbox" checked={isRetirement} onChange={e => setIsRetirement(e.target.checked)}
              className="w-4 h-4 accent-blue-500" />
            Retirement / walkover
          </label>

          {setsA !== '' && setsB !== '' && (() => {
            const nA = Number(setsA)
            const nB = Number(setsB)
            const maxSets = ({ BEST_OF_1: 1, BEST_OF_3: 3, BEST_OF_5: 5, BEST_OF_7: 7 } as const)[matchFormat as 'BEST_OF_1' | 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7']!
            return nA + nB > 0 && nA <= maxSets && nB <= maxSets && nA + nB <= maxSets ? (
              <SetPointsInput
                matchFormat={matchFormat as 'BEST_OF_1' | 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7'}
                setsWonA={nA}
                setsWonB={nB}
                isRetirement={isRetirement}
                onSetScoresChange={setSetScores}
              />
            ) : null
          })()}

          <div className="flex gap-2 pt-1">
            <button onClick={onClose}
              className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm">Cancel</button>
            <button onClick={() => mut.mutate()} disabled={mut.isPending || !isValid}
              className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-sm disabled:opacity-50">
              {mut.isPending ? 'Submitting…' : 'Submit Result'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  
