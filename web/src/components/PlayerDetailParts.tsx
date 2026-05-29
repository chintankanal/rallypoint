import React from 'react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts'
import { TierBadge, CRBar } from './Layout'
import { type PlayerDetail, type ComputedStats, type RatingHistoryEntry, type VelocityReport } from '../api/client'

const PERIODS = ['1m', '3m', '6m', '1y'] as const

export interface ChartPoint { seq: number; date: string; rating: number }

export function netDelta(matches: RatingHistoryEntry[]): number {
  return matches.reduce((acc, m) => acc + m.delta, 0)
}

export function formatScore(entry: RatingHistoryEntry): string {
  if (entry.sets_won_a === null || entry.sets_won_b === null) return '—'
  const won = entry.result === 'WIN'
  const winSets = Math.max(entry.sets_won_a, entry.sets_won_b)
  const loseSets = Math.min(entry.sets_won_a, entry.sets_won_b)
  return won ? `${winSets}–${loseSets}` : `${loseSets}–${winSets}`
}

export function matchTypeBadge(r: RatingHistoryEntry) {
  const type = r.round_intent || r.gap_band || r.match_category
  if (!type) return <span className="text-gray-600">—</span>

  if (type === 'COMPETITIVE') {
    return (
      <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-900/50 text-blue-300">Competitive</span>
    )
  }

  if (type === 'DEVELOPMENTAL') {
    return (
      <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">Developmental</span>
    )
  }

  if (type === 'OUT_OF_BAND') {
    return (
      <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-orange-900/50 text-orange-200">Out of band</span>
    )
  }

  if (type === 'STRETCH') {
    const oppRating = r.opponent_rating_before
    if (oppRating != null && r.rating_before < oppRating) {
      return (
        <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-900/50 text-purple-300" title="Playing up against a stronger opponent">Stretch ↑</span>
      )
    }
    if (oppRating != null && r.rating_before > oppRating) {
      return (
        <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-900/50 text-amber-400" title="Playing down as the stronger player">Anchor ↓</span>
      )
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-900/50 text-purple-300">Stretch</span>
    )
  }

  return (
    <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">{type.charAt(0) + type.slice(1).toLowerCase()}</span>
  )
}

const EVENT_TYPE_META: Record<string, { label: string; style: string }> = {
  INTRA_ACADEMY: { label: 'Training · Friendly', style: 'bg-gray-700 text-gray-400' },
  LEAGUE:        { label: 'League',              style: 'bg-green-900/60 text-green-300' },
  TOURNAMENT:    { label: 'Tournament',           style: 'bg-yellow-900/60 text-yellow-300' },
}

