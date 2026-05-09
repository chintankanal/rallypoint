import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { playersApi, type RatingHistoryEntry } from '../api/client'
import { Layout, TierBadge, CRBar, Spinner, ErrorMsg } from '../components/Layout'
import { useAuth } from '../auth/context'

const PERIODS = ['1m', '3m', '6m', '1y'] as const

// ── Grouping helpers ──────────────────────────────────────────────────────────

interface SessionGroup {
  session_id: string | null
  session_date: string | null
  matches: RatingHistoryEntry[]
}

interface EventGroup {
  event_id: string | null
  event_name: string | null
  event_type: string | null
  sessions: SessionGroup[]
}

function groupByEventSession(items: RatingHistoryEntry[]): EventGroup[] {
  const eventMap = new Map<string, EventGroup>()
  for (const item of items) {
    const eid = item.event_id ?? '__none__'
    if (!eventMap.has(eid)) {
      eventMap.set(eid, {
        event_id: item.event_id,
        event_name: item.event_name,
        event_type: item.event_type,
        sessions: [],
      })
    }
    const eg = eventMap.get(eid)!
    const sid = item.session_id ?? '__adhoc__'
    let sg = eg.sessions.find(s => (s.session_id ?? '__adhoc__') === sid)
    if (!sg) {
      sg = { session_id: item.session_id, session_date: item.session_date, matches: [] }
      eg.sessions.push(sg)
    }
    sg.matches.push(item)
  }
  return Array.from(eventMap.values())
}

function netDelta(matches: RatingHistoryEntry[]): number {
  return matches.reduce((acc, m) => acc + m.delta, 0)
}

function formatScore(entry: RatingHistoryEntry, playerId: string): string {
  if (entry.sets_won_a === null || entry.sets_won_b === null) return '—'
  // We need to figure out which side this player was on.
  // We can't know player_a vs player_b from the entry alone, but result tells us winner.
  // Just show the score as a–b where a is this player's sets.
  // delta > 0 means WIN, so winner's sets are the higher number.
  const won = entry.result === 'WIN'
  const winSets = Math.max(entry.sets_won_a, entry.sets_won_b)
  const loseSets = Math.min(entry.sets_won_a, entry.sets_won_b)
  return won ? `${winSets}–${loseSets}` : `${loseSets}–${winSets}`
}

function matchTypeBadge(r: RatingHistoryEntry) {
  if (!r.match_category) return <span className="text-gray-600">—</span>

  if (r.match_category === 'COMPETITIVE') {
    return (
      <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-900/50 text-blue-300">
        Competitive
      </span>
    )
  }

  if (r.match_category === 'STRETCH') {
    const oppRating = r.opponent_rating_before
    if (oppRating != null && r.rating_before < oppRating) {
      return (
        <span
          className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-900/50 text-purple-300"
          title="Playing up against a stronger opponent"
        >
          Stretch ↑
        </span>
      )
    }
    if (oppRating != null && r.rating_before > oppRating) {
      return (
        <span
          className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-900/50 text-amber-400"
          title="Playing down as the stronger player"
        >
          Anchor ↓
        </span>
      )
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-900/50 text-purple-300">
        Stretch
      </span>
    )
  }

  return (
    <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">
      {r.match_category.charAt(0) + r.match_category.slice(1).toLowerCase()}
    </span>
  )
}

const EVENT_TYPE_META: Record<string, { label: string; style: string }> = {
  INTRA_ACADEMY: { label: 'Training · Friendly', style: 'bg-gray-700 text-gray-400' },
  LEAGUE:        { label: 'League',              style: 'bg-green-900/60 text-green-300' },
  TOURNAMENT:    { label: 'Tournament',           style: 'bg-yellow-900/60 text-yellow-300' },
}

