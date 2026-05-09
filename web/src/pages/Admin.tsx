import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  disputesApi, configApi, seasonsApi, eventsApi, academiesApi,
  type Season, type Event, type AcademyListItem,
} from '../api/client'
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
  const [createdEvents, setCreatedEvents] = useState<Event[]>([])
  const [form, setForm] = useState({
    name: '', scheduling_mode: 'INTRA_ACADEMY', event_type: 'FRIENDLY',
    default_match_format: 'BEST_OF_3', start_date: '', end_date: '',
    season_id: '', host_academy_id: '',
  })
  const [error, setError] = useState<string | null>(null)

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
    onSuccess: ev => {
      setCreatedEvents(prev => [ev, ...prev])
      setShowForm(false)
      setError(null)
      setForm({ name: '', scheduling_mode: 'INTRA_ACADEMY', event_type: 'FRIENDLY', default_match_format: 'BEST_OF_3', start_date: '', end_date: '', season_id: '', host_academy_id: '' })
    },
    onError: (e: Error) => setError(e.message),
  })

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => eventsApi.updateStatus(id, status),
    onSuccess: updated => setCreatedEvents(prev => prev.map(e => e.event_id === updated.event_id ? updated : e)),
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
        {createdEvents.map(ev => (
          <EventCard key={ev.event_id} event={ev}
            onStatusChange={(status) => statusMut.mutate({ id: ev.event_id, status })} />
        ))}
        {createdEvents.length === 0 && !showForm && (
          <p className="text-gray-500 text-sm">No events created in this session. Events created in past sessions are visible via the API.</p>
        )}
      </div>
    </div>
  )
}

function EventCard({ event: ev, onStatusChange }: { event: Event; onStatusChange: (s: string) => void }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-2">
      <div className="flex items-start justify-between flex-wrap gap-2">
        <div>
          <div className="font-medium text-white">{ev.name}</div>
          <div className="text-xs text-gray-500 mt-0.5">
            {ev.scheduling_mode.replace('_', ' ')} · {ev.event_type.replace(/_/g, ' ')} · {ev.start_date}
            {ev.end_date && ` → ${ev.end_date}`}
          </div>
          <div className="text-xs text-gray-600 font-mono mt-1">{ev.event_id}</div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${EVENT_STATUS_COLOR[ev.status] ?? 'bg-gray-700 text-gray-300'}`}>
          {ev.status}
        </span>
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