export function eventTypeBadge(type: string | null) {
  if (!type) return null
  const meta = EVENT_TYPE_META[type] ?? { label: type.replace(/_/g, ' '), style: 'bg-gray-700 text-gray-300' }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${meta.style}`}>{meta.label}</span>
  )
}

export function PlayerHeader({ player, stats, canSeeBreakdown }: { player: PlayerDetail; stats?: ComputedStats; canSeeBreakdown: boolean }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold text-white">{player.name}</h2>
          <p className="text-gray-400 text-sm mt-1">
            {player.primary_academy?.name ?? 'No academy'}
            {player.primary_academy && (player.primary_academy as any).city && ` · ${(player.primary_academy as any).city}`}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
            {player.gender && <span>{player.gender === 'MALE' ? 'Male' : 'Female'}</span>}
            {player.nationality && player.nationality !== 'India' && <span>{player.nationality}</span>}
            {player.date_of_birth && <span>DOB: {player.date_of_birth}</span>}
          </div>
        </div>
        <div className="text-right">
          <div className="text-4xl font-bold font-mono text-white">{Math.round(player.current_rating)}</div>
          <div className="text-gray-400 text-sm">rating</div>
        </div>
      </div>

      {stats && (
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Tier</div>
            <TierBadge tier={stats.tier} />
            {stats.is_provisional && <span className="ml-1 text-yellow-400 text-xs">Provisional</span>}
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Confidence</div>
            <CRBar value={stats.confidence_ratio} />
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Rated Matches</div>
            <div className="font-semibold text-white">{player.rated_matches_completed ?? 0}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Weeks Inactive</div>
            <div className={`font-semibold ${stats.weeks_inactive !== null && stats.weeks_inactive >= 8 ? 'text-red-400' : 'text-white'}`}>
              {stats.weeks_inactive !== null ? stats.weeks_inactive.toFixed(1) : '—'}
            </div>
          </div>
        </div>
      )}

      {canSeeBreakdown && (player.guardian_name || player.guardian_phone || player.contact_email) && (
        <div className="mt-4 pt-4 border-t border-gray-800">
          <div className="text-xs text-gray-500 mb-2">Contact</div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-300">
            {player.guardian_name && <span>{player.guardian_name}</span>}
            {player.guardian_phone && <span>{player.guardian_phone}</span>}
            {player.contact_email && <span>{player.contact_email}</span>}
          </div>
        </div>
      )}
    </div>
  )
}

export function VelocitySection({ period, setPeriod, isLoading, velocity, chartData }: {
  period: '1m' | '3m' | '6m' | '1y'
  setPeriod: (p: '1m' | '3m' | '6m' | '1y') => void
  isLoading: boolean
  velocity?: VelocityReport | null
  chartData?: ChartPoint[] | undefined
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-white">Rating Velocity</h3>
        <div className="flex gap-1">
          {PERIODS.map(p => (
            <button key={p} onClick={() => setPeriod(p)} className={`px-2 py-1 rounded text-xs font-medium transition-colors ${period === p ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white bg-gray-800'}`}>
              {p}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <div className="p-4">Loading…</div>}
      {velocity && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Net Δ</div>
              <div className={`font-semibold text-lg ${velocity.rating_change >= 0 ? 'text-green-400' : 'text-red-400'}`}>{velocity.rating_change >= 0 ? '+' : ''}{velocity.rating_change.toFixed(1)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Matches</div>
              <div className="font-semibold text-lg">{String(velocity.matches_played)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Win Rate</div>
              <div className="font-semibold text-lg">{(velocity.win_rate * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Stretch Win Rate</div>
              <div className="font-semibold text-lg">{velocity.stretch_win_rate !== null ? `${(velocity.stretch_win_rate * 100).toFixed(0)}%` : '—'}</div>
            </div>
          </div>

          {chartData && chartData.length > 1 && (() => {
            const uniqueDates = [...new Set(chartData.map(d => d.date))]
            const lastSeq = chartData[chartData.length - 1].seq
            return (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={chartData}>
                  <XAxis dataKey="seq" tick={{ fill: '#9ca3af', fontSize: 10 }} tickFormatter={i => {
                    if (i === 0) return 'Start'
                    if (uniqueDates.length === 1) return i === lastSeq ? uniqueDates[0] : ''
                    return chartData.find(d => d.seq === i)?.date ?? ''
                  }} axisLine={{ stroke: '#374151' }} tickLine={false} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} domain={["dataMin", "dataMax"] as any} tickCount={5} />
                  <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }} labelStyle={{ color: '#9ca3af', fontSize: 11 }} labelFormatter={(_, payload) => payload?.[0]?.payload?.seq === 0 ? `Start · ${payload[0].payload.date}` : `Match ${payload?.[0]?.payload?.seq} · ${payload?.[0]?.payload?.date ?? ''}`} formatter={(value: any) => [value ?? '—', 'Rating']} />
                  <Line type="monotone" dataKey="rating" stroke="#3b82f6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )
          })()}
        </>
      )}
    </div>
  )
}

