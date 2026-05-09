import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  leaderboardApi, matchesApi, playersApi, academiesApi, eventsApi, sessionsApi,
  type PlayerSearchResult, type LeaderboardEntry, type SessionSummary, type FixtureSlot,
} from '../api/client'
import { Layout, TierBadge, CRBar, Spinner, ErrorMsg, ProtectedRoute } from '../components/Layout'
import { useAuth } from '../auth/context'

export default function Dashboard() {
  return (
    <ProtectedRoute roles={['COACH', 'ADMIN']}>
      <Layout>
        <DashboardInner />
      </Layout>
    </ProtectedRoute>
  )
}

type Tab = 'roster' | 'events' | 'sessions' | 'submit' | 'register-player'

function DashboardInner() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('roster')

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Coach Dashboard</h2>

      <div className="flex gap-0 border-b border-gray-800 overflow-x-auto">
        {([
          ['roster', 'Roster'],
          ['events', 'My Events'],
          ['sessions', 'Sessions & Fixtures'],
          ['submit', 'Submit Match'],
          ['register-player', 'Register Player'],
        ] as [Tab, string][]).map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px whitespace-nowrap ${
              tab === t ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'roster' && user?.academy_id && <RosterTab academyId={user.academy_id} />}
      {tab === 'events' && user?.academy_id && <EventsTab academyId={user.academy_id} />}
      {tab === 'sessions' && user?.academy_id && <SessionsTab academyId={user.academy_id} />}
      {tab === 'submit' && user?.academy_id && <SubmitMatchTab academyId={user.academy_id} />}
      {tab === 'register-player' && user?.academy_id && <RegisterPlayerTab academyId={user.academy_id} />}
    </div>
  )
}

// ── My Events ────────────────────────────────────────────────────────────────

const EVENT_STATUS_COLOR: Record<string, string> = {
  SCHEDULED: 'bg-yellow-800 text-yellow-100',
  IN_PROGRESS: 'bg-blue-800 text-blue-100',
  COMPLETED: 'bg-green-800 text-green-100',
  CANCELLED: 'bg-gray-700 text-gray-300',
}

const MATCH_FORMATS = [
  { value: 'BEST_OF_3', label: 'Best of 3' },
  { value: 'BEST_OF_5', label: 'Best of 5' },
  { value: 'BEST_OF_7', label: 'Best of 7' },
]

