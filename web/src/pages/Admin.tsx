import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  disputesApi, configApi, seasonsApi, eventsApi, academiesApi, playersApi, matchesApi,
  type Season, type EventListItem, type AcademyListItem,
  type EventRoster, type EventFixtures, type EventFixturePlayer, type EventFixtureSlot,
  type PlayerDirectoryItem,
} from '../api/client'

type FixtureState = 'ROSTER_OPEN' | 'FIXTURES_READY' | 'FIXTURE_FROZEN' | 'RESULTS_SUBMITTED' | 'RATINGS_APPLIED' | null
import { Layout, Spinner, ErrorMsg, ProtectedRoute } from '../components/Layout'

type Tab = 'seasons' | 'events' | 'academies' | 'disputes' | 'config'

export default function Admin() {
  return (
    <ProtectedRoute roles={['ADMIN']}>
      <Layout>
        <AdminInner />
      </Layout>
    </ProtectedRoute>
  )
}

function AdminInner() {
  const [tab, setTab] = useState<Tab>('seasons')

  const tabs: [Tab, string][] = [
    ['seasons', 'Seasons'],
    ['events', 'Events'],
    ['academies', 'Academies'],
    ['disputes', 'Disputes'],
    ['config', 'Config'],
  ]

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Admin Panel</h2>

      <div className="flex gap-0 border-b border-gray-800 flex-wrap">
        {tabs.map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'seasons' && <SeasonsTab />}
      {tab === 'events' && <EventsTab />}
      {tab === 'academies' && <AcademiesTab />}
      {tab === 'disputes' && <DisputeQueue />}
      {tab === 'config' && <ConfigEditor />}
    </div>
  )
}

// ── Seasons ───────────────────────────────────────────────────────────────────

const SEASON_STATUSES = ['UPCOMING', 'ACTIVE', 'COMPLETED']
const STATUS_COLOR: Record<string, string> = {
  UPCOMING: 'bg-yellow-800 text-yellow-100',
  ACTIVE: 'bg-green-800 text-green-100',
  COMPLETED: 'bg-gray-700 text-gray-300',
}

function SeasonsTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', start_date: '', end_date: '' })
  const [error, setError] = useState<string | null>(null)

  const q = useQuery({ queryKey: ['seasons'], queryFn: () => seasonsApi.list() })

  const createMut = useMutation({
    mutationFn: () => seasonsApi.create(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['seasons'] }); setShowForm(false); setForm({ name: '', start_date: '', end_date: '' }); setError(null) },
    onError: (e: Error) => setError(e.message),
  })

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => seasonsApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['seasons'] }),
  })

  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorMsg message={(q.error as Error).message} />

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-white">Seasons</h3>
        <button onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors">
          {showForm ? 'Cancel' : '+ New Season'}
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-4">
          {error && <ErrorMsg message={error} />}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Season name</label>
            <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Season 2025–26" className={inputCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Start date</label>
              <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} className={inputCls} />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">End date</label>
              <input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} className={inputCls} />
            </div>
          </div>
          <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.name || !form.start_date || !form.end_date}
            className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg disabled:opacity-50">
            {createMut.isPending ? 'Creating…' : 'Create Season'}
          </button>
        </div>
      )}

      <div className="space-y-3">
        {(q.data as Season[])?.map(s => (
          <div key={s.season_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="font-medium text-white">{s.name}</div>
              <div className="text-xs text-gray-500 mt-0.5">{s.start_date} → {s.end_date}</div>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLOR[s.status] ?? 'bg-gray-700 text-gray-300'}`}>{s.status}</span>
              <select value={s.status} onChange={e => statusMut.mutate({ id: s.season_id, status: e.target.value })}
                className="text-xs bg-gray-800 border border-gray-700 text-gray-300 rounded px-2 py-1">
                {SEASON_STATUSES.map(st => <option key={st} value={st}>{st}</option>)}
              </select>
            </div>
          </div>
        ))}
        {!q.data?.length && <p className="text-gray-500 text-sm">No seasons yet.</p>}
      </div>
    </div>
  )
}

// ── Events ────────────────────────────────────────────────────────────────────

const VALID_COMBOS: Record<string, string[]> = {
  INTRA_ACADEMY: ['FRIENDLY'],
  INTER_ACADEMY: ['LEAGUE', 'TOURNAMENT_EXTERNAL', 'TOURNAMENT_MANAGED'],
}
const FORMATS = ['BEST_OF_3', 'BEST_OF_5', 'BEST_OF_7']
const EVENT_STATUSES = ['SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED']
const EVENT_STATUS_COLOR: Record<string, string> = {
  SCHEDULED: 'bg-yellow-800 text-yellow-100',
  IN_PROGRESS: 'bg-blue-800 text-blue-100',
  COMPLETED: 'bg-green-800 text-green-100',
  CANCELLED: 'bg-gray-700 text-gray-300',
}

function EventsTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '', scheduling_mode: 'INTRA_ACADEMY', event_type: 'FRIENDLY',
    default_match_format: 'BEST_OF_3', start_date: '', end_date: '',
    season_id: '', host_academy_id: '',
  })
  const [error, setError] = useState<string | null>(null)

  const eventsQ = useQuery({ queryKey: ['admin-events'], queryFn: () => eventsApi.list() })
  const seasonsQ = useQuery({ queryKey: ['seasons'], queryFn: () => seasonsApi.list() })
  const academiesQ = useQuery({ queryKey: ['academies-list'], queryFn: () => academiesApi.list('ACTIVE') })

  const validTypes = VALID_COMBOS[form.scheduling_mode] ?? []

  const createMut = useMutation({
    mutationFn: () => eventsApi.create({
      name: form.name,
      scheduling_mode: form.scheduling_mode,
      event_type: form.event_type,
      default_match_format: form.default_match_format || undefined,
      start_date: form.start_date,
      end_date: form.end_date || undefined,
      season_id: form.season_id || undefined,
      host_academy_id: form.host_academy_id || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-events'] })
      setShowForm(false)
      setError(null)
      setForm({ name: '', scheduling_mode: 'INTRA_ACADEMY', event_type: 'FRIENDLY', default_match_format: 'BEST_OF_3', start_date: '', end_date: '', season_id: '', host_academy_id: '' })
    },
    onError: (e: Error) => setError(e.message),
  })

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => eventsApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-events'] }),
  })

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-white">Events</h3>
        <button onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors">
          {showForm ? 'Cancel' : '+ New Event'}
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-4">
          {error && <ErrorMsg message={error} />}

          <div>
            <label className="block text-sm text-gray-400 mb-1">Event name</label>
            <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Academy Inter-Club League — October 2025" className={inputCls} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Scheduling mode</label>
              <select value={form.scheduling_mode}
                onChange={e => {
                  const mode = e.target.value
                  const firstType = VALID_COMBOS[mode][0]
                  setForm(f => ({ ...f, scheduling_mode: mode, event_type: firstType }))
                }}
                className={selectCls}>
                <option value="INTRA_ACADEMY">Intra-Academy (within one academy)</option>
                <option value="INTER_ACADEMY">Inter-Academy (multiple academies)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Event type</label>
              <select value={form.event_type} onChange={e => setForm(f => ({ ...f, event_type: e.target.value }))}
                className={selectCls}>
                {validTypes.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Default match format</label>
            <select value={form.default_match_format} onChange={e => setForm(f => ({ ...f, default_match_format: e.target.value }))}
              className={selectCls}>
              {FORMATS.map(f => <option key={f} value={f}>{f.replace(/_/g, ' ')}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Start date</label>
              <input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} className={inputCls} />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                End date {form.scheduling_mode === 'INTER_ACADEMY' && <span className="text-red-400">*</span>}
              </label>
              <input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} className={inputCls} />
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Season <span className="text-gray-500">(optional)</span></label>
            <select value={form.season_id} onChange={e => setForm(f => ({ ...f, season_id: e.target.value }))} className={selectCls}>
              <option value="">No season</option>
              {(seasonsQ.data as Season[] | undefined)?.map(s => (
                <option key={s.season_id} value={s.season_id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Host academy <span className="text-gray-500">(optional)</span></label>
            <select value={form.host_academy_id} onChange={e => setForm(f => ({ ...f, host_academy_id: e.target.value }))} className={selectCls}>
              <option value="">None</option>
              {academiesQ.data?.items.map((a: AcademyListItem) => (
                <option key={a.academy_id} value={a.academy_id}>{a.name} — {a.city}</option>
              ))}
            </select>
          </div>

          <button onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.name || !form.start_date}
            className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg disabled:opacity-50">
            {createMut.isPending ? 'Creating…' : 'Create Event'}
          </button>
        </div>
      )}

      <div className="space-y-3">
        {eventsQ.isLoading && <Spinner />}
        {eventsQ.error && <ErrorMsg message={(eventsQ.error as Error).message} />}
        {eventsQ.data?.items.map((ev: EventListItem) => {
          const isLeague = ev.scheduling_mode === 'INTER_ACADEMY' && ev.event_type === 'LEAGUE'
          const isExpanded = expandedEventId === ev.event_id
          return (
            <div key={ev.event_id}>
              <EventCard event={ev}
                onStatusChange={(status) => statusMut.mutate({ id: ev.event_id, status })}
                expanded={isExpanded}
                onToggle={isLeague ? () => setExpandedEventId(isExpanded ? null : ev.event_id) : undefined}
              />
              {isExpanded && isLeague && (
                <EventDetailPanel eventId={ev.event_id} canManage={true} />
              )}
            </div>
          )
        })}
        {eventsQ.data?.items.length === 0 && !showForm && (
          <p className="text-gray-500 text-sm">No events found.</p>
        )}
      </div>
    </div>
  )
}

function EventCard({ event: ev, onStatusChange, expanded, onToggle }: {
  event: EventListItem
  onStatusChange: (s: string) => void
  expanded?: boolean
  onToggle?: () => void
}) {
  return (
    <div className={`bg-gray-900 border border-gray-800 p-4 space-y-2 ${expanded ? 'rounded-t-xl border-b-0' : 'rounded-xl'}`}>
      <div className="flex items-start justify-between flex-wrap gap-2">
        <div>
          <div className="font-medium text-white">{ev.name}</div>
          <div className="text-xs text-gray-500 mt-0.5">
            {ev.scheduling_mode.replace('_', ' ')} · {ev.event_type.replace(/_/g, ' ')} · {ev.start_date}
            {ev.end_date && ` → ${ev.end_date}`}
          </div>
          <div className="text-xs text-gray-600 font-mono mt-1">{ev.event_id}</div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${EVENT_STATUS_COLOR[ev.status] ?? 'bg-gray-700 text-gray-300'}`}>
            {ev.status}
          </span>
          {onToggle && (
            <button onClick={onToggle}
              className="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors">
              {expanded ? 'Close ▲' : 'Manage ▼'}
            </button>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-500">Change status:</label>
        <select defaultValue={ev.status} onChange={e => onStatusChange(e.target.value)}
          className="text-xs bg-gray-800 border border-gray-700 text-gray-300 rounded px-2 py-1">
          {EVENT_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
    </div>
  )
}

// ── Event detail: roster + fixture matrix ─────────────────────────────────────

const ACADEMY_PALETTE = [
  { bg: 'bg-blue-800', text: 'text-blue-100' },
  { bg: 'bg-purple-800', text: 'text-purple-100' },
  { bg: 'bg-green-800', text: 'text-green-100' },
  { bg: 'bg-amber-700', text: 'text-amber-100' },
  { bg: 'bg-red-800', text: 'text-red-100' },
  { bg: 'bg-cyan-800', text: 'text-cyan-100' },
  { bg: 'bg-pink-800', text: 'text-pink-100' },
  { bg: 'bg-indigo-800', text: 'text-indigo-100' },
]

function EventDetailPanel({ eventId, canManage }: { eventId: string; canManage: boolean }) {
  const [section, setSection] = useState<'roster' | 'fixtures'>('roster')
  const [roster, setRoster] = useState<EventRoster | null>(null)
  const [allPlayers, setAllPlayers] = useState<PlayerDirectoryItem[]>([])
  const [fixtures, setFixtures] = useState<EventFixtures | null>(null)
  const [rosterLoading, setRosterLoading] = useState(false)
  const [rosterError, setRosterError] = useState<string | null>(null)
  const [dirLoading, setDirLoading] = useState(false)
  const [fixturesLoading, setFixturesLoading] = useState(false)
  const [fixturesError, setFixturesError] = useState<string | null>(null)
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

  // Build colorMap from all academies in the directory
  const allAcademyIds = [...new Set(allPlayers.map(p => p.academy_id))]
  const colorMap = Object.fromEntries(allAcademyIds.map((id, i) => [id, ACADEMY_PALETTE[i % ACADEMY_PALETTE.length]]))

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
                {fixtureState === 'FIXTURES_READY' && ' Regenerate fixtures to modify the roster.'}
              </span>
            </div>
          )}

          {/* Player directory — all players grouped by academy */}
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
              <FixtureMatrix fixtures={fixtures} colorMap={colorMap} />
              <SlotResultList
                fixtures={fixtures}
                colorMap={colorMap}
                onEnterResult={setResultSlot}
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

const MATCH_DURATION_MIN: Record<string, number> = { BEST_OF_3: 18, BEST_OF_5: 30, BEST_OF_7: 45 }

function FixtureStats({ fixtures, matchFormat, numTables }: {
  fixtures: EventFixtures
  matchFormat: string
  numTables: number
}) {
  const CHANGEOVER = 3 // minutes between rounds

  const playerStats: Record<string, {
    total: number; cross: number; intra: number
    competitive: number; stretch: number; anchor: number; byes: number
    opponents: Set<string>
  }> = {}

  for (const slot of fixtures.slots) {
    const isBye = slot.status === 'BYE' || !slot.player_b
    const isCross = !isBye && slot.player_a.academy_id !== slot.player_b!.academy_id

    const upsert = (pid: string) => {
      if (!playerStats[pid]) playerStats[pid] = { total: 0, cross: 0, intra: 0, competitive: 0, stretch: 0, anchor: 0, byes: 0, opponents: new Set() }
    }

    upsert(slot.player_a.player_id)
    if (isBye) {
      playerStats[slot.player_a.player_id].byes++
    } else {
      const pb = slot.player_b!
      upsert(pb.player_id)
      for (const [pid, oppId] of [[slot.player_a.player_id, pb.player_id], [pb.player_id, slot.player_a.player_id]] as [string, string][]) {
        const s = playerStats[pid]
        s.total++
        s.opponents.add(oppId)
        if (isCross) s.cross++; else s.intra++
        if (slot.match_category === 'COMPETITIVE') s.competitive++
        else if (slot.match_category === 'STRETCH') s.stretch++
        else if (slot.match_category === 'ANCHOR') s.anchor++
      }
    }
  }

  const vals = Object.values(playerStats)
  if (!vals.length) return null

  const stat = (arr: number[]) => {
    const min = Math.min(...arr), max = Math.max(...arr)
    const avg = arr.reduce((a, b) => a + b, 0) / arr.length
    return { min, max, avg: Math.round(avg * 10) / 10 }
  }

  const matchesPS = stat(vals.map(v => v.total))
  const crossPS = stat(vals.map(v => v.cross))
  const intraPS = stat(vals.map(v => v.intra))
  const compPS = stat(vals.map(v => v.competitive))
  const strPS = stat(vals.map(v => v.stretch))
  const ancPS = stat(vals.map(v => v.anchor))
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
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
        <div>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Matches per player</p>
          <StatRow label="Total matches" s={matchesPS} />
          <StatRow label="Cross-academy" s={crossPS} accent="text-green-400" />
          <StatRow label="Intra-academy" s={intraPS} accent="text-blue-400" />
          <StatRow label="Unique opponents" s={oppPS} />
        </div>
        <div>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">By match category</p>
          <StatRow label="Competitive" s={compPS} accent="text-blue-400" />
          <StatRow label="Stretch" s={strPS} accent="text-purple-400" />
          {hasAnchor && <StatRow label="Anchor" s={ancPS} accent="text-green-400" />}
        </div>
      </div>
    </div>
  )
}

// ── Round-by-round slot list with Enter Result buttons ────────────────────────

const MATCH_CAT_COLOR: Record<string, string> = {
  COMPETITIVE: 'text-blue-400',
  STRETCH: 'text-purple-400',
  ANCHOR: 'text-green-400',
}

function SlotResultList({ fixtures, colorMap, onEnterResult }: {
  fixtures: EventFixtures
  colorMap: Record<string, { bg: string; text: string }>
  onEnterResult: (slot: EventFixtureSlot) => void
}) {
  const byRound = fixtures.slots.reduce<Record<number, EventFixtureSlot[]>>((acc, s) => {
    ;(acc[s.round_number] ??= []).push(s)
    return acc
  }, {})

  const scheduledCount = fixtures.slots.filter(s => s.status === 'SCHEDULED').length

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Enter Results</p>
        {scheduledCount > 0 && (
          <span className="text-xs text-yellow-400">{scheduledCount} match{scheduledCount !== 1 ? 'es' : ''} pending</span>
        )}
        {scheduledCount === 0 && (
          <span className="text-xs text-green-400">All matches completed</span>
        )}
      </div>
      {Object.entries(byRound).map(([rn, slots]) => (
        <div key={rn}>
          <div className="text-xs text-gray-500 mb-1.5 font-semibold uppercase tracking-wide">Round {rn}</div>
          <div className="space-y-1">
            {slots.map(slot => {
              if (slot.status === 'BYE' || !slot.player_b) {
                return (
                  <div key={slot.slot_id} className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 opacity-40">
                    <span className="text-xs text-gray-500 w-16 shrink-0">T{slot.table_number}</span>
                    <span className="text-sm text-gray-400">{slot.player_a.name}</span>
                    <span className="text-xs text-gray-600 italic">BYE</span>
                  </div>
                )
              }
              const aColor = colorMap[slot.player_a.academy_id] ?? ACADEMY_PALETTE[0]
              const bColor = colorMap[slot.player_b.academy_id] ?? ACADEMY_PALETTE[0]
              const isCross = slot.player_a.academy_id !== slot.player_b.academy_id
              return (
                <div key={slot.slot_id}
                  className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
                  <span className="text-xs text-gray-600 w-14 shrink-0">T{slot.table_number}</span>
                  <span className={`text-xs font-semibold shrink-0 ${MATCH_CAT_COLOR[slot.match_category] ?? 'text-gray-400'}`}>
                    {slot.match_category}
                  </span>
                  <div className="flex items-center gap-1.5 flex-1 min-w-0">
                    <span className={`text-sm font-medium truncate ${aColor.text}`}>{slot.player_a.name}</span>
                    {isCross && <span className={`text-[10px] px-1 rounded shrink-0 ${aColor.bg} ${aColor.text}`}>{slot.player_a.academy_name}</span>}
                    <span className="text-gray-600 text-xs shrink-0">vs</span>
                    <span className={`text-sm font-medium truncate ${bColor.text}`}>{slot.player_b.name}</span>
                    {isCross && <span className={`text-[10px] px-1 rounded shrink-0 ${bColor.bg} ${bColor.text}`}>{slot.player_b.academy_name}</span>}
                  </div>
                  <div className="shrink-0 ml-auto">
                    {slot.status === 'SCHEDULED' && (
                      <button onClick={() => onEnterResult(slot)}
                        className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition-colors">
                        Enter Result
                      </button>
                    )}
                    {slot.status === 'PLAYED' && (
                      <span className="text-xs text-green-400 font-medium">✓ Played</span>
                    )}
                    {slot.status === 'UNPLAYED' && (
                      <span className="text-xs text-gray-500">Unplayed</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Inter-academy result entry modal ──────────────────────────────────────────

const MAX_SETS_MAP: Record<string, number> = { BEST_OF_3: 2, BEST_OF_5: 3, BEST_OF_7: 4 }

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
            {slot.player_a.name} <span className="text-gray-500">vs</span> {slot.player_b!.name}
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

function FixtureMatrix({
  fixtures,
  colorMap,
}: {
  fixtures: EventFixtures
  colorMap: Record<string, { bg: string; text: string }>
}) {
  const [filterAcademyId, setFilterAcademyId] = useState<string | null>(null)
  const [highlightRound, setHighlightRound] = useState<number | null>(null)

  type Cell = { opponent: EventFixturePlayer | null; is_bye: boolean; category: string }
  const schedule: Record<string, Record<number, Cell>> = {}
  const playerById: Record<string, EventFixturePlayer> = {}

  for (const slot of fixtures.slots) {
    playerById[slot.player_a.player_id] = slot.player_a
    if (slot.player_b) playerById[slot.player_b.player_id] = slot.player_b
    const pa = slot.player_a.player_id
    const pb = slot.player_b?.player_id
    if (!schedule[pa]) schedule[pa] = {}
    schedule[pa][slot.round_number] = { opponent: slot.player_b, is_bye: !pb, category: slot.match_category }
    if (pb) {
      if (!schedule[pb]) schedule[pb] = {}
      schedule[pb][slot.round_number] = { opponent: slot.player_a, is_bye: false, category: slot.match_category }
    }
  }

  const byAcademy: Record<string, EventFixturePlayer[]> = {}
  for (const p of Object.values(playerById)) {
    (byAcademy[p.academy_id] ??= []).push(p)
  }
  for (const players of Object.values(byAcademy)) {
    players.sort((a, b) => b.current_rating - a.current_rating)
    const seen = new Set<string>()
    const key = Object.keys(byAcademy).find(k => byAcademy[k] === players)!
    byAcademy[key] = players.filter(p => { if (seen.has(p.player_id)) return false; seen.add(p.player_id); return true })
  }

  const rounds = Array.from({ length: fixtures.total_rounds }, (_, i) => i + 1)
  const academyIds = Object.keys(byAcademy)

  return (
    <div className="space-y-3">
      <div className="flex gap-1.5 flex-wrap">
        <button onClick={() => setFilterAcademyId(null)}
          className={`px-2 py-1 text-xs rounded transition-colors ${!filterAcademyId ? 'bg-white text-gray-900 font-medium' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
          All
        </button>
        {academyIds.map(id => {
          const color = colorMap[id] ?? ACADEMY_PALETTE[0]
          return (
            <button key={id} onClick={() => setFilterAcademyId(filterAcademyId === id ? null : id)}
              className={`px-2 py-1 text-xs rounded transition-colors ${filterAcademyId === id ? `${color.bg} ${color.text} font-medium` : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
              {byAcademy[id][0]?.academy_name}
            </button>
          )
        })}
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="text-xs border-collapse w-full">
          <thead>
            <tr className="bg-gray-900/80">
              <th className="text-left px-3 py-2 text-gray-500 border-b border-gray-800 sticky left-0 bg-gray-900 min-w-[130px] z-10">Player</th>
              <th className="text-right px-2 py-2 text-gray-500 border-b border-gray-800 min-w-[50px]">Rtg</th>
              {rounds.map(r => (
                <th key={r} onClick={() => setHighlightRound(highlightRound === r ? null : r)}
                  className={`text-center px-2 py-2 border-b border-gray-800 cursor-pointer min-w-[110px] select-none transition-colors ${
                    highlightRound === r ? 'bg-blue-900/40 text-blue-300' : 'text-gray-500 hover:text-gray-300'
                  }`}>
                  R{r}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {academyIds.map(academyId => {
              const players = byAcademy[academyId] ?? []
              const color = colorMap[academyId] ?? ACADEMY_PALETTE[0]
              const dimmed = filterAcademyId !== null && filterAcademyId !== academyId
              return [
                <tr key={`hdr-${academyId}`} className={dimmed ? 'opacity-20' : ''}>
                  <td colSpan={rounds.length + 2} className={`px-3 py-1 font-semibold text-xs ${color.text} border-b border-gray-800/50`}>
                    <span className={`inline-block w-2 h-2 rounded-full ${color.bg} mr-1.5`} />
                    {players[0]?.academy_name}
                  </td>
                </tr>,
                ...players.map(p => (
                  <tr key={p.player_id}
                    className={`border-b border-gray-900 ${dimmed ? 'opacity-20' : 'hover:bg-gray-800/20'}`}>
                    <td className="px-3 py-1.5 text-white font-medium sticky left-0 bg-gray-950 z-10">{p.name}</td>
                    <td className="px-2 py-1.5 text-gray-400 text-right">{Math.round(p.current_rating)}</td>
                    {rounds.map(r => {
                      const cell = schedule[p.player_id]?.[r]
                      const hilite = highlightRound === r ? 'bg-blue-900/15' : ''
                      if (!cell) return <td key={r} className={`px-2 py-1.5 text-center text-gray-700 ${hilite}`}>—</td>
                      if (cell.is_bye) return <td key={r} className={`px-2 py-1.5 text-center ${hilite}`}><span className="text-gray-600 italic">BYE</span></td>
                      const opp = cell.opponent!
                      const oppColor = colorMap[opp.academy_id] ?? ACADEMY_PALETTE[0]
                      const isCross = opp.academy_id !== academyId
                      return (
                        <td key={r} className={`px-1 py-1 ${hilite}`}>
                          <div className={`rounded px-1.5 py-0.5 ${isCross ? oppColor.bg : 'bg-gray-800'}`}>
                            <div className={`font-medium truncate max-w-[90px] ${isCross ? oppColor.text : 'text-gray-300'}`}>{opp.name}</div>
                            <div className={`text-[10px] opacity-80 ${isCross ? oppColor.text : 'text-gray-500'}`}>
                              {isCross ? `${opp.academy_name} · ` : ''}{Math.round(opp.current_rating)}
                            </div>
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                )),
              ]
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Academies ─────────────────────────────────────────────────────────────────

function AcademiesTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', location: '', city: '', state: '', min_tables: '4' })
  const [error, setError] = useState<string | null>(null)

  const q = useQuery({ queryKey: ['academies-list'], queryFn: () => academiesApi.list() })

  const createMut = useMutation({
    mutationFn: () => academiesApi.create({
      name: form.name, location: form.location,
      city: form.city, state: form.state,
      min_tables: Number(form.min_tables),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['academies-list'] }); setShowForm(false); setError(null) },
    onError: (e: Error) => setError(e.message),
  })

  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorMsg message={(q.error as Error).message} />

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-white">Academies</h3>
        <button onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg">
          {showForm ? 'Cancel' : '+ New Academy'}
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-4">
          {error && <ErrorMsg message={error} />}
          {[
            { key: 'name', label: 'Academy name', placeholder: 'Champion TT Academy' },
            { key: 'location', label: 'Address / location', placeholder: '12 Sports Complex, Sector 5' },
            { key: 'city', label: 'City', placeholder: 'Mumbai' },
            { key: 'state', label: 'State', placeholder: 'Maharashtra' },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-sm text-gray-400 mb-1">{label}</label>
              <input type="text" value={form[key as keyof typeof form]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                placeholder={placeholder} className={inputCls} />
            </div>
          ))}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Number of tables</label>
            <input type="number" min={1} value={form.min_tables}
              onChange={e => setForm(f => ({ ...f, min_tables: e.target.value }))} className={inputCls} />
          </div>
          <button onClick={() => createMut.mutate()}
            disabled={createMut.isPending || !form.name || !form.city || !form.state}
            className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg disabled:opacity-50">
            {createMut.isPending ? 'Creating…' : 'Create Academy'}
          </button>
        </div>
      )}

      <div className="space-y-2">
        {q.data?.items.map((a: AcademyListItem) => (
          <div key={a.academy_id} className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3 flex items-center justify-between">
            <div>
              <div className="font-medium text-white">{a.name}</div>
              <div className="text-xs text-gray-500">{a.city}, {a.state}</div>
              <div className="text-xs text-gray-700 font-mono">{a.academy_id}</div>
            </div>
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
              a.status === 'ACTIVE' ? 'bg-green-800 text-green-100' :
              a.status === 'FROZEN' ? 'bg-blue-800 text-blue-100' : 'bg-gray-700 text-gray-300'
            }`}>{a.status}</span>
          </div>
        ))}
        {!q.data?.items.length && <p className="text-gray-500 text-sm">No academies yet.</p>}
      </div>
    </div>
  )
}

// ── Disputes ──────────────────────────────────────────────────────────────────

const DISPUTE_STATUS_COLOR: Record<string, string> = {
  OPEN: 'bg-yellow-700 text-yellow-100',
  UNDER_REVIEW: 'bg-blue-700 text-blue-100',
  RESOLVED: 'bg-green-700 text-green-100',
  EXPIRED: 'bg-gray-700 text-gray-300',
}

function DisputeQueue() {
  const [statusFilter, setStatusFilter] = useState('')
  const [resolveId, setResolveId] = useState<string | null>(null)
  const [resolution, setResolution] = useState('CONFIRMED_ORIGINAL')
  const qc = useQueryClient()

  const q = useQuery({
    queryKey: ['disputes', statusFilter],
    queryFn: () => disputesApi.list({ status: statusFilter || undefined, limit: 50 }),
  })

  const reviewMut = useMutation({
    mutationFn: (id: string) => disputesApi.updateStatus(id, 'UNDER_REVIEW'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['disputes'] }),
  })
  const resolveMut = useMutation({
    mutationFn: ({ id, resolution }: { id: string; resolution: string }) =>
      disputesApi.resolve(id, { resolution }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['disputes'] }); setResolveId(null) },
  })

  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorMsg message={(q.error as Error).message} />

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {['', 'OPEN', 'UNDER_REVIEW', 'RESOLVED', 'EXPIRED'].map(s => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              statusFilter === s ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}`}>
            {s || 'All'}
          </button>
        ))}
      </div>
      {q.data?.items.length === 0 && <p className="text-gray-500 text-sm">No disputes found.</p>}
      <div className="space-y-3">
        {q.data?.items.map(d => {
          const hoursLeft = Math.max(0, (new Date(d.resolution_deadline).getTime() - Date.now()) / 3600000)
          return (
            <div key={d.dispute_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-gray-500">{d.dispute_id.slice(0, 8)}</span>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${DISPUTE_STATUS_COLOR[d.status] ?? ''}`}>{d.status}</span>
                  {d.status === 'OPEN' && <span className={`text-xs ${hoursLeft < 12 ? 'text-red-400' : 'text-gray-400'}`}>{hoursLeft.toFixed(0)}h left</span>}
                </div>
                <div className="flex gap-2">
                  {d.status === 'OPEN' && (
                    <button onClick={() => reviewMut.mutate(d.dispute_id)} className="text-xs px-3 py-1.5 bg-blue-700 hover:bg-blue-600 text-white rounded-lg">Review</button>
                  )}
                  {(d.status === 'OPEN' || d.status === 'UNDER_REVIEW') && (
                    <button onClick={() => setResolveId(resolveId === d.dispute_id ? null : d.dispute_id)}
                      className="text-xs px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white rounded-lg">Resolve</button>
                  )}
                </div>
              </div>
              <div className="text-sm text-gray-300">{d.dispute_reason}</div>
              {resolveId === d.dispute_id && (
                <div className="bg-gray-800 rounded-lg p-3 space-y-2">
                  <select value={resolution} onChange={e => setResolution(e.target.value)} className={selectCls}>
                    <option value="CONFIRMED_ORIGINAL">Confirm original result</option>
                    <option value="VOIDED">Void the match</option>
                  </select>
                  <div className="flex gap-2">
                    <button onClick={() => resolveMut.mutate({ id: d.dispute_id, resolution })}
                      disabled={resolveMut.isPending}
                      className="px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-sm rounded-lg disabled:opacity-50">
                      {resolveMut.isPending ? 'Resolving…' : 'Confirm'}
                    </button>
                    <button onClick={() => setResolveId(null)} className="px-3 py-1.5 bg-gray-700 text-gray-300 text-sm rounded-lg">Cancel</button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Config ────────────────────────────────────────────────────────────────────

function ConfigEditor() {
  const qc = useQueryClient()
  const [editKey, setEditKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [editReason, setEditReason] = useState('')

  const q = useQuery({ queryKey: ['config'], queryFn: () => configApi.get() })
  const mut = useMutation({
    mutationFn: () => configApi.update(editKey!, editValue, editReason),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['config'] }); setEditKey(null) },
  })

  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorMsg message={(q.error as Error).message} />

  return (
    <div className="space-y-3">
      {q.data?.items.map(entry => (
        <div key={entry.key} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div>
              <span className="font-mono text-sm text-blue-400">{entry.key}</span>
              {entry.description && <span className="ml-2 text-xs text-gray-500">{entry.description}</span>}
            </div>
            <button onClick={() => { setEditKey(editKey === entry.key ? null : entry.key); setEditValue(entry.value); setEditReason('') }}
              className="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded">Edit</button>
          </div>
          {editKey === entry.key ? (
            <div className="space-y-2">
              <input type="text" value={editValue} onChange={e => setEditValue(e.target.value)} className={inputCls} />
              <input type="text" placeholder="Reason for change" value={editReason} onChange={e => setEditReason(e.target.value)} className={inputCls} />
              <div className="flex gap-2">
                <button onClick={() => mut.mutate()} disabled={mut.isPending || !editReason}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded disabled:opacity-50">Save</button>
                <button onClick={() => setEditKey(null)} className="px-3 py-1.5 bg-gray-700 text-gray-300 text-sm rounded">Cancel</button>
              </div>
              {mut.error && <ErrorMsg message={(mut.error as Error).message} />}
            </div>
          ) : (
            <div className="font-mono text-white">{entry.value}</div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Shared styles ─────────────────────────────────────────────────────────────

const inputCls = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 placeholder-gray-600'
const selectCls = 'w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500'
