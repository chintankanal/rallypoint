import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  matchesApi, playersApi, academiesApi, eventsApi, sessionsApi,
  type PlayerSearchResult, type LeaderboardEntry, type SessionSummary, type FixtureSlot, type FixturesResponse,
} from '../api/client'
import FixtureMatrixGrid from '../components/FixtureMatrixGrid'
import { buildMatrixModel, classifyCell, TIER_META, GAP_BAND_LEGEND, MATCH_CAT_BADGE } from '../lib/fixtures'
import { analyzeFixtureSlots } from '../lib/fixtureAnalytics'
import { Layout, TierBadge, CRBar, Spinner, ErrorMsg, ProtectedRoute } from '../components/Layout'
import { EventDetailPanel } from '../components/EventDetailPanel'
import { SetPointsInput } from '../components/SetPointsInput'
import { useAuth } from '../auth/context'
import { MatchSubmissionSchema, PlayerRegistrationSchema, getMatchFormatRules, validateEventAsync, validatePlayerNameAsync } from '../validation/schemas'
import { useFormValidation } from '../validation/useFormValidation'

function SendClaimButton({ playerId }: { playerId: string }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const mut = useMutation({
    mutationFn: () => playersApi.sendClaim(playerId),
    onSuccess: () => {
      setBusy(false)
      qc.invalidateQueries({ queryKey: ['players', 'roster'] })
    },
    onError: () => setBusy(false),
  })

  return (
    <button
      type="button"
      onClick={() => { setBusy(true); mut.mutate() }}
      className="text-green-300 hover:text-white text-xs font-semibold"
      disabled={busy}
    >
      {busy ? 'Sending…' : 'Send'}
    </button>
  )
}

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
  const [expandedLeagueEventId, setExpandedLeagueEventId] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '', start_date: '', end_date: '', default_match_format: 'BEST_OF_3',
  })
  const [error, setError] = useState<string | null>(null)

  const q = useQuery({ queryKey: ['events'], queryFn: () => eventsApi.list() })
  const myEvents = q.data?.items.filter(ev => {
    // host academy OR participating academy membership
    if (ev.host_academy_id === academyId) return true
    // participating_academies: array of { academy_id }
    if (Array.isArray((ev as any).participating_academies) && (ev as any).participating_academies.some((a: any) => a.academy_id === academyId)) return true
    // If this is an INTRA_ACADEMY event with an empty participating list, treat it as belonging to a single (host) academy
    if (ev.scheduling_mode === 'INTRA_ACADEMY' && Array.isArray((ev as any).participating_academies) && (ev as any).participating_academies.length === 0) return true
    // participating_academy_ids: array of ids
    if (Array.isArray((ev as any).participating_academy_ids) && (ev as any).participating_academy_ids.includes(academyId)) return true
    // alternative camelCase shape
    if (Array.isArray((ev as any).participatingAcademies) && (ev as any).participatingAcademies.some((a: any) => a.academy_id === academyId)) return true
    return false
  }) ?? []
  const intraEvents = myEvents.filter(ev => ev.scheduling_mode === 'INTRA_ACADEMY')
  const leagueEvents = myEvents.filter(ev => ev.scheduling_mode === 'INTER_ACADEMY' && ev.event_type === 'LEAGUE')

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
          <h3 className="text-lg font-semibold text-white">Training Sessions</h3>
          <p className="text-xs text-gray-500 mt-0.5">Intra-academy practice sessions and friendly matches for your players.</p>
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

      <div className="space-y-6">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-base font-semibold text-white">League Meets & Tournaments</h4>
              <p className="text-xs text-gray-500">Cross-academy leagues and tournaments involving multiple clubs.</p>
            </div>
            <span className="text-xs text-gray-400">{intraEvents.length} events</span>
          </div>

          {intraEvents.map(ev => (
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
          {!intraEvents.length && (
            <p className="text-gray-500 text-sm">No events yet. Create one to start running daily training sessions.</p>
          )}
        </div>

        {leagueEvents.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-base font-semibold text-white">Hosted League Events</h4>
                <p className="text-xs text-gray-500">View roster and fixtures for your inter-academy league events in read-only mode.</p>
              </div>
              <span className="text-xs text-gray-400">{leagueEvents.length} hosted leagues</span>
            </div>
            {leagueEvents.map(ev => {
              const isExpanded = expandedLeagueEventId === ev.event_id
              return (
                <div key={ev.event_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="font-medium text-white text-sm">{ev.name}</div>
                      <div className="text-xs text-gray-500">{ev.event_type.replace(/_/g, ' ')} · {ev.start_date}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => setExpandedLeagueEventId(isExpanded ? null : ev.event_id)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg">
                        {isExpanded ? 'Hide details' : 'View roster & fixtures'}
                      </button>
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${EVENT_STATUS_COLOR[ev.status] ?? ''}`}>
                        {ev.status}
                      </span>
                    </div>
                  </div>
                  {isExpanded && (
                    <EventDetailPanel eventId={ev.event_id} canManage={false} />
                  )}
                </div>
              )
            })}
          </div>
        )}
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
  const [fixtureResult, setFixtureResult] = useState<FixturesResponse | null>(null)
  const [resultSlot, setResultSlot] = useState<FixtureSlot | null>(null)
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string | null>(null)
  const [diagnosticsExpanded, setDiagnosticsExpanded] = useState(false)
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

  const BOOTSTRAP_PHASE_BADGE: Record<string, string> = {
    DISCOVERY: 'bg-blue-500/10 text-blue-300 border-blue-500/20',
    TRANSITION: 'bg-purple-500/10 text-purple-300 border-purple-500/20',
    STANDARD: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
  }

  // Slot classification and labeling provided by shared fixtures helpers

  const SESSION_STATUS_COLOR: Record<string, string> = {
    SCHEDULED: 'bg-yellow-800 text-yellow-100',
    IN_PROGRESS: 'bg-blue-800 text-blue-100',
    COMPLETED: 'bg-green-800 text-green-100',
    CANCELLED: 'bg-gray-700 text-gray-300',
  }

  const hasFixtures = !!fixtureResult || (openedSession?.generated_at != null)
  const fixtureAnalytics = fixturesQ.data ? analyzeFixtureSlots(
    fixturesQ.data.slots,
    fixturesQ.data.diagnostics,
    { numTables: openedSession?.num_tables, sessionMinutes: openedSession?.session_minutes }
  ) : null
  const bootstrapPhase = fixtureAnalytics?.bootstrapPhase ?? fixtureResult?.bootstrap_phase ?? openedSession?.bootstrap_phase ?? 'STANDARD'

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
            <div className="space-y-5">
              {fixtureAnalytics && (
                <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 via-slate-900/80 to-slate-800/80 p-[1px]">
                  <div className="rounded-2xl bg-gray-900/80 border border-gray-800 backdrop-blur-sm p-5 space-y-4">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div className="space-y-4 max-w-2xl">
                        <div className="flex flex-wrap items-center gap-3">
                          <span className="text-xs uppercase tracking-[0.24em] text-gray-400">Session diagnostics</span>
                          <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold ${BOOTSTRAP_PHASE_BADGE[bootstrapPhase] ?? 'bg-slate-700/10 text-slate-200 border-slate-700/20'}`}>
                            {bootstrapPhase.replace(/_/g, ' ')}
                          </span>
                          <span className="inline-flex items-center rounded-full border border-slate-700/20 bg-slate-800 px-3 py-1 text-sm font-semibold text-slate-200">
                            {fixtureAnalytics.regime ?? 'Default'}
                          </span>
                        </div>
                        <div className="text-gray-300 text-sm leading-6">
                          {bootstrapPhase === 'STANDARD' ? (
                            <>Standard Phase: Active because players have established ratings. Matches prioritize <span className="font-semibold text-emerald-400">competitive integrity</span> within strict rating bands.</>
                          ) : bootstrapPhase === 'TRANSITION' ? (
                            <>Transition Phase: Active because there is a mix of established and provisional players. Matches blend rating integrity with accelerated discovery.</>
                          ) : bootstrapPhase === 'DISCOVERY' ? (
                            <>Discovery Phase: Active because players are unrated or provisional. Matches focus on establishing rating accuracy quickly.</>
                          ) : (
                            <>This session was generated with a {bootstrapPhase.toLowerCase()} bootstrap phase. Review slot balance across rounds before entering results.</>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-col items-start gap-3 sm:items-end">
                        <div className="text-xs uppercase tracking-[0.24em] text-gray-400">Fixture Quality</div>
                        <div className="text-3xl font-semibold text-white">{fixtureAnalytics.quality.overallLabel}</div>
                        <span className="text-xs text-gray-400">{fixtureAnalytics.quality.overallScore}%</span>
                        <button
                          type="button"
                          onClick={() => setDiagnosticsExpanded(prev => !prev)}
                          className="inline-flex items-center gap-2 rounded-full border border-gray-700 bg-white/5 px-3 py-2 text-xs font-semibold text-white transition hover:bg-white/10"
                        >
                          {diagnosticsExpanded ? 'Hide details' : 'Show details'}
                          <span className={`transition-transform ${diagnosticsExpanded ? 'rotate-180' : ''}`}>▼</span>
                        </button>
                      </div>
                    </div>

                    {diagnosticsExpanded && (
                      <div className="space-y-4">
                        {/* Narrative verdict */}
                        <div className="rounded-2xl border border-gray-800 bg-gray-950/90 p-4 text-sm text-gray-300 leading-relaxed">
                          {fixtureAnalytics.narrative.split('**').map((part, i) =>
                            i % 2 === 0 ? part : <span key={i} className="font-semibold text-white">{part}</span>
                          )}
                        </div>

                        {/* Two-column: Constraints vs Quality */}
                        <div className="grid gap-4 lg:grid-cols-2">
                          {/* Left: Constraints */}
                          <div className="space-y-3">
                            <div className="text-xs uppercase tracking-[0.24em] text-gray-400 font-semibold">What constrained this session?</div>
                            <div className="space-y-2">
                              <div className="rounded-2xl border border-gray-800 bg-slate-950/70 p-3 text-sm">
                                <div className="text-xs text-gray-500">Player count & parity</div>
                                <div className="mt-1 text-white font-semibold">
                                  {fixtureAnalytics.constraints.playerCount} players{fixtureAnalytics.constraints.parityForcesBye ? ' (odd → forced byes)' : ' (even)'}
                                </div>
                              </div>
                              {fixtureAnalytics.constraints.rawSpread != null && (
                                <div className="rounded-2xl border border-gray-800 bg-slate-950/70 p-3 text-sm">
                                  <div className="text-xs text-gray-500">Rating spread</div>
                                  <div className="mt-1 text-white font-semibold">Raw {Math.round(fixtureAnalytics.constraints.rawSpread)} · Core {Math.round(fixtureAnalytics.constraints.coreSpread ?? 0)}</div>
                                </div>
                              )}
                              {Object.keys(fixtureAnalytics.constraints.tierDistribution).length > 0 && (
                                <div className="rounded-2xl border border-gray-800 bg-slate-950/70 p-3 text-sm">
                                  <div className="text-xs text-gray-500">Tier distribution</div>
                                  <div className="mt-1 text-white text-xs font-mono">
                                    {Object.entries(fixtureAnalytics.constraints.tierDistribution)
                                      .map(([tier, count]) => `${count} ${tier}`)
                                      .join(' · ')}
                                  </div>
                                </div>
                              )}
                              {fixtureAnalytics.constraints.provisionalCount != null && (
                                <div className="rounded-2xl border border-gray-800 bg-slate-950/70 p-3 text-sm">
                                  <div className="text-xs text-gray-500">Provisional players</div>
                                  <div className="mt-1 text-white font-semibold">
                                    {fixtureAnalytics.constraints.provisionalCount} of {fixtureAnalytics.constraints.playerCount}
                                  </div>
                                </div>
                              )}
                              <div className="rounded-2xl border border-gray-800 bg-slate-950/70 p-3 text-sm">
                                <div className="text-xs text-gray-500">Session structure</div>
                                <div className="mt-1 text-white font-semibold text-xs">
                                  {fixtureAnalytics.constraints.rounds} round{fixtureAnalytics.constraints.rounds !== 1 ? 's' : ''}{fixtureAnalytics.constraints.numTables ? ` · ${fixtureAnalytics.constraints.numTables} table${fixtureAnalytics.constraints.numTables !== 1 ? 's' : ''}` : ''}
                                </div>
                              </div>
                              <div className="rounded-2xl border border-gray-800 bg-slate-950/70 p-3 text-sm">
                                <div className="text-xs text-gray-500">Gap targets</div>
                                <div className="mt-1 text-white text-xs font-mono">
                                  Competitive ≤ {fixtureAnalytics.constraints.competitiveMaxGap ?? '—'} · Stretch ≤ {fixtureAnalytics.constraints.stretchMaxGap ?? '—'}
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Right: Quality dimensions */}
                          <div className="space-y-3">
                            <div className="text-xs uppercase tracking-[0.24em] text-gray-400 font-semibold">How fairly it delivered</div>
                            <div className="space-y-2">
                              {fixtureAnalytics.quality.dimensions.map(dim => {
                                const verdictColors = {
                                  optimal: 'bg-emerald-900/30 border-emerald-700/50 text-emerald-200',
                                  good: 'bg-blue-900/30 border-blue-700/50 text-blue-200',
                                  limited: 'bg-amber-900/30 border-amber-700/50 text-amber-200',
                                }
                                const dimensionHelpText: Record<string, string> = {
                                  'competitive-balance': 'Share of matches kept within sane rating bands — only out-of-band pairings count against this.',
                                  'opponent-variety': 'Average distinct opponents per player vs the most possible given rounds and pool size.',
                                  'game-equity': 'How evenly match counts are spread (1.00 = everyone played the same number).',
                                  'rest-distribution': 'Byes given vs the minimum unavoidable for this pool size.',
                                  'stretch-reach': 'Of players who had a higher-rated opponent available, how many got a play-up match.',
                                }
                                return (
                                  <div key={dim.key} className={`rounded-2xl border ${verdictColors[dim.verdict]} bg-slate-950/70 p-3 text-sm`}>
                                    <div className="flex items-center justify-between gap-2">
                                      <div className="flex items-center gap-1">
                                        <div className="text-xs text-gray-400">{dim.label}</div>
                                        <span
                                          title={dimensionHelpText[dim.key] || ''}
                                          className="text-gray-500 hover:text-gray-300 cursor-help text-[10px] font-bold leading-none"
                                        >
                                          ⓘ
                                        </span>
                                      </div>
                                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold bg-white/10 border border-white/20">
                                        {dim.verdict === 'optimal' ? '✓ Optimal' : dim.verdict === 'good' ? '✓ Good' : '⚠ Limited'}
                                      </span>
                                    </div>
                                    <div className="mt-2 text-white font-semibold">{dim.achieved}</div>
                                    {dim.limitedBy && (
                                      <div className="mt-1 text-xs text-gray-400">
                                        <div>Limited by: {dim.limitedBy}</div>
                                        {dim.guidance && (
                                          <div className="mt-1 text-gray-500 text-[11px]">{dim.guidance}</div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        </div>

                        {/* Category mix and rematch info */}
                        <div className="space-y-3">
                          <div className="text-xs uppercase tracking-[0.24em] text-gray-400">Matchup category mix</div>
                          <div className="flex w-full h-3 overflow-hidden rounded-full bg-gray-800 border border-gray-700">
                            {[
                              { key: 'competitive', color: 'bg-blue-500', percentage: fixtureAnalytics.percentages.competitive },
                              { key: 'stretch', color: 'bg-fuchsia-500', percentage: fixtureAnalytics.percentages.stretch },
                              { key: 'anchor', color: 'bg-amber-500', percentage: fixtureAnalytics.percentages.anchor },
                              { key: 'developmental', color: 'bg-slate-400', percentage: fixtureAnalytics.percentages.developmental },
                              { key: 'outOfBand', color: 'bg-red-500', percentage: fixtureAnalytics.percentages.outOfBand },
                              { key: 'bye', color: 'bg-gray-600', percentage: fixtureAnalytics.percentages.bye },
                            ].map(category => (
                              <div key={category.key}
                                className={`${category.color} h-full transition-all duration-200 ${activeCategoryFilter && activeCategoryFilter !== category.key ? 'opacity-30' : 'opacity-100'}`}
                                style={{ width: activeCategoryFilter ? (activeCategoryFilter === category.key ? `${category.percentage}%` : '0%') : `${category.percentage}%` }}
                              />
                            ))}
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-[10px] uppercase tracking-[0.25em] text-gray-500">
                            {[
                              { key: 'competitive', label: 'Comp', color: 'bg-blue-500', value: fixtureAnalytics.percentages.competitive },
                              { key: 'stretch', label: 'Stretch', color: 'bg-fuchsia-500', value: fixtureAnalytics.percentages.stretch },
                              { key: 'anchor', label: 'Anchor', color: 'bg-amber-500', value: fixtureAnalytics.percentages.anchor },
                              { key: 'developmental', label: 'Developmental', color: 'bg-slate-400', value: fixtureAnalytics.percentages.developmental },
                              { key: 'outOfBand', label: 'Out-of-band', color: 'bg-red-500', value: fixtureAnalytics.percentages.outOfBand },
                              { key: 'bye', label: 'Bye', color: 'bg-gray-600', value: fixtureAnalytics.percentages.bye },
                            ].map(category => (
                              <button key={category.key} type="button"
                                onClick={() => setActiveCategoryFilter(prev => prev === category.key ? null : category.key)}
                                className={`flex items-center gap-2 text-left ${activeCategoryFilter === category.key ? 'text-white font-semibold' : 'text-gray-400 hover:text-white'} focus:outline-none transition-colors`}>
                                <span className={`inline-block h-2 w-2 rounded-full ${category.color}`} />
                                {category.label} ({category.value}%)
                              </button>
                            ))}
                          </div>
                        </div>

                      </div>
                    )}
                  </div>
                </div>
              )}

              {fixturesQ.isLoading && <Spinner />}

              {fixturesQ.data && fixturesQ.data.slots.length > 0 && (() => {
                const model = buildMatrixModel(fixturesQ.data.slots as any, {
                  sectionOf: (p: any) => p.tier ?? 'UNKNOWN',
                  sectionMeta: (id: string, _players: any[]) => ({
                    label: (TIER_META[id]?.label ?? id),
                    accent: (TIER_META[id]?.accent ?? { bg: 'bg-gray-700', text: 'text-gray-200' }),
                  }),
                  cellOf: (slot: any, self: any, opp: any) => {
                    const meta = classifyCell(slot as any, self as any, opp as any)
                    return { label: meta.label, stripClass: meta.stripClass, category: meta.category, tooltip: meta.tooltip }
                  },
                  sectionSort: (a, b) => (TIER_META[b.id]?.rank ?? 0) - (TIER_META[a.id]?.rank ?? 0),
                  // totalRounds omitted for sessions; buildMatrixModel derives rounds from schedule
                })

                return (
                  <FixtureMatrixGrid model={model} legend={GAP_BAND_LEGEND} dimCategory={activeCategoryFilter} />
                )
              })()}

              {fixturesQ.data && (() => {
                const byRound = fixturesQ.data.slots.reduce<Record<number, typeof fixturesQ.data.slots>>((acc, slot) => {
                  ;(acc[slot.round_number] ??= []).push(slot)
                  return acc
                }, {})
                return Object.entries(byRound).map(([rn, slots]) => (
                  <div key={rn} className="space-y-3">
                    <div className="rounded-2xl border border-gray-800 bg-gray-950/70 px-4 py-3">
                      <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Round {rn}</div>
                    </div>

                    <div className="space-y-3">
                      {slots.map(slot => {
                        const meta = classifyCell(slot as any, slot.player_a as any, slot.player_b as any)
                        const code = (c: string) => {
                          if (c === 'competitive') return 'COMPETITIVE'
                          if (c === 'stretch') return 'STRETCH'
                          if (c === 'anchor') return 'ANCHOR'
                          if (c === 'developmental') return 'DEVELOPMENTAL'
                          if (c === 'outOfBand') return 'OUT_OF_BAND'
                          if (c === 'bye') return 'BYE'
                          return 'UNKNOWN'
                        }
                        const categoryCode = code(meta.category)
                        const badgeClasses = MATCH_CAT_BADGE[categoryCode] ?? MATCH_CAT_BADGE.UNKNOWN
                        const winnerA = slot.status === 'PLAYED' && slot.match_result?.winner_id === slot.player_a.player_id
                        const winnerB = slot.status === 'PLAYED' && slot.match_result?.winner_id === slot.player_b?.player_id
                        return (
                          <div key={slot.slot_id} className={`rounded-3xl border border-gray-800 bg-gray-900/80 p-4 shadow-sm transition ${slot.status === 'BYE' ? 'opacity-70' : 'hover:border-slate-600'}`}>
                            <div className="grid gap-4 md:grid-cols-[1.8fr_0.85fr_0.75fr] items-center">
                              <div className="space-y-3 min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeClasses}`}>
                                    {meta.label}
                                  </span>
                                  <span className="text-xs text-gray-500">Table {slot.table_number}</span>
                                </div>

                                <div className="grid gap-3 sm:grid-cols-2">
                                  <div className="min-w-0">
                                    <div className="text-sm font-semibold text-white truncate">{slot.player_a.name}</div>
                                    <div className="text-xs text-gray-400 font-mono">{Math.round(slot.player_a.current_rating)}</div>
                                  </div>
                                  {slot.player_b ? (
                                    <div className="min-w-0">
                                      <div className="text-sm font-semibold text-white truncate">{slot.player_b.name}</div>
                                      <div className="text-xs text-gray-400 font-mono">{Math.round(slot.player_b.current_rating)}</div>
                                    </div>
                                  ) : (
                                    <div className="text-sm font-semibold text-gray-400 italic">Bye</div>
                                  )}
                                </div>
                              </div>

                              <div className="rounded-3xl border border-gray-800 bg-gray-950/90 px-3 py-2 text-sm font-mono text-gray-200">
                                {slot.status === 'PLAYED' && slot.match_result ? (
                                  <div className="flex items-center justify-between gap-3">
                                    <span className={winnerA ? 'text-emerald-300 font-semibold' : 'text-gray-500'}>{slot.match_result.sets_won_a}</span>
                                    <span className="text-gray-600">–</span>
                                    <span className={winnerB ? 'text-emerald-300 font-semibold' : 'text-gray-500'}>{slot.match_result.sets_won_b}</span>
                                  </div>
                                ) : (
                                  <div className="text-xs uppercase tracking-[0.24em] text-slate-500">{slot.status.replace(/_/g, ' ')}</div>
                                )}
                              </div>

                              <div className="flex flex-col items-start justify-between gap-3 sm:items-end">
                                <span className="inline-flex rounded-full border border-slate-700 bg-slate-950/80 px-3 py-1 text-xs text-gray-300">Table {slot.table_number}</span>
                                {slot.player_b && slot.status === 'SCHEDULED' && (
                                  <button
                                    onClick={() => setResultSlot(slot)}
                                    className="rounded-full bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-blue-500">
                                    Enter Result
                                  </button>
                                )}
                              </div>
                            </div>
                          </div>
                        )
                      })}
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
  const { user } = useAuth()
  const [selectedPlayer, setSelectedPlayer] = useState<LeaderboardEntry | null>(null)
  const [copiedClaimCode, setCopiedClaimCode] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['academy-leaderboard', academyId],
    queryFn: () => academiesApi.leaderboard(academyId, { limit: 100 }),
  })

  function copyClaimCode(code: string) {
    navigator.clipboard.writeText(code)
      .then(() => {
        setCopiedClaimCode(code)
        window.setTimeout(() => setCopiedClaimCode(null), 1500)
      })
      .catch(() => {
        setCopiedClaimCode(null)
      })
  }
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
              <th className="px-4 py-3 hidden lg:table-cell">Claim code</th>
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
                  {row.claim_code && !row.is_claimed ? (
                    <div className="flex items-center gap-2">
                      <span>{row.claim_code}</span>
                      <button
                        type="button"
                        onClick={() => copyClaimCode(row.claim_code!)}
                        className="text-blue-300 hover:text-white text-xs font-semibold"
                      >
                        {copiedClaimCode === row.claim_code ? 'Copied' : 'Copy'}
                      </button>
                      {user?.role === 'COACH' && (
                        <SendClaimButton playerId={row.player_id} />
                      )}
                    </div>
                  ) : '—'}
                </td>
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
  const [setScores, setSetScores] = useState<Array<{ points_a: number; points_b: number }> | null>(null)
  const [result, setResult] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  
  // Validation hook
  const validation = useFormValidation(MatchSubmissionSchema)

  const maxSets: Record<string, number> = { BEST_OF_3: 2, BEST_OF_5: 3, BEST_OF_7: 4 }

  const mutation = useMutation({
    mutationFn: async () => {
      // Player selection validation
      if (!playerA || !playerB) throw new Error('Select both players')
      
      // Form data validation using Zod schema with async checks
      await validation.validateAsync({
        event_id: form.event_id,
        match_format: form.match_format,
        sets_won_a: form.sets_won_a ? Number(form.sets_won_a) : 0,
        sets_won_b: form.sets_won_b ? Number(form.sets_won_b) : 0,
        match_date: form.match_date,
        is_retirement: form.is_retirement,
        set_scores: setScores,
      })

      return matchesApi.submit({
        event_id: form.event_id,
        player_a_id: playerA.player_id,
        player_b_id: playerB.player_id,
        match_format: form.match_format,
        sets_won_a: Number(form.sets_won_a),
        sets_won_b: Number(form.sets_won_b),
        match_date: form.match_date,
        is_retirement: form.is_retirement,
        set_scores: setScores,
      })
    },
    onSuccess: m => {
      const winner = m.winner_id === m.player_a.player_id ? m.player_a.name : m.player_b.name
      setResult(`Match submitted! Winner: ${winner}. Status: ${m.confirmation_status}`)
      setApiError(null)
      setPlayerA(null); setPlayerB(null)
      setForm(f => ({ ...f, sets_won_a: '', sets_won_b: '' }))
      setSetScores(null)
      validation.clearError('sets_won_a')
      validation.clearError('sets_won_b')
    },
    onError: (e: Error) => { setApiError(e.message); setResult(null) },
  })

  const max = maxSets[form.match_format]
  const matchFormatRules = getMatchFormatRules(form.match_format)

  const handleSubmit = () => {
    mutation.mutate()
  }

  return (
    <div className="max-w-md space-y-4">
      {result && <div className="bg-green-900/40 border border-green-700 text-green-300 rounded p-3 text-sm">{result}</div>}
      {apiError && <ErrorMsg message={apiError} />}
      {validation.hasErrors && (
        <div className="bg-red-900/20 border border-red-700 text-red-300 rounded p-3 text-sm space-y-1">
          <p className="font-semibold">Form validation errors:</p>
          {Object.entries(validation.errors).map(([field, msg]) => (
            <p key={field} className="text-xs">• {msg}</p>
          ))}
        </div>
      )}

      <PlayerPicker label="Player A" academyId={academyId} value={playerA} onChange={setPlayerA} />
      <PlayerPicker label="Player B" academyId={academyId} value={playerB} onChange={setPlayerB} />

      <div>
        <label className="block text-sm text-gray-400 mb-1">Match Format</label>
        <select value={form.match_format} onChange={e => setForm(f => ({ ...f, match_format: e.target.value }))}
          className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm">
          {FORMATS.map(f => <option key={f} value={f}>{f.replace(/_/g, ' ')} (first to {maxSets[f]})</option>)}
        </select>
        <p className="text-xs text-gray-500 mt-1">{matchFormatRules}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm text-gray-400 mb-1">
            {playerA ? playerA.name.split(' ')[0] : 'Player A'} sets won
          </label>
          <input type="number" min={0} max={max} value={form.sets_won_a}
            onChange={e => {
              setForm(f => ({ ...f, sets_won_a: e.target.value }))
              validation.clearError('sets_won_a')
            }}
            className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-center text-lg font-mono ${
              validation.getError('sets_won_a') 
                ? 'border-2 border-red-500' 
                : 'border border-gray-700'
            }`} />
          {validation.getError('sets_won_a') && (
            <p className="text-xs text-red-400 mt-1">{validation.getError('sets_won_a')}</p>
          )}
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">
            {playerB ? playerB.name.split(' ')[0] : 'Player B'} sets won
          </label>
          <input type="number" min={0} max={max} value={form.sets_won_b}
            onChange={e => {
              setForm(f => ({ ...f, sets_won_b: e.target.value }))
              validation.clearError('sets_won_b')
            }}
            className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-center text-lg font-mono ${
              validation.getError('sets_won_b') 
                ? 'border-2 border-red-500' 
                : 'border border-gray-700'
            }`} />
          {validation.getError('sets_won_b') && (
            <p className="text-xs text-red-400 mt-1">{validation.getError('sets_won_b')}</p>
          )}
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Match Date</label>
        <input type="date" value={form.match_date}
          onChange={e => {
            setForm(f => ({ ...f, match_date: e.target.value }))
            validation.clearError('match_date')
          }}
          className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
            validation.getError('match_date') 
              ? 'border-2 border-red-500' 
              : 'border border-gray-700'
          }`} />
        {validation.getError('match_date') && (
          <p className="text-xs text-red-400 mt-1">{validation.getError('match_date')}</p>
        )}
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Event ID</label>
        <div className="relative">
          <input type="text" value={form.event_id} placeholder="Paste the event UUID"
            onChange={e => {
              setForm(f => ({ ...f, event_id: e.target.value }))
              validation.clearError('event_id')
            }}
            onBlur={() => {
              // Validate event exists when field loses focus
              if (form.event_id.trim()) {
                validation.validateFieldAsync('event_id', () => validateEventAsync(form.event_id))
              }
            }}
            className={`w-full bg-gray-800 rounded-lg px-3 py-2 pr-8 text-white text-sm font-mono placeholder-gray-600 ${
              validation.getError('event_id') 
                ? 'border-2 border-red-500' 
                : 'border border-gray-700'
            }`} />
          {validation.isValidatingField('event_id') && (
            <div className="absolute right-2 top-2.5 text-gray-400">
              <div className="animate-spin text-xs">⟳</div>
            </div>
          )}
        </div>
        <p className="text-xs text-gray-500 mt-1">Find event IDs in Admin → Events</p>
        {validation.getError('event_id') && (
          <p className="text-xs text-red-400 mt-1">{validation.getError('event_id')}</p>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
        <input type="checkbox" checked={form.is_retirement}
          onChange={e => setForm(f => ({ ...f, is_retirement: e.target.checked }))}
          className="w-4 h-4 accent-blue-500" />
        Retirement / walkover
      </label>

      {form.sets_won_a !== '' && form.sets_won_b !== '' && (() => {
        const nA = Number(form.sets_won_a)
        const nB = Number(form.sets_won_b)
        const maxSets = ({ BEST_OF_3: 3, BEST_OF_5: 5, BEST_OF_7: 7 } as const)[form.match_format as 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7']!
        return nA + nB > 0 && nA <= maxSets && nB <= maxSets && nA + nB <= maxSets ? (
          <SetPointsInput
            matchFormat={form.match_format as 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7'}
            setsWonA={nA}
            setsWonB={nB}
            isRetirement={form.is_retirement}
            onSetScoresChange={(scores) => setSetScores(scores)}
          />
        ) : null
      })()}

      <button onClick={handleSubmit} disabled={mutation.isPending || !playerA || !playerB}
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
  const [setScores, setSetScores] = useState<Array<{ points_a: number; points_b: number }> | null>(null)
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
      set_scores: setScores,
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

        {setsA !== '' && setsB !== '' && (() => {
          const nA = Number(setsA)
          const nB = Number(setsB)
          const maxTotalSets = ({ BEST_OF_3: 3, BEST_OF_5: 5, BEST_OF_7: 7 } as const)[matchFormat as 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7']!
          return nA + nB > 0 && nA + nB <= maxTotalSets ? (
            <SetPointsInput
              matchFormat={matchFormat as 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7'}
              setsWonA={nA}
              setsWonB={nB}
              isRetirement={isRetirement}
              onSetScoresChange={setSetScores}
            />
          ) : null
        })()}

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
  const [apiError, setApiError] = useState<string | null>(null)
  const qc = useQueryClient()
  
  // Validation hook
  const validation = useFormValidation(PlayerRegistrationSchema)

  const mutation = useMutation({
    mutationFn: async () => {
      // Form data validation using Zod schema with async checks
      await validation.validateAsync({
        name: form.name,
        date_of_birth: form.date_of_birth,
        gender: form.gender,
        seeding_level: form.seeding_level,
        seeding_reference: form.seeding_reference || null,
        virtual_matches: Number(form.virtual_matches),
        nationality: form.nationality || null,
        guardian_name: form.guardian_name || null,
        guardian_phone: form.guardian_phone || null,
        contact_email: form.contact_email || null,
      })

      return playersApi.create({
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
      })
    },
    onSuccess: p => {
      setSuccess(
        p.claim_code
          ? `${p.name} registered with rating ${Math.round(p.current_rating)} — claim code ${p.claim_code}`
          : `${p.name} registered with rating ${Math.round(p.current_rating)}`
      )
      setApiError(null)
      setForm({
        name: '', date_of_birth: '', gender: '',
        seeding_level: 'UNSEEDED', seeding_reference: '', virtual_matches: '0',
        nationality: 'India', guardian_name: '', guardian_phone: '', contact_email: '',
      })
      validation.clearAllErrors()
      qc.invalidateQueries({ queryKey: ['academy-leaderboard', academyId] })
    },
    onError: (e: Error) => { setApiError(e.message); setSuccess(null) },
  })

  function set(k: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm(f => ({ ...f, [k]: e.target.value }))
      validation.clearError(k)
    }
  }

  return (
    <div className="max-w-md space-y-4">
      {success && <div className="bg-green-900/40 border border-green-700 text-green-300 rounded p-3 text-sm">{success}</div>}
      {apiError && <ErrorMsg message={apiError} />}
      {validation.hasErrors && (
        <div className="bg-red-900/20 border border-red-700 text-red-300 rounded p-3 text-sm space-y-1">
          <p className="font-semibold">Form validation errors:</p>
          {Object.entries(validation.errors).map(([field, msg]) => (
            <p key={field} className="text-xs">• {msg}</p>
          ))}
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-400 mb-1">Full name <span className="text-red-400">*</span></label>
        <div className="relative">
          <input type="text" required value={form.name} onChange={set('name')} placeholder="Arjun Sharma"
            onBlur={() => {
              // Validate player name uniqueness when field loses focus
              if (form.name.trim()) {
                validation.validateFieldAsync('name', () => validatePlayerNameAsync(form.name, academyId))
              }
            }}
            className={`w-full bg-gray-800 rounded-lg px-3 py-2 pr-8 text-white text-sm ${
              validation.getError('name') 
                ? 'border-2 border-red-500' 
                : 'border border-gray-700'
            }`} />
          {validation.isValidatingField('name') && (
            <div className="absolute right-2 top-2.5 text-gray-400">
              <div className="animate-spin text-xs">⟳</div>
            </div>
          )}
        </div>
        {validation.getError('name') && (
          <p className="text-xs text-red-400 mt-1">{validation.getError('name')}</p>
        )}
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Date of birth <span className="text-red-400">*</span> <span className="text-gray-500 text-xs">(must be 6–18 years old)</span></label>
        <input type="date" required value={form.date_of_birth} onChange={set('date_of_birth')}
          className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
            validation.getError('date_of_birth') 
              ? 'border-2 border-red-500' 
              : 'border border-gray-700'
          }`} />
        {validation.getError('date_of_birth') && (
          <p className="text-xs text-red-400 mt-1">{validation.getError('date_of_birth')}</p>
        )}
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Gender <span className="text-red-400">*</span></label>
        <select value={form.gender} onChange={set('gender')}
          className={`w-full bg-gray-800 text-white rounded-lg px-3 py-2 text-sm ${
            validation.getError('gender') 
              ? 'border-2 border-red-500' 
              : 'border border-gray-700'
          }`}>
          <option value="">Select gender…</option>
          <option value="MALE">Male</option>
          <option value="FEMALE">Female</option>
        </select>
        {validation.getError('gender') && (
          <p className="text-xs text-red-400 mt-1">{validation.getError('gender')}</p>
        )}
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
            className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
              validation.getError('seeding_reference') 
                ? 'border-2 border-red-500' 
                : 'border border-gray-700'
            }`} />
          {validation.getError('seeding_reference') && (
            <p className="text-xs text-red-400 mt-1">{validation.getError('seeding_reference')}</p>
          )}
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-400 mb-1">Virtual matches <span className="text-gray-500 text-xs">(prior experience credit, 0–30)</span></label>
        <input type="number" min={0} max={30} value={form.virtual_matches} onChange={set('virtual_matches')}
          className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
            validation.getError('virtual_matches') 
              ? 'border-2 border-red-500' 
              : 'border border-gray-700'
          }`} />
        {validation.getError('virtual_matches') && (
          <p className="text-xs text-red-400 mt-1">{validation.getError('virtual_matches')}</p>
        )}
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">Nationality</label>
        <input type="text" value={form.nationality} onChange={set('nationality')} placeholder="India"
          className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
            validation.getError('nationality') 
              ? 'border-2 border-red-500' 
              : 'border border-gray-700'
          }`} />
        {validation.getError('nationality') && (
          <p className="text-xs text-red-400 mt-1">{validation.getError('nationality')}</p>
        )}
      </div>

      <div className="border-t border-gray-800 pt-4">
        <p className="text-xs text-gray-500 mb-3">Guardian / contact info (optional)</p>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Guardian name</label>
            <input type="text" value={form.guardian_name} onChange={set('guardian_name')} placeholder="Parent / guardian full name"
              className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
                validation.getError('guardian_name') 
                  ? 'border-2 border-red-500' 
                  : 'border border-gray-700'
              }`} />
            {validation.getError('guardian_name') && (
              <p className="text-xs text-red-400 mt-1">{validation.getError('guardian_name')}</p>
            )}
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Guardian phone</label>
            <input type="tel" value={form.guardian_phone} onChange={set('guardian_phone')} placeholder="+91 98765 43210"
              className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
                validation.getError('guardian_phone') 
                  ? 'border-2 border-red-500' 
                  : 'border border-gray-700'
              }`} />
            {validation.getError('guardian_phone') && (
              <p className="text-xs text-red-400 mt-1">{validation.getError('guardian_phone')}</p>
            )}
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Contact email</label>
            <input type="email" value={form.contact_email} onChange={set('contact_email')} placeholder="guardian@example.com"
              className={`w-full bg-gray-800 rounded-lg px-3 py-2 text-white text-sm ${
                validation.getError('contact_email') 
                  ? 'border-2 border-red-500' 
                  : 'border border-gray-700'
              }`} />
            {validation.getError('contact_email') && (
              <p className="text-xs text-red-400 mt-1">{validation.getError('contact_email')}</p>
            )}
          </div>
        </div>
      </div>

      <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !form.name || !form.date_of_birth || !form.gender}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors disabled:opacity-50">
        {mutation.isPending ? 'Registering…' : 'Register Player'}
      </button>
    </div>
  )
}