function eventTypeBadge(type: string | null) {
  if (!type) return null
  const meta = EVENT_TYPE_META[type] ?? { label: type.replace(/_/g, ' '), style: 'bg-gray-700 text-gray-300' }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${meta.style}`}>
      {meta.label}
    </span>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function PlayerDetail() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const [period, setPeriod] = useState<'1m' | '3m' | '6m' | '1y'>('3m')
  const [historyTab, setHistoryTab] = useState<'session' | 'timeline'>('session')
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set())
  const [expandedBreakdowns, setExpandedBreakdowns] = useState<Set<string>>(new Set())

  function toggleSession(key: string) {
    setExpandedSessions(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function toggleBreakdown(historyId: string) {
    setExpandedBreakdowns(prev => {
      const next = new Set(prev)
      next.has(historyId) ? next.delete(historyId) : next.add(historyId)
      return next
    })
  }

  const playerQ = useQuery({
    queryKey: ['player', id],
    queryFn: () => playersApi.get(id!),
    enabled: !!id,
  })

  const statsQ = useQuery({
    queryKey: ['player', id, 'stats'],
    queryFn: () => playersApi.computedStats(id!),
    enabled: !!id,
  })

  const historyQ = useQuery({
    queryKey: ['player', id, 'history'],
    queryFn: () => playersApi.ratingHistory(id!, { limit: 200 }),
    enabled: !!id,
  })

  const velocityQ = useQuery({
    queryKey: ['player', id, 'velocity', period],
    queryFn: () => playersApi.velocity(id!, period),
    enabled: !!id,
  })

  const p = playerQ.data
  const s = statsQ.data
  const h = historyQ.data
  const v = velocityQ.data

  if (playerQ.isLoading) return <Layout><Spinner /></Layout>
  if (playerQ.error) return <Layout><ErrorMsg message={(playerQ.error as Error).message} /></Layout>
  if (!p) return null

  const isSelf = user?.user_id === id
  const canSeeBreakdown = isSelf || user?.role === 'COACH' || user?.role === 'ADMIN'

  const sortedItems = h?.items.slice().reverse() // oldest-first after backend DESC order
  const chartData = sortedItems && sortedItems.length > 0
    ? [
        {
          seq: 0,
          date: (sortedItems[0].match_date ?? sortedItems[0].created_at ?? '').slice(0, 10),
          rating: Math.round(sortedItems[0].rating_before),
        },
        ...sortedItems.map((r, i) => ({
          seq: i + 1,
          date: (r.match_date ?? r.created_at ?? '').slice(0, 10),
          rating: Math.round(r.rating_after),
        })),
      ]
    : undefined

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header card */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex flex-wrap items-start gap-4">
            <div className="flex-1 min-w-0">
              <h2 className="text-2xl font-bold text-white">{p.name}</h2>
              <p className="text-gray-400 text-sm mt-1">
                {p.primary_academy?.name ?? 'No academy'}
                {p.primary_academy && (p.primary_academy as any).city && ` · ${(p.primary_academy as any).city}`}
              </p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
                {p.gender && <span>{p.gender === 'MALE' ? 'Male' : 'Female'}</span>}
                {p.nationality && p.nationality !== 'India' && <span>{p.nationality}</span>}
                {p.date_of_birth && <span>DOB: {p.date_of_birth}</span>}
              </div>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold font-mono text-white">
                {Math.round(p.current_rating)}
              </div>
              <div className="text-gray-400 text-sm">rating</div>
            </div>
          </div>

          {s && (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-1">Tier</div>
                <TierBadge tier={s.tier} />
                {s.is_provisional && (
                  <span className="ml-1 text-yellow-400 text-xs">Provisional</span>
                )}
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Confidence</div>
                <CRBar value={s.confidence_ratio} />
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Rated Matches</div>
                <div className="font-semibold text-white">{p.rated_matches_completed ?? 0}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Weeks Inactive</div>
                <div className={`font-semibold ${s.weeks_inactive !== null && s.weeks_inactive >= 8 ? 'text-red-400' : 'text-white'}`}>
                  {s.weeks_inactive !== null ? s.weeks_inactive.toFixed(1) : '—'}
                </div>
              </div>
            </div>
          )}

          {canSeeBreakdown && (p.guardian_name || p.guardian_phone || p.contact_email) && (
            <div className="mt-4 pt-4 border-t border-gray-800">
              <div className="text-xs text-gray-500 mb-2">Contact</div>
              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-300">
                {p.guardian_name && <span>{p.guardian_name}</span>}
                {p.guardian_phone && <span>{p.guardian_phone}</span>}
                {p.contact_email && <span>{p.contact_email}</span>}
              </div>
            </div>
          )}
        </div>

        {/* Velocity */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">Rating Velocity</h3>
            <div className="flex gap-1">
              {PERIODS.map(p => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                    period === p ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white bg-gray-800'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {velocityQ.isLoading && <Spinner />}
          {v && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
                <Stat label="Net Δ" value={`${v.rating_change > 0 ? '+' : ''}${v.rating_change.toFixed(1)}`}
                  color={v.rating_change >= 0 ? 'text-green-400' : 'text-red-400'} />
                <Stat label="Matches" value={String(v.matches_played)} />
                <Stat label="Win Rate" value={`${(v.win_rate * 100).toFixed(0)}%`} />
                <Stat label="Stretch Win Rate"
                  value={v.stretch_win_rate !== null ? `${(v.stretch_win_rate * 100).toFixed(0)}%` : '—'} />
              </div>

              {chartData && chartData.length > 1 && (() => {
                const uniqueDates = [...new Set(chartData.map(d => d.date))]
                const lastSeq = chartData[chartData.length - 1].seq
                return (
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={chartData}>
                    <XAxis
                      dataKey="seq"
                      tick={{ fill: '#9ca3af', fontSize: 10 }}
                      tickFormatter={i => {
                        if (i === 0) return 'Start'
                        if (uniqueDates.length === 1) return i === lastSeq ? uniqueDates[0] : ''
                        return chartData.find(d => d.seq === i)?.date ?? ''
                      }}
                      axisLine={{ stroke: '#374151' }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: '#9ca3af', fontSize: 11 }}
                      domain={(['dataMin', 'dataMax'] as [string, string])}
                      tickCount={5}
                    />
                    <Tooltip
                      contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                      labelStyle={{ color: '#9ca3af', fontSize: 11 }}
                      labelFormatter={(_, payload) =>
                        payload?.[0]?.payload?.seq === 0
                          ? `Start · ${payload[0].payload.date}`
                          : `Match ${payload?.[0]?.payload?.seq} · ${payload?.[0]?.payload?.date ?? ''}`
                      }
                      formatter={(value: number) => [value, 'Rating']}
                    />
                    <Line type="monotone" dataKey="rating" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
                )
              })()}
            </>
          )}
        </div>

        {/* Match history */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">Match History</h3>
            <div className="flex gap-1">
              {(['session', 'timeline'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setHistoryTab(tab)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    historyTab === tab ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white bg-gray-800'
                  }`}
                >
                  {tab === 'session' ? 'By Session' : 'Timeline'}
                </button>
              ))}
            </div>
          </div>

          {historyQ.isLoading && <Spinner />}

          {h && h.items.length === 0 && (
            <p className="text-gray-500 text-sm">No rated matches yet.</p>
          )}

          {/* ── By Session tab ── */}
          {h && h.items.length > 0 && historyTab === 'session' && (() => {
            const groups = groupByEventSession(h.items)
            return (
              <div className="space-y-4">
                {groups.map(eg => {
                  const allMatches = eg.sessions.flatMap(s => s.matches)
                  const net = netDelta(allMatches)
                  return (
                    <div key={eg.event_id ?? 'none'} className="border border-gray-800 rounded-lg overflow-hidden">
                      {/* Event header */}
                      <div className="flex items-center gap-3 px-4 py-3 bg-gray-800/60">
                        <span className="font-medium text-white text-sm flex-1 truncate">
                          {eg.event_name ?? 'Unknown Event'}
                        </span>
                        {eventTypeBadge(eg.event_type)}
                        <span className="text-xs text-gray-400">{allMatches.length} matches</span>
                        <span className={`text-xs font-mono font-semibold w-14 text-right ${net >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {net >= 0 ? '+' : ''}{net.toFixed(1)}
                        </span>
                      </div>

                      {/* Sessions */}
                      <div className="divide-y divide-gray-800">
                        {eg.sessions.map(sg => {
                          const sessionKey = `${eg.event_id}-${sg.session_id ?? 'adhoc'}`
                          const sessionNet = netDelta(sg.matches)
                          const isExpanded = expandedSessions.has(sessionKey)
                          return (
                            <div key={sessionKey}>
                              {/* Session row (clickable) */}
                              <button
                                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800/40 transition-colors text-left"
                                onClick={() => toggleSession(sessionKey)}
                              >
                                <span className="text-gray-500 text-xs w-4">{isExpanded ? '▾' : '▸'}</span>
                                <span className="text-sm text-gray-300 flex-1">
                                  {sg.session_date
                                    ? `Session · ${sg.session_date}`
                                    : 'Ad-hoc matches'}
                                </span>
                                <span className="text-xs text-gray-500">{sg.matches.length} matches</span>
                                <span className={`text-xs font-mono font-semibold w-14 text-right ${sessionNet >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                  {sessionNet >= 0 ? '+' : ''}{sessionNet.toFixed(1)}
                                </span>
                              </button>

                              {/* Match rows */}
                              {isExpanded && (
                                <div className="bg-gray-950/40 overflow-x-auto">
                                  <table className="w-full text-xs min-w-[640px]">
                                    <thead>
                                      <tr className="text-gray-500 border-b border-gray-800">
                                        <th className="px-3 py-2 text-left w-12">Result</th>
                                        <th className="px-3 py-2 text-left">Opponent</th>
                                        <th className="px-3 py-2 text-left hidden sm:table-cell">Score</th>
                                        <th className="px-3 py-2 text-left">Type</th>
                                        <th className="px-3 py-2 text-right">Opp. Rtg</th>
                                        <th className="px-3 py-2 text-right">Before → After</th>
                                        <th className="px-3 py-2 text-left hidden md:table-cell">Tier</th>
                                        <th className="px-3 py-2 text-right hidden lg:table-cell">K-eff</th>
                                        <th className="px-3 py-2 text-right hidden lg:table-cell">Exp. Win</th>
                                        <th className="px-3 py-2 text-right w-14">Δ</th>
                                        {canSeeBreakdown && <th className="px-3 py-2 w-6"></th>}
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-800/60">
                                      {sg.matches.map(r => {
                                        const totalCols = canSeeBreakdown ? 11 : 10
                                        return (
                                          <>
                                            <tr key={r.history_id} className="hover:bg-gray-800/30 transition-colors">
                                              <td className="px-3 py-2">
                                                <span className={`font-bold ${r.result === 'WIN' ? 'text-green-400' : 'text-red-400'}`}>
                                                  {r.result}
                                                </span>
                                              </td>
                                              <td className="px-3 py-2">
                                                <div className="text-gray-300">vs {r.opponent_name ?? '—'}</div>
                                              </td>
                                              <td className="px-3 py-2 text-gray-400 hidden sm:table-cell font-mono">
                                                {formatScore(r, id!)}
                                              </td>
                                              <td className="px-3 py-2">
                                                <div className="flex flex-wrap gap-1 items-center">
                                                  {matchTypeBadge(r)}
                                                  {r.diminishing_signal_applied && (
                                                    <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-orange-900/50 text-orange-300" title="Diminishing signal — treated as Friendly">DS</span>
                                                  )}
                                                </div>
                                              </td>
                                              <td className="px-3 py-2 text-right text-gray-400 font-mono">
                                                {r.opponent_rating_before != null ? Math.round(r.opponent_rating_before) : '—'}
                                              </td>
                                              <td className="px-3 py-2 text-right font-mono text-gray-300 whitespace-nowrap">
                                                {Math.round(r.rating_before)} → {Math.round(r.rating_after)}
                                              </td>
                                              <td className="px-3 py-2 text-left hidden md:table-cell text-xs whitespace-nowrap">
                                                {r.tier_before === r.tier_after
                                                  ? <span className="text-gray-400">{r.tier_before}</span>
                                                  : <span className="text-yellow-400">{r.tier_before} → {r.tier_after}</span>}
                                              </td>
                                              <td className="px-3 py-2 text-right text-gray-400 font-mono hidden lg:table-cell">
                                                {r.k_eff !== null ? r.k_eff.toFixed(1) : '—'}
                                              </td>
                                              <td className="px-3 py-2 text-right text-gray-400 font-mono hidden lg:table-cell">
                                                {r.expected_score !== null ? `${(r.expected_score * 100).toFixed(0)}%` : '—'}
                                              </td>
                                              <td className={`px-3 py-2 text-right font-mono font-semibold ${r.delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {r.delta >= 0 ? '+' : ''}{r.delta.toFixed(1)}
                                              </td>
                                              {canSeeBreakdown && (
                                                <td className="px-3 py-2 text-center">
                                                  {r.delta_breakdown && (
                                                    <button
                                                      onClick={() => toggleBreakdown(r.history_id)}
                                                      className="text-gray-600 hover:text-gray-300 transition-colors"
                                                      title="Toggle breakdown"
                                                    >
                                                      {expandedBreakdowns.has(r.history_id) ? '▴' : '▾'}
                                                    </button>
                                                  )}
                                                </td>
                                              )}
                                            </tr>
                                            {canSeeBreakdown && expandedBreakdowns.has(r.history_id) && r.delta_breakdown && (
                                              <tr key={`${r.history_id}-bd`}>
                                                <td colSpan={totalCols} className="px-4 py-2 bg-gray-900">
                                                  <pre className="text-xs text-gray-400 overflow-x-auto">
                                                    {JSON.stringify(r.delta_breakdown, null, 2)}
                                                  </pre>
                                                </td>
                                              </tr>
                                            )}
                                          </>
                                        )
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </div>
            )
          })()}

          {/* ── Timeline tab ── */}
          {h && h.items.length > 0 && historyTab === 'timeline' && (
            <div className="space-y-1">
              {h.items.map(r => (
                <div key={r.history_id}>
                  <div className="flex items-center gap-3 py-2 border-b border-gray-800 last:border-0">
                    <span className={`w-10 text-xs font-bold ${r.result === 'WIN' ? 'text-green-400' : 'text-red-400'}`}>
                      {r.result}
                    </span>
                    <span className="flex-1 text-sm text-gray-300 truncate">vs {r.opponent_name}</span>
                    <span className="text-xs text-gray-500 hidden sm:block">{r.event_name ?? '—'}</span>
                    <span className="text-xs text-gray-500">{r.match_date?.slice(0, 10) ?? '—'}</span>
                    {r.tier_before === r.tier_after
                      ? <span className="text-xs text-gray-500 hidden md:block">{r.tier_before}</span>
                      : <span className="text-xs text-yellow-400 hidden md:block whitespace-nowrap">{r.tier_before} → {r.tier_after}</span>}
                    <span className={`text-xs font-mono font-semibold w-14 text-right ${r.delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {r.delta >= 0 ? '+' : ''}{r.delta.toFixed(1)}
                    </span>
                    {canSeeBreakdown && r.delta_breakdown && (
                      <button
                        onClick={() => toggleBreakdown(`tl-${r.history_id}`)}
                        className="text-gray-600 hover:text-gray-300 transition-colors text-xs"
                      >
                        {expandedBreakdowns.has(`tl-${r.history_id}`) ? '▴' : '▾'}
                      </button>
                    )}
                  </div>
                  {canSeeBreakdown && expandedBreakdowns.has(`tl-${r.history_id}`) && r.delta_breakdown && (
                    <pre className="text-xs text-gray-400 bg-gray-800 p-2 rounded overflow-x-auto mb-1">
                      {JSON.stringify(r.delta_breakdown, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}

function Stat({
  label,
  value,
  color,
}: {
  label: string
  value: string
  color?: string
}) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`font-semibold text-lg ${color ?? 'text-white'}`}>{value}</div>
    </div>
  )
}