function EventsTab({ academyId }: { academyId: string }) {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '', start_date: '', end_date: '', default_match_format: 'BEST_OF_3',
  })
  const [error, setError] = useState<string | null>(null)

  const q = useQuery({ queryKey: ['events'], queryFn: () => eventsApi.list() })

  const createMut = useMutation({
    mutationFn: () => eventsApi.create({
      name: form.name,
      scheduling_mode: 'INTRA_ACADEMY',
      event_type: 'FRIENDLY',
      default_match_format: form.default_match_format,
      start_date: form.start_date,
      end_date: form.end_date || undefined,
      host_academy_id: academyId,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events'] })
      setShowForm(false)
      setError(null)
      setForm({ name: '', start_date: '', end_date: '', default_match_format: 'BEST_OF_3' })
    },
    onError: (e: Error) => setError(e.message),
  })

  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorMsg message={(q.error as Error).message} />

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold text-white">My Events</h3>
          <p className="text-xs text-gray-500 mt-0.5">Intra-academy training events for daily sessions</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg">
          {showForm ? 'Cancel' : '+ New Event'}
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-3">
          {error && <ErrorMsg message={error} />}

          <div className="bg-gray-800/50 rounded-lg px-3 py-2 text-xs text-gray-400">
            Type: <span className="text-gray-200">Intra-Academy · Friendly</span>
            <span className="ml-2 text-gray-600">— only format available for in-academy training</span>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Event name <span className="text-red-400">*</span></label>
            <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Daily Training — Season 2025-26"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Start date <span className="text-red-400">*</span></label>
              <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">End date <span className="text-gray-600">(optional)</span></label>
              <input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Default match format <span className="text-red-400">*</span></label>
            <select value={form.default_match_format} onChange={e => setForm(f => ({ ...f, default_match_format: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
              {MATCH_FORMATS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <p className="text-xs text-gray-500 mt-1">Applied to all matches in sessions under this event unless overridden per-match.</p>
          </div>

          <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.name || !form.start_date}
            className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg disabled:opacity-50">
            {createMut.isPending ? 'Creating…' : 'Create Event'}
          </button>
        </div>
      )}

      <div className="space-y-2">
        {q.data?.items.map(ev => (
          <div key={ev.event_id} className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="font-medium text-white text-sm">{ev.name}</div>
                <div className="text-xs text-gray-500">{ev.event_type.replace(/_/g, ' ')} · {ev.start_date}</div>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${EVENT_STATUS_COLOR[ev.status] ?? ''}`}>
                {ev.status}
              </span>
            </div>
            <div className="text-xs text-gray-700 font-mono mt-1 truncate">{ev.event_id}</div>
          </div>
        ))}
        {!q.data?.items.length && <p className="text-gray-500 text-sm">No events yet. Create one to start running training sessions.</p>}
      </div>
    </div>
  )
}

// ── Sessions & Fixtures ───────────────────────────────────────────────────────

function SessionsTab({ academyId }: { academyId: string }) {
  const [eventId, setEventId] = useState('')
  // null = list view; a session_id string = that session is open
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [showNewForm, setShowNewForm] = useState(false)
  const [sessionForm, setSessionForm] = useState({ session_date: new Date().toISOString().slice(0, 10), num_tables: '3', session_minutes: '150', match_format: '' })
  const [selectedPlayers, setSelectedPlayers] = useState<Set<string>>(new Set())
  const [fixtureResult, setFixtureResult] = useState<{ bootstrap_phase: string; matches_per_player: number; fixture_slots_created: number } | null>(null)
  const [resultSlot, setResultSlot] = useState<FixtureSlot | null>(null)
  const [error, setError] = useState<string | null>(null)

  const eventsQ = useQuery({ queryKey: ['events'], queryFn: () => eventsApi.list() })
  const sessionsQ = useQuery({
    queryKey: ['sessions', eventId],
    queryFn: () => sessionsApi.list(eventId),
    enabled: !!eventId,
  })
  const rosterQ = useQuery({
    queryKey: ['academy-leaderboard', academyId],
    queryFn: () => academiesApi.leaderboard(academyId, { limit: 100 }),
  })
  // opened session's details (for resume)
  const openedSession = sessionsQ.data?.find(s => s.session_id === sessionId) ?? null
  const fixturesQ = useQuery({
    queryKey: ['fixtures', sessionId],
    queryFn: () => sessionsApi.fixtures(sessionId!),
    enabled: !!sessionId && (!!fixtureResult || openedSession?.generated_at != null),
  })

  const qc = useQueryClient()

  const createSessionMut = useMutation({
    mutationFn: async () => {
      if (!eventId) throw new Error('Select an event first')
      return sessionsApi.create(eventId, {
        session_date: sessionForm.session_date,
        num_tables: Number(sessionForm.num_tables),
        session_minutes: Number(sessionForm.session_minutes),
        match_format: sessionForm.match_format || undefined,
      })
    },
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ['sessions', eventId] })
      setSessionId(s.session_id)
      setShowNewForm(false)
      setError(null)
    },
    onError: (e: Error) => setError(e.message),
  })

  const generateMut = useMutation({
    mutationFn: () => {
      if (!sessionId) throw new Error('No session selected')
      return sessionsApi.generateFixtures(sessionId, Array.from(selectedPlayers))
    },
    onSuccess: r => {
      setFixtureResult(r)
      qc.invalidateQueries({ queryKey: ['sessions', eventId] })
      qc.invalidateQueries({ queryKey: ['fixtures', sessionId] })
    },
    onError: (e: Error) => setError(e.message),
  })

  const completeSessionMut = useMutation({
    mutationFn: (sid: string) => sessionsApi.updateStatus(sid, 'COMPLETED'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions', eventId] }),
  })

  const [ratingsResult, setRatingsResult] = useState<{ matches_rated: number; tier_changes: { player_id: string; tier_before: string; tier_after: string }[] } | null>(null)
  const applyRatingsMut = useMutation({
    mutationFn: (sid: string) => sessionsApi.applyRatings(sid),
    onSuccess: (r) => {
      setRatingsResult({ matches_rated: r.matches_rated, tier_changes: r.tier_changes })
      qc.invalidateQueries({ queryKey: ['academy-leaderboard', academyId] })
      qc.invalidateQueries({ queryKey: ['fixtures', sessionId] })
    },
    onError: (e: Error) => setError(e.message),
  })

  // Auto-complete session when all non-BYE slots are played (handles both live and retroactive cases)
  const allSlotsPlayed = !!fixturesQ.data?.slots.length &&
    fixturesQ.data.slots.filter(s => s.status !== 'BYE').every(s => s.status === 'PLAYED')

  useEffect(() => {
    if (
      allSlotsPlayed &&
      sessionId &&
      openedSession?.status !== 'COMPLETED' &&
      openedSession?.status !== 'CANCELLED' &&
      !completeSessionMut.isPending
    ) {
      completeSessionMut.mutate(sessionId)
    }
  }, [allSlotsPlayed, sessionId, openedSession?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  function togglePlayer(id: string) {
    setSelectedPlayers(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function openSession(s: SessionSummary) {
    setSessionId(s.session_id)
    setShowNewForm(false)
    setSelectedPlayers(new Set())
    setFixtureResult(null)
    setError(null)
  }

  function backToList() {
    setSessionId(null)
    setShowNewForm(false)
    setSelectedPlayers(new Set())
    setFixtureResult(null)
    setError(null)
  }

  const intraEvents = eventsQ.data?.items.filter(e => e.scheduling_mode === 'INTRA_ACADEMY') ?? []
  const roster = rosterQ.data?.items ?? []
  const sessions = sessionsQ.data ?? []

  const MATCH_CAT_COLOR: Record<string, string> = {
    COMPETITIVE: 'text-blue-400',
    STRETCH: 'text-purple-400',
    ANCHOR: 'text-green-400',
    BYE: 'text-gray-500',
  }

  const SESSION_STATUS_COLOR: Record<string, string> = {
    SCHEDULED: 'bg-yellow-800 text-yellow-100',
    IN_PROGRESS: 'bg-blue-800 text-blue-100',
    COMPLETED: 'bg-green-800 text-green-100',
    CANCELLED: 'bg-gray-700 text-gray-300',
  }

  const hasFixtures = !!fixtureResult || (openedSession?.generated_at != null)

  return (
    <div className="space-y-5">
      {error && <ErrorMsg message={error} />}

      {/* ── Event picker (always visible) ─────────────────────────────── */}
      <div>
        <label className="block text-sm text-gray-400 mb-1">Event</label>
        <select value={eventId} onChange={e => { setEventId(e.target.value); backToList() }}
          className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
          <option value="">Select an event…</option>
          {intraEvents.map(ev => (
            <option key={ev.event_id} value={ev.event_id}>{ev.name}</option>
          ))}
        </select>
      </div>

      {/* ── Session list ───────────────────────────────────────────────── */}
      {eventId && !sessionId && (
        <>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">
              {sessionsQ.isLoading ? 'Loading sessions…' : `${sessions.length} session${sessions.length !== 1 ? 's' : ''}`}
            </span>
            <button onClick={() => setShowNewForm(v => !v)}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg">
              {showNewForm ? 'Cancel' : '+ New Session'}
            </button>
          </div>

          {showNewForm && (
            <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Date</label>
                  <input type="date" value={sessionForm.session_date}
                    onChange={e => setSessionForm(f => ({ ...f, session_date: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Tables</label>
                  <input type="number" min={1} value={sessionForm.num_tables}
                    onChange={e => setSessionForm(f => ({ ...f, num_tables: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Minutes</label>
                  <input type="number" min={30} step={30} value={sessionForm.session_minutes}
                    onChange={e => setSessionForm(f => ({ ...f, session_minutes: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Match format <span className="text-gray-600">(blank = event default)</span></label>
                <select value={sessionForm.match_format} onChange={e => setSessionForm(f => ({ ...f, match_format: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
                  <option value="">Use event default</option>
                  {MATCH_FORMATS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </div>
              <button onClick={() => createSessionMut.mutate()} disabled={createSessionMut.isPending || !sessionForm.session_date}
                className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg disabled:opacity-50">
                {createSessionMut.isPending ? 'Creating…' : 'Create Session'}
              </button>
            </div>
          )}

          <div className="space-y-2">
            {sessions.map(s => (
              <button key={s.session_id} onClick={() => openSession(s)}
                className="w-full text-left bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl px-4 py-3 transition-colors">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="font-medium text-white text-sm">{s.session_date}</div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {s.match_format.replace(/_/g, ' ')} · {s.num_tables} table{s.num_tables !== 1 ? 's' : ''} · {s.session_minutes} min
                      {s.generated_at ? ` · ${s.present_player_count} players` : ' · fixtures pending'}
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${SESSION_STATUS_COLOR[s.status] ?? ''}`}>
                    {s.status}
                  </span>
                </div>
              </button>
            ))}
            {!sessionsQ.isLoading && sessions.length === 0 && (
              <p className="text-gray-500 text-sm">No sessions yet. Create one to start.</p>
            )}
          </div>
        </>
      )}

      {/* ── Session detail (player selection + fixtures) ───────────────── */}
      {sessionId && (
        <>
          <button onClick={backToList} className="text-xs text-gray-400 hover:text-white flex items-center gap-1">
            ← Back to sessions
          </button>

          {openedSession && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-white text-sm">{openedSession.session_date}</div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {openedSession.match_format.replace(/_/g, ' ')} · {openedSession.num_tables} tables · {openedSession.session_minutes} min
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${SESSION_STATUS_COLOR[openedSession.status] ?? ''}`}>
                    {openedSession.status}
                  </span>
                  {openedSession.status === 'COMPLETED' && (
                    <button
                      onClick={() => { setRatingsResult(null); applyRatingsMut.mutate(sessionId!) }}
                      disabled={applyRatingsMut.isPending}
                      className="px-3 py-1 bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50">
                      {applyRatingsMut.isPending ? 'Applying…' : '⚡ Apply Ratings'}
                    </button>
                  )}
                </div>
              </div>

              {ratingsResult && (
                <div className="bg-gray-800 rounded-lg px-3 py-2 text-xs space-y-1">
                  {ratingsResult.matches_rated === 0 ? (
                    <span className="text-gray-400">Ratings already up to date — no new matches to process.</span>
                  ) : (
                    <>
                      <div className="text-green-400 font-medium">
                        ✓ Ratings applied for {ratingsResult.matches_rated} match{ratingsResult.matches_rated !== 1 ? 'es' : ''}.
                      </div>
                      {ratingsResult.tier_changes.length > 0 && (
                        <div className="text-yellow-300">
                          🏆 {ratingsResult.tier_changes.length} tier change{ratingsResult.tier_changes.length !== 1 ? 's' : ''} —
                          check the Roster for updated ratings.
                        </div>
                      )}
                      {ratingsResult.tier_changes.length === 0 && (
                        <div className="text-gray-400">No tier changes. Check the Roster tab for updated ratings.</div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {!hasFixtures && (
            <>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm text-gray-400">Mark players present ({selectedPlayers.size} selected)</label>
                  <button type="button" onClick={() => setSelectedPlayers(new Set(roster.map((p: LeaderboardEntry) => p.player_id)))}
                    className="text-xs text-blue-400 hover:text-blue-300">Select all</button>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-xl max-h-64 overflow-y-auto divide-y divide-gray-800">
                  {roster.map((p: LeaderboardEntry) => (
                    <label key={p.player_id} className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-gray-800">
                      <input type="checkbox" checked={selectedPlayers.has(p.player_id)}
                        onChange={() => togglePlayer(p.player_id)} className="accent-blue-500 w-4 h-4" />
                      <span className="flex-1 text-sm text-white">{p.name}</span>
                      <span className="text-xs text-gray-400 font-mono">{Math.round(p.current_rating)}</span>
                      <TierBadge tier={p.tier} />
                    </label>
                  ))}
                </div>
              </div>
              <button onClick={() => generateMut.mutate()}
                disabled={generateMut.isPending || selectedPlayers.size < 2}
                className="w-full py-2.5 bg-purple-700 hover:bg-purple-600 text-white font-semibold rounded-lg disabled:opacity-50">
                {generateMut.isPending ? 'Generating…' : `Generate Fixtures for ${selectedPlayers.size} players`}
              </button>
            </>
          )}

          {resultSlot && openedSession && (
            <ResultEntryModal
              slot={resultSlot}
              sessionId={sessionId!}
              eventId={eventId}
              matchFormat={openedSession.match_format}
              sessionDate={openedSession.session_date}
              onClose={() => setResultSlot(null)}
              onSuccess={() => {
                setResultSlot(null)
                qc.invalidateQueries({ queryKey: ['fixtures', sessionId] })
                qc.invalidateQueries({ queryKey: ['sessions', eventId] })
                qc.invalidateQueries({ queryKey: ['academy-leaderboard', academyId] })
              }}
            />
          )}

          {hasFixtures && (
            <div className="space-y-4">
              {fixtureResult && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-wrap gap-6">
                  <div><div className="text-xs text-gray-500 mb-1">Phase</div><div className="font-semibold text-white">{fixtureResult.bootstrap_phase}</div></div>
                  <div><div className="text-xs text-gray-500 mb-1">Matches per player</div><div className="font-semibold text-white">{fixtureResult.matches_per_player}</div></div>
                  <div><div className="text-xs text-gray-500 mb-1">Total slots</div><div className="font-semibold text-white">{fixtureResult.fixture_slots_created}</div></div>
                </div>
              )}
              {fixturesQ.isLoading && <Spinner />}
              {fixturesQ.data && (() => {
                const byRound = fixturesQ.data.slots.reduce<Record<number, typeof fixturesQ.data.slots>>((acc, slot) => {
                  ;(acc[slot.round_number] ??= []).push(slot)
                  return acc
                }, {})
                return Object.entries(byRound).map(([rn, slots]) => (
                  <div key={rn}>
                    <div className="text-xs text-gray-500 mb-2 font-semibold uppercase tracking-wide">Round {rn}</div>
                    <div className="space-y-1">
                      {slots.map(slot => (
                        <div key={slot.slot_id}
                          className={`bg-gray-900 border border-gray-800 rounded-lg px-4 py-2.5 flex items-center justify-between gap-3 ${slot.status === 'BYE' ? 'opacity-50' : ''}`}>
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span className={`text-xs font-semibold shrink-0 ${MATCH_CAT_COLOR[slot.match_category] ?? 'text-gray-400'}`}>
                              {slot.match_category}
                            </span>
                            <span className="text-white text-sm truncate">{slot.player_a.name}</span>
                            {slot.player_b
                              ? <><span className="text-gray-500 text-xs shrink-0">vs</span><span className="text-white text-sm truncate">{slot.player_b.name}</span></>
                              : <span className="text-gray-500 text-xs italic">BYE</span>
                            }
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <div className="hidden sm:flex items-center gap-2 text-xs text-gray-500">
                              <span className="font-mono">{Math.round(slot.player_a.current_rating)}</span>
                              {slot.player_b && <span className="font-mono">{Math.round(slot.player_b.current_rating)}</span>}
                            </div>
                            {slot.player_b && slot.status === 'SCHEDULED' && (
                              <button
                                onClick={() => setResultSlot(slot)}
                                className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition-colors">
                                Enter Result
                              </button>
                            )}
                            {slot.status === 'PLAYED' && slot.match_result && (
                              <div className="flex items-center gap-1.5 text-xs shrink-0">
                                <span className={`font-mono font-bold ${slot.match_result.winner_id === slot.player_a.player_id ? 'text-green-400' : 'text-gray-400'}`}>
                                  {slot.match_result.sets_won_a}
                                </span>
                                <span className="text-gray-600">–</span>
                                <span className={`font-mono font-bold ${slot.match_result.winner_id === slot.player_b?.player_id ? 'text-green-400' : 'text-gray-400'}`}>
                                  {slot.match_result.sets_won_b}
                                </span>
                                {slot.match_result.is_retirement && <span className="text-gray-500 text-xs">(R)</span>}
                              </div>
                            )}
                            {slot.status === 'PLAYED' && !slot.match_result && (
                              <span className="text-xs text-green-400 font-medium">✓</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              })()}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Roster helpers ────────────────────────────────────────────────────────────

function activityDotClass(lastMatchDate: string | null): string {
  if (!lastMatchDate) return 'bg-red-600'
  const days = Math.floor((Date.now() - new Date(lastMatchDate).getTime()) / 86_400_000)
  if (days <= 7) return 'bg-green-500'
  if (days <= 21) return 'bg-yellow-500'
  return 'bg-red-500'
}

function activityLabel(lastMatchDate: string | null): string {
  if (!lastMatchDate) return 'Never played'
  const days = Math.floor((Date.now() - new Date(lastMatchDate).getTime()) / 86_400_000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days <= 7) return `${days}d ago`
  return `${Math.round(days / 7)}w ago`
}

// ── Roster ────────────────────────────────────────────────────────────────────

function RosterTab({ academyId }: { academyId: string }) {
  const [selectedPlayer, setSelectedPlayer] = useState<LeaderboardEntry | null>(null)

  const q = useQuery({
    queryKey: ['academy-leaderboard', academyId],
    queryFn: () => academiesApi.leaderboard(academyId, { limit: 100 }),
  })
  const asiQ = useQuery({
    queryKey: ['asi-history', academyId],
    queryFn: () => academiesApi.asiHistory(academyId, 6),
  })

  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorMsg message={(q.error as Error).message} />

  const latestASI = asiQ.data?.items?.[0]

  return (
    <div className="space-y-4">
      {latestASI && (
        <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-4 flex items-center gap-6">
          <div>
            <div className="text-xs text-blue-400 mb-1">Academy Strength Index (ASI)</div>
            <div className="text-3xl font-bold font-mono text-white">
              {latestASI.asi_value !== null ? Math.round(latestASI.asi_value) : '—'}
            </div>
          </div>
          <div>
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
              latestASI.calculation_basis === 'COMPUTED' ? 'bg-green-700 text-green-100' :
              latestASI.calculation_basis === 'FROZEN' ? 'bg-blue-700 text-blue-100' : 'bg-gray-700 text-gray-300'
            }`}>{latestASI.calculation_basis}</span>
            <div className="text-xs text-gray-500 mt-1">{latestASI.qualifying_player_count} qualifying players</div>
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-900 text-gray-400 text-left">
              <th className="px-4 py-3 w-10">#</th>
              <th className="px-4 py-3">Player</th>
              <th className="px-4 py-3">Rating</th>
              <th className="px-4 py-3">Tier</th>
              <th className="px-4 py-3 hidden lg:table-cell">Gender</th>
              <th className="px-4 py-3 hidden lg:table-cell">Age Cat.</th>
              <th className="px-4 py-3 hidden md:table-cell">Matches</th>
              <th className="px-4 py-3 hidden md:table-cell">Activity</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {q.data?.items.map(row => (
              <tr key={row.player_id} className="hover:bg-gray-900/50">
                <td className="px-4 py-3 text-gray-500">{row.rank}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => setSelectedPlayer(row)}
                    className="text-blue-400 hover:text-blue-300 font-medium text-left">
                    {row.name}
                  </button>
                  {row.is_provisional && <span className="ml-1 text-yellow-500 text-xs">(P)</span>}
                </td>
                <td className="px-4 py-3 font-mono font-semibold text-white">{Math.round(row.current_rating)}</td>
                <td className="px-4 py-3"><TierBadge tier={row.tier} /></td>
                <td className="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">
                  {row.gender === 'MALE' ? 'M' : row.gender === 'FEMALE' ? 'F' : '—'}
                </td>
                <td className="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">
                  {row.age_group ?? '—'}
                </td>
                <td className="px-4 py-3 hidden md:table-cell text-gray-400">{row.rated_matches}</td>
                <td className="px-4 py-3 hidden md:table-cell">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${activityDotClass(row.last_match_date)}`} />
                    <span className="text-gray-500 text-xs">{activityLabel(row.last_match_date)}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedPlayer && (
        <PlayerModal player={selectedPlayer} onClose={() => setSelectedPlayer(null)} />
      )}
    </div>
  )
}

// ── Player autocomplete ───────────────────────────────────────────────────────

function PlayerPicker({
  label,
  academyId,
  value,
  onChange,
}: {
  label: string
  academyId: string
  value: PlayerSearchResult | null
  onChange: (p: PlayerSearchResult | null) => void
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [results, setResults] = useState<PlayerSearchResult[]>([])

  function handleInput(v: string) {
    setQ(v)
    if (v === '') { onChange(null); setResults([]); return }
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      const r = await playersApi.search(v, academyId)
      setResults(r.items)
      setOpen(true)
    }, 250)
  }

  function pick(p: PlayerSearchResult) {
    onChange(p)
    setQ(p.name)
    setOpen(false)
  }

  return (
    <div className="relative">
      <label className="block text-sm text-gray-400 mb-1">{label}</label>
      {value && (
        <div className="flex items-center gap-2 mb-1 text-xs text-gray-400">
          <span className="text-white font-medium">{value.name}</span>
          <span className="font-mono">{Math.round(value.current_rating)}</span>
          <button type="button" onClick={() => { onChange(null); setQ('') }}
            className="text-gray-600 hover:text-red-400">✕</button>
        </div>
      )}
      {!value && (
        <input type="text" value={q} onChange={e => handleInput(e.target.value)}
          onFocus={() => q && setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Type player name…"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 placeholder-gray-600" />
      )}
      {open && results.length > 0 && (
        <div className="absolute z-20 w-full bg-gray-800 border border-gray-700 rounded-lg mt-1 shadow-xl max-h-48 overflow-y-auto">
          {results.map(p => (
            <button key={p.player_id} type="button" onMouseDown={() => pick(p)}
              className="w-full text-left px-3 py-2 hover:bg-gray-700 flex items-center justify-between text-sm">
              <span className="text-white">{p.name}</span>
              <span className="text-gray-400 font-mono text-xs">{Math.round(p.current_rating)}</span>
            </button>
          ))}
        </div>
      )}
      {open && results.length === 0 && q.length >= 2 && (
        <div className="absolute z-20 w-full bg-gray-800 border border-gray-700 rounded-lg mt-1 px-3 py-2 text-sm text-gray-500">
          No players found
        </div>
      )}
    </div>
  )
}

// ── Submit match ──────────────────────────────────────────────────────────────

const FORMATS = ['BEST_OF_3', 'BEST_OF_5', 'BEST_OF_7']

function SubmitMatchTab({ academyId }: { academyId: string }) {
  const [playerA, setPlayerA] = useState<PlayerSearchResult | null>(null)
  const [playerB, setPlayerB] = useState<PlayerSearchResult | null>(null)
  const [form, setForm] = useState({
    event_id: '',
    match_format: 'BEST_OF_3',
    sets_won_a: '',
    sets_won_b: '',
    match_date: new Date().toISOString().slice(0, 10),
    is_retirement: false,
  })
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const maxSets: Record<string, number> = { BEST_OF_3: 2, BEST_OF_5: 3, BEST_OF_7: 4 }

  const mutation = useMutation({
    mutationFn: () => {
      if (!playerA || !playerB) throw new Error('Select both players')
      if (!form.event_id) throw new Error('Event ID is required')
      return matchesApi.submit({
        event_id: form.event_id,
        player_a_id: playerA.player_id,
        player_b_id: playerB.player_id,
        match_format: form.match_format,
        sets_won_a: Number(form.sets_won_a),
        sets_won_b: Number(form.sets_won_b),
        match_date: form.match_date,
        is_retirement: form.is_retirement,
      })
    },
    onSuccess: m => {
      const winner = m.winner_id === m.player_a.player_id ? m.player_a.name : m.player_b.name
      setResult(`Match submitted! Winner: ${winner}. Status: ${m.confirmation_status}`)
      setError(null)
      setPlayerA(null); setPlayerB(null)
      setForm(f => ({ ...f, sets_won_a: '', sets_won_b: '' }))
    },
    onError: (e: Error) => { setError(e.message); setResult(null) },
  })

  const max = maxSets[form.match_format]

  return (
    <div className="max-w-md space-y-4">
      {result && <div className="bg-green-900/40 border border-green-700 text-green-300 rounded p-3 text-sm">{result}</div>}
      {error && <ErrorMsg message={error} />}

      <PlayerPicker label="Player A" academyId={academyId} value={playerA} onChange={setPlayerA} />
      <PlayerPicker label="Player B" academyId={academyId} value={playerB} onChange={setPlayerB} />

      <div>
        <label className="block text-sm text-gray-400 mb-1">Match Format</label>
        <select value={form.match_format} onChange={e => setForm(f => ({ ...f, match_format: e.target.value }))}
          className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
          {FORMATS.map(f => <option key={f} value={f}>{f.replace(/_/g, ' ')} (first to {maxSets[f]})</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm text-gray-400 mb-1">
            {playerA ? playerA.name.split(' ')[0] : 'Player A'} sets won
          </label>
          <input type="number" min={0} max={max} value={form.sets_won_a}
            onChange={e => setForm(f => ({ ...f, sets_won_a: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-center text-lg font-mono" />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">
            {playerB ? playerB.name.split(' ')[0] : 'Player B'} sets won
          </label>
          <input type="number" min={0} max={max} value={form.sets_won_b}
            onChange={e => setForm(f => ({ ...f, sets_won_b: e.target.value }))}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-center text-lg font-mono" />
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Match Date</label>
        <input type="date" value={form.match_date}
          onChange={e => setForm(f => ({ ...f, match_date: e.target.value }))}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Event ID</label>
        <input type="text" value={form.event_id} placeholder="Paste the event UUID"
          onChange={e => setForm(f => ({ ...f, event_id: e.target.value }))}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm font-mono placeholder-gray-600" />
        <p className="text-xs text-gray-500 mt-1">Find event IDs in Admin → Events</p>
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
        <input type="checkbox" checked={form.is_retirement}
          onChange={e => setForm(f => ({ ...f, is_retirement: e.target.checked }))}
          className="w-4 h-4 accent-blue-500" />
        Retirement / walkover
      </label>

      <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !playerA || !playerB}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors disabled:opacity-50">
        {mutation.isPending ? 'Submitting…' : 'Submit Match'}
      </button>
    </div>
  )
}

// ── Result entry modal ────────────────────────────────────────────────────────

const MAX_SETS: Record<string, number> = { BEST_OF_3: 2, BEST_OF_5: 3, BEST_OF_7: 4 }

function ResultEntryModal({
  slot, sessionId, eventId, matchFormat, sessionDate, onClose, onSuccess,
}: {
  slot: FixtureSlot
  sessionId: string
  eventId: string
  matchFormat: string
  sessionDate: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [setsA, setSetsA] = useState('')
  const [setsB, setSetsB] = useState('')
  const [isRetirement, setIsRetirement] = useState(false)
  const [matchDate, setMatchDate] = useState(sessionDate)
  const [error, setError] = useState<string | null>(null)

  const max = MAX_SETS[matchFormat] ?? 2
  const nA = Number(setsA), nB = Number(setsB)
  const isValid = setsA !== '' && setsB !== '' && nA !== nB && (
    isRetirement
      ? (nA + nB > 0 && nA <= max && nB <= max)
      : ((nA === max && nB < max) || (nB === max && nA < max))
  )

  const mutation = useMutation({
    mutationFn: () => matchesApi.submit({
      event_id: eventId,
      session_id: sessionId,
      fixture_slot_id: slot.slot_id,
      player_a_id: slot.player_a.player_id,
      player_b_id: slot.player_b!.player_id,
      match_format: matchFormat,
      sets_won_a: nA,
      sets_won_b: nB,
      match_date: matchDate,
      is_retirement: isRetirement,
    }),
    onSuccess: () => onSuccess(),
    onError: (e: Error) => setError(e.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 w-full max-w-sm mx-4 space-y-4"
        onClick={e => e.stopPropagation()}>

        <div>
          <h3 className="text-white font-semibold text-base">Enter Result</h3>
          <p className="text-sm text-gray-300 mt-1">
            {slot.player_a.name} <span className="text-gray-500">vs</span> {slot.player_b!.name}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {matchFormat.replace(/_/g, ' ')} · Table {slot.table_number}
            · first to {max} sets
          </p>
        </div>

        {error && <ErrorMsg message={error} />}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1 truncate">{slot.player_a.name.split(' ')[0]} sets won</label>
            <input type="number" min={0} max={max} value={setsA}
              onChange={e => setSetsA(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-3 text-white text-center text-2xl font-mono focus:outline-none focus:border-blue-500" />
            <div className="text-center text-xs text-gray-600 mt-1 font-mono">
              {Math.round(slot.player_a.current_rating)}
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1 truncate">{slot.player_b!.name.split(' ')[0]} sets won</label>
            <input type="number" min={0} max={max} value={setsB}
              onChange={e => setSetsB(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-3 text-white text-center text-2xl font-mono focus:outline-none focus:border-blue-500" />
            <div className="text-center text-xs text-gray-600 mt-1 font-mono">
              {Math.round(slot.player_b!.current_rating)}
            </div>
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

        <div className="flex gap-2 pt-1">
          <button onClick={onClose}
            className="flex-1 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors">
            Cancel
          </button>
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !isValid}
            className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-sm transition-colors disabled:opacity-50">
            {mutation.isPending ? 'Submitting…' : 'Submit Result'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Player modal ─────────────────────────────────────────────────────────────

function PlayerModal({ player, onClose }: { player: LeaderboardEntry; onClose: () => void }) {
  const [tab, setTab] = useState<'overview' | 'history'>('overview')
  const [histPage, setHistPage] = useState(0)
  const PAGE_SIZE = 15

  const statsQ = useQuery({
    queryKey: ['player-computed', player.player_id],
    queryFn: () => playersApi.computedStats(player.player_id),
  })
  const velocityQ = useQuery({
    queryKey: ['player-velocity', player.player_id, '1m'],
    queryFn: () => playersApi.velocity(player.player_id, '1m'),
  })
  const recentQ = useQuery({
    queryKey: ['player-history-recent', player.player_id],
    queryFn: () => playersApi.ratingHistory(player.player_id, { limit: 5 }),
  })
  const histQ = useQuery({
    queryKey: ['player-history-full', player.player_id, histPage],
    queryFn: () => playersApi.ratingHistory(player.player_id, { limit: PAGE_SIZE, offset: histPage * PAGE_SIZE }),
    enabled: tab === 'history',
  })

  const totalPages = histQ.data ? Math.ceil(histQ.data.total / PAGE_SIZE) : 0

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 p-4"
      onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[88vh] flex flex-col"
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="flex items-start justify-between px-5 pt-5 pb-4 border-b border-gray-800 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-2.5 h-2.5 rounded-full shrink-0 mt-1 ${activityDotClass(player.last_match_date)}`} />
            <div className="min-w-0">
              <div className="text-white font-bold text-lg leading-tight truncate">{player.name}</div>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <TierBadge tier={player.tier} />
                {player.is_provisional && (
                  <span className="text-xs text-yellow-400 bg-yellow-900/30 border border-yellow-800 px-2 py-0.5 rounded">Provisional</span>
                )}
                <span className="text-xs text-gray-500">#{player.rank} · {activityLabel(player.last_match_date)}</span>
              </div>
            </div>
          </div>
          <div className="flex items-start gap-4 shrink-0 ml-3">
            <div className="text-right">
              <div className="text-2xl font-bold font-mono text-white leading-none">{Math.round(player.current_rating)}</div>
              <div className="text-xs text-gray-500 mt-0.5">rating</div>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-white text-lg leading-none mt-0.5">✕</button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-800 shrink-0">
          {(['overview', 'history'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === t ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-white'
              }`}>
              {t === 'overview' ? 'Overview' : 'Match History'}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">

          {/* ── Overview tab ── */}
          {tab === 'overview' && (
            <div className="space-y-5">

              {/* CR + meta stats */}
              {statsQ.isLoading && <Spinner />}
              {statsQ.data && (
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs text-gray-400">Confidence Ratio</span>
                      <span className="text-xs text-gray-500">{Math.round(statsQ.data.confidence_ratio * 100)}%</span>
                    </div>
                    <CRBar value={statsQ.data.confidence_ratio} />
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Rated</div>
                      <div className="text-white font-semibold font-mono">{player.rated_matches}</div>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Age group</div>
                      <div className="text-white font-semibold text-sm">{statsQ.data.age_group}</div>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Inactive</div>
                      <div className={`font-semibold text-sm font-mono ${
                        statsQ.data.weeks_inactive != null && statsQ.data.weeks_inactive > 4
                          ? 'text-red-400' : 'text-white'
                      }`}>
                        {statsQ.data.weeks_inactive != null ? `${statsQ.data.weeks_inactive.toFixed(1)}w` : '—'}
                      </div>
                    </div>
                  </div>
                  {statsQ.data.is_provisional && (
                    <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-lg px-3 py-2 text-xs text-yellow-300">
                      Provisional — {statsQ.data.provisional_matches_remaining} more rated match{statsQ.data.provisional_matches_remaining !== 1 ? 'es' : ''} needed to exit
                    </div>
                  )}
                </div>
              )}

              {/* 30-day velocity */}
              {velocityQ.isLoading && !statsQ.isLoading && <Spinner />}
              {velocityQ.data && (
                <div>
                  <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide font-semibold">Last 30 days</div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Rating Δ</div>
                      <div className={`text-xl font-bold font-mono ${velocityQ.data.rating_change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {velocityQ.data.rating_change >= 0 ? '+' : ''}{Math.round(velocityQ.data.rating_change)}
                      </div>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Win rate</div>
                      <div className="text-xl font-bold text-white">
                        {velocityQ.data.matches_played > 0
                          ? `${Math.round(velocityQ.data.win_rate * 100)}%`
                          : '—'}
                      </div>
                      <div className="text-xs text-gray-600 mt-0.5">{velocityQ.data.matches_played} matches</div>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Stretch win rate</div>
                      <div className="text-xl font-bold text-purple-400">
                        {velocityQ.data.stretch_win_rate != null
                          ? `${Math.round(velocityQ.data.stretch_win_rate * 100)}%`
                          : '—'}
                      </div>
                      <div className="text-xs text-gray-600 mt-0.5">{velocityQ.data.stretch_matches} stretch</div>
                    </div>
                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Tier changes</div>
                      <div className={`text-xl font-bold ${velocityQ.data.tier_changes > 0 ? 'text-yellow-400' : 'text-gray-400'}`}>
                        {velocityQ.data.tier_changes > 0 ? `+${velocityQ.data.tier_changes}` : velocityQ.data.tier_changes}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Recent form pips */}
              {recentQ.data && (() => {
                const played = recentQ.data.items.filter(h => !h.is_rollback)
                return played.length > 0 ? (
                  <div>
                    <div className="text-xs text-gray-500 mb-2 uppercase tracking-wide font-semibold">Recent form</div>
                    <div className="flex items-end gap-2 flex-wrap">
                      {played.slice(0, 5).map(h => (
                        <div key={h.history_id} className="flex flex-col items-center gap-1">
                          <div className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold ${
                            h.result === 'WIN' ? 'bg-green-800 text-green-200' : 'bg-red-900/80 text-red-300'
                          }`}>
                            {h.result === 'WIN' ? 'W' : 'L'}
                          </div>
                          <div className={`text-xs font-mono font-semibold ${h.delta >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                            {h.delta >= 0 ? '+' : ''}{Math.round(h.delta)}
                          </div>
                          <div className="text-xs text-gray-600 text-center leading-tight max-w-[4rem] truncate">
                            {h.opponent_name?.split(' ')[0] ?? '—'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-gray-500">No rated matches yet — apply ratings after sessions.</p>
                )
              })()}
            </div>
          )}

          {/* ── History tab ── */}
          {tab === 'history' && (
            <div className="space-y-3">
              {histQ.isLoading && <Spinner />}
              {histQ.data && (
                <>
                  {histQ.data.items.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-12">No rated matches yet.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-gray-500 border-b border-gray-800 text-right">
                            <th className="text-left pb-2 pr-3 font-medium">Date</th>
                            <th className="text-left pb-2 pr-3 font-medium">Opponent</th>
                            <th className="text-left pb-2 pr-3 font-medium">Result</th>
                            <th className="pb-2 pr-2 font-medium">Before</th>
                            <th className="pb-2 pr-2 font-medium">After</th>
                            <th className="pb-2 pr-2 font-medium">Δ</th>
                            <th className="pb-2 pr-2 font-medium">K-eff</th>
                            <th className="pb-2 font-medium">Exp.</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800/40">
                          {histQ.data.items.map(h => (
                            <tr key={h.history_id} className={`${h.is_rollback ? 'opacity-35' : 'hover:bg-gray-800/30'}`}>
                              <td className="py-2 pr-3 text-gray-400 whitespace-nowrap">
                                {h.match_date?.slice(0, 10) ?? '—'}
                                {h.is_rollback && <span className="ml-1 text-gray-600 italic">(void)</span>}
                              </td>
                              <td className="py-2 pr-3 text-white max-w-[8rem] truncate">{h.opponent_name ?? '—'}</td>
                              <td className="py-2 pr-3">
                                <span className={`px-1.5 py-0.5 rounded font-bold ${
                                  h.result === 'WIN' ? 'bg-green-800/60 text-green-300' : 'bg-red-900/60 text-red-300'
                                }`}>
                                  {h.result}
                                </span>
                              </td>
                              <td className="py-2 pr-2 text-right font-mono text-gray-500">{Math.round(h.rating_before)}</td>
                              <td className="py-2 pr-2 text-right font-mono text-white">{Math.round(h.rating_after)}</td>
                              <td className={`py-2 pr-2 text-right font-mono font-semibold ${h.delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {h.delta >= 0 ? '+' : ''}{h.delta.toFixed(1)}
                              </td>
                              <td className="py-2 pr-2 text-right text-gray-500">{h.k_eff?.toFixed(1) ?? '—'}</td>
                              <td className="py-2 text-right text-gray-500">{h.expected_score?.toFixed(2) ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between pt-1">
                      <button onClick={() => setHistPage(p => Math.max(0, p - 1))} disabled={histPage === 0}
                        className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg disabled:opacity-40 transition-colors">
                        ← Prev
                      </button>
                      <span className="text-xs text-gray-500">Page {histPage + 1} of {totalPages}</span>
                      <button onClick={() => setHistPage(p => Math.min(totalPages - 1, p + 1))} disabled={histPage >= totalPages - 1}
                        className="px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg disabled:opacity-40 transition-colors">
                        Next →
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Register player ───────────────────────────────────────────────────────────

const SEEDING_LEVELS = ['UNSEEDED', 'DISTRICT', 'STATE', 'NATIONAL']

function RegisterPlayerTab({ academyId }: { academyId: string }) {
  const [form, setForm] = useState({
    name: '', date_of_birth: '', gender: '',
    seeding_level: 'UNSEEDED', seeding_reference: '', virtual_matches: '0',
    nationality: 'India', guardian_name: '', guardian_phone: '', contact_email: '',
  })
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => playersApi.create({
      name: form.name,
      date_of_birth: form.date_of_birth,
      gender: form.gender,
      primary_academy_id: academyId,
      seeding_level: form.seeding_level,
      seeding_reference: form.seeding_reference || undefined,
      virtual_matches: Number(form.virtual_matches),
      nationality: form.nationality || undefined,
      guardian_name: form.guardian_name || undefined,
      guardian_phone: form.guardian_phone || undefined,
      contact_email: form.contact_email || undefined,
    }),
    onSuccess: p => {
      setSuccess(`${p.name} registered with rating ${Math.round(p.current_rating)}`)
      setError(null)
      setForm({
        name: '', date_of_birth: '', gender: '',
        seeding_level: 'UNSEEDED', seeding_reference: '', virtual_matches: '0',
        nationality: 'India', guardian_name: '', guardian_phone: '', contact_email: '',
      })
      qc.invalidateQueries({ queryKey: ['academy-leaderboard', academyId] })
    },
    onError: (e: Error) => { setError(e.message); setSuccess(null) },
  })

  function set(k: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm(f => ({ ...f, [k]: e.target.value }))
  }

  const canSubmit = !mutation.isPending && !!form.name && !!form.date_of_birth && !!form.gender
    && (form.seeding_level === 'UNSEEDED' || !!form.seeding_reference)

  return (
    <div className="max-w-md space-y-4">
      {success && <div className="bg-green-900/40 border border-green-700 text-green-300 rounded p-3 text-sm">{success}</div>}
      {error && <ErrorMsg message={error} />}

      <div>
        <label className="block text-sm text-gray-400 mb-1">Full name <span className="text-red-400">*</span></label>
        <input type="text" required value={form.name} onChange={set('name')} placeholder="Arjun Sharma"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Date of birth <span className="text-red-400">*</span> <span className="text-gray-500 text-xs">(must be 6–18 years old)</span></label>
        <input type="date" required value={form.date_of_birth} onChange={set('date_of_birth')}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Gender <span className="text-red-400">*</span></label>
        <select value={form.gender} onChange={set('gender')}
          className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
          <option value="">Select gender…</option>
          <option value="MALE">Male</option>
          <option value="FEMALE">Female</option>
        </select>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Seeding level <span className="text-red-400">*</span></label>
        <select value={form.seeding_level} onChange={set('seeding_level')}
          className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
          {SEEDING_LEVELS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <p className="text-xs text-gray-500 mt-1">
          {form.seeding_level === 'UNSEEDED' && 'Starts at 1000 rating · 0 virtual matches · enters provisional phase (15 matches)'}
          {form.seeding_level === 'DISTRICT' && 'Starts at 1200 rating · 10 virtual matches · skips provisional phase'}
          {form.seeding_level === 'STATE' && 'Starts at 1400 rating · 20 virtual matches · skips provisional phase'}
          {form.seeding_level === 'NATIONAL' && 'Starts at 1500 rating · 30 virtual matches · skips provisional phase'}
        </p>
      </div>

      {form.seeding_level !== 'UNSEEDED' && (
        <div>
          <label className="block text-sm text-gray-400 mb-1">Seeding reference <span className="text-red-400">*</span> <span className="text-gray-500 text-xs">(certificate / ranking ID)</span></label>
          <input type="text" value={form.seeding_reference} onChange={set('seeding_reference')}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-400 mb-1">Virtual matches <span className="text-gray-500 text-xs">(prior experience credit, 0–30)</span></label>
        <input type="number" min={0} max={30} value={form.virtual_matches} onChange={set('virtual_matches')}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Nationality</label>
        <input type="text" value={form.nationality} onChange={set('nationality')} placeholder="India"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
      </div>

      <div className="border-t border-gray-800 pt-4">
        <p className="text-xs text-gray-500 mb-3">Guardian / contact info (optional)</p>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Guardian name</label>
            <input type="text" value={form.guardian_name} onChange={set('guardian_name')} placeholder="Parent / guardian full name"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Guardian phone</label>
            <input type="tel" value={form.guardian_phone} onChange={set('guardian_phone')} placeholder="+91 98765 43210"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Contact email</label>
            <input type="email" value={form.contact_email} onChange={set('contact_email')} placeholder="guardian@example.com"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
          </div>
        </div>
      </div>

      <button onClick={() => mutation.mutate()} disabled={!canSubmit}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors disabled:opacity-50">
        {mutation.isPending ? 'Registering…' : 'Register Player'}
      </button>
    </div>
  )
}