export function MatchHistory({
  history,
  historyTab,
  setHistoryTab,
  expandedSessions,
  toggleSession,
  expandedBreakdowns,
  toggleBreakdown,
  canSeeBreakdown,
}: {
  history?: { items: RatingHistoryEntry[] } | undefined
  historyTab: 'session' | 'timeline'
  setHistoryTab: (t: 'session' | 'timeline') => void
  expandedSessions: Set<string>
  toggleSession: (k: string) => void
  expandedBreakdowns: Set<string>
  toggleBreakdown: (id: string) => void
  canSeeBreakdown: boolean
}) {
  if (!history) return null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-white">Match History</h3>
        <div className="flex gap-1">
          {(['session', 'timeline'] as const).map(tab => (
            <button key={tab} onClick={() => setHistoryTab(tab)} className={`px-3 py-1 rounded text-xs font-medium transition-colors ${historyTab === tab ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white bg-gray-800'}`}>
              {tab === 'session' ? 'By Session' : 'Timeline'}
            </button>
          ))}
        </div>
      </div>

      {history.items.length === 0 && <p className="text-gray-500 text-sm">No rated matches yet.</p>}

      {/* By Session */}
      {history.items.length > 0 && historyTab === 'session' && (() => {
        const groups = (() => {
          const eventMap = new Map<string, { event_id: string | null; event_name: string | null; event_type: string | null; sessions: { session_id: string | null; session_date: string | null; matches: RatingHistoryEntry[] }[] }>()
          for (const item of history.items) {
            const eid = item.event_id ?? '__none__'
            if (!eventMap.has(eid)) {
              eventMap.set(eid, { event_id: item.event_id, event_name: item.event_name, event_type: item.event_type, sessions: [] })
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
        })()

        return (
          <div className="space-y-4">
            {groups.map(eg => {
              const allMatches = eg.sessions.flatMap(s => s.matches)
              const net = netDelta(allMatches)
              return (
                <div key={eg.event_id ?? 'none'} className="border border-gray-800 rounded-lg overflow-hidden">
                  <div className="flex items-center gap-3 px-4 py-3 bg-gray-800/60">
                    <span className="font-medium text-white text-sm flex-1 truncate">{eg.event_name ?? 'Unknown Event'}</span>
                    {eventTypeBadge(eg.event_type)}
                    <span className="text-xs text-gray-400">{allMatches.length} matches</span>
                    <span className={`text-xs font-mono font-semibold w-14 text-right ${net >= 0 ? 'text-green-400' : 'text-red-400'}`}>{net >= 0 ? '+' : ''}{net.toFixed(1)}</span>
                  </div>

                  <div className="divide-y divide-gray-800">
                    {eg.sessions.map(sg => {
                      const sessionKey = `${eg.event_id}-${sg.session_id ?? 'adhoc'}`
                      const sessionNet = netDelta(sg.matches)
                      const isExpanded = expandedSessions.has(sessionKey)
                      return (
                        <div key={sessionKey}>
                          <button className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800/40 transition-colors text-left" onClick={() => toggleSession(sessionKey)}>
                            <span className="text-gray-500 text-xs w-4">{isExpanded ? '▾' : '▸'}</span>
                            <span className="text-sm text-gray-300 flex-1">{sg.session_date ? `Session · ${sg.session_date}` : 'Ad-hoc matches'}</span>
                            <span className="text-xs text-gray-500">{sg.matches.length} matches</span>
                            <span className={`text-xs font-mono font-semibold w-14 text-right ${sessionNet >= 0 ? 'text-green-400' : 'text-red-400'}`}>{sessionNet >= 0 ? '+' : ''}{sessionNet.toFixed(1)}</span>
                          </button>

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
                                      <React.Fragment key={r.history_id}>
                                        <tr className="hover:bg-gray-800/30 transition-colors">
                                          <td className="px-3 py-2"><span className={`font-bold ${r.result === 'WIN' ? 'text-green-400' : 'text-red-400'}`}>{r.result}</span></td>
                                          <td className="px-3 py-2"><div className="text-gray-300">vs {r.opponent_name ?? '—'}</div></td>
                                          <td className="px-3 py-2 text-gray-400 hidden sm:table-cell font-mono">{formatScore(r)}</td>
                                          <td className="px-3 py-2"><div className="flex flex-wrap gap-1 items-center">{matchTypeBadge(r)}{r.diminishing_signal_applied && <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-orange-900/50 text-orange-300" title="Diminishing signal — treated as Friendly">DS</span>}</div></td>
                                          <td className="px-3 py-2 text-right text-gray-400 font-mono">{r.opponent_rating_before != null ? Math.round(r.opponent_rating_before) : '—'}</td>
                                          <td className="px-3 py-2 text-right font-mono text-gray-300 whitespace-nowrap">{Math.round(r.rating_before)} → {Math.round(r.rating_after)}</td>
                                          <td className="px-3 py-2 text-left hidden md:table-cell text-xs whitespace-nowrap">{r.tier_before === r.tier_after ? <span className="text-gray-400">{r.tier_before}</span> : <span className="text-yellow-400">{r.tier_before} → {r.tier_after}</span>}</td>
                                          <td className="px-3 py-2 text-right text-gray-400 font-mono hidden lg:table-cell">{r.k_eff !== null ? r.k_eff.toFixed(1) : '—'}</td>
                                          <td className="px-3 py-2 text-right text-gray-400 font-mono hidden lg:table-cell">{r.expected_score !== null ? `${(r.expected_score * 100).toFixed(0)}%` : '—'}</td>
                                          <td className={`px-3 py-2 text-right font-mono font-semibold ${r.delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>{r.delta >= 0 ? '+' : ''}{r.delta.toFixed(1)}</td>
                                          {canSeeBreakdown && (<td className="px-3 py-2 text-center">{r.delta_breakdown && (<button onClick={() => toggleBreakdown(r.history_id)} className="text-gray-600 hover:text-gray-300 transition-colors" title="Toggle breakdown">{expandedBreakdowns.has(r.history_id) ? '▴' : '▾'}</button>)}</td>)}
                                        </tr>
                                        {canSeeBreakdown && expandedBreakdowns.has(r.history_id) && r.delta_breakdown && (
                                          <tr>
                                            <td colSpan={totalCols} className="px-4 py-2 bg-gray-900"><pre className="text-xs text-gray-400 overflow-x-auto">{JSON.stringify(r.delta_breakdown, null, 2)}</pre></td>
                                          </tr>
                                        )}
                                      </React.Fragment>
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

      {/* Timeline */}
      {history.items.length > 0 && historyTab === 'timeline' && (
        <div className="space-y-1">
          {history.items.map(r => (
            <div key={r.history_id}>
              <div className="flex items-center gap-3 py-2 border-b border-gray-800 last:border-0">
                <span className={`w-10 text-xs font-bold ${r.result === 'WIN' ? 'text-green-400' : 'text-red-400'}`}>{r.result}</span>
                <span className="flex-1 text-sm text-gray-300 truncate">vs {r.opponent_name}</span>
                <span className="text-xs text-gray-500 hidden sm:block">{r.event_name ?? '—'}</span>
                <span className="text-xs text-gray-500">{r.match_date?.slice(0, 10) ?? '—'}</span>
                {r.tier_before === r.tier_after ? <span className="text-xs text-gray-500 hidden md:block">{r.tier_before}</span> : <span className="text-xs text-yellow-400 hidden md:block whitespace-nowrap">{r.tier_before} → {r.tier_after}</span>}
                <span className={`text-xs font-mono font-semibold w-14 text-right ${r.delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>{r.delta >= 0 ? '+' : ''}{r.delta.toFixed(1)}</span>
                {canSeeBreakdown && r.delta_breakdown && (<button onClick={() => toggleBreakdown(`tl-${r.history_id}`)} className="text-gray-600 hover:text-gray-300 transition-colors text-xs">{expandedBreakdowns.has(`tl-${r.history_id}`) ? '▴' : '▾'}</button>)}
              </div>
              {canSeeBreakdown && expandedBreakdowns.has(`tl-${r.history_id}`) && r.delta_breakdown && (
                <pre className="text-xs text-gray-400 bg-gray-800 p-2 rounded overflow-x-auto mb-1">{JSON.stringify(r.delta_breakdown, null, 2)}</pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default {}
